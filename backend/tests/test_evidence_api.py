"""SPRINT-08 CAP-008 — evidence dataset API routes: inspect/create/list/detail,
object-scoped correlation drill-down."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from sqlalchemy import text

from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    SAPObject,
    ScanStatus,
    SourceFile,
    SourceScan,
)
from settings import get_settings

_PANAYA_XML = """<?xml version="1.0"?>
<ROOT_ELEMENT>
<HEADER SYSTEM_ID="QAS" CLIENT="300" EXPORT_TOOL_VERSION="26.07.15.10_200"/>
<REPOSITORY_OBJECTS>
<TADIR PGMID="R3TR" OBJECT="CLAS" OBJ_NAME="ZCL_ORDER" DEVCLASS="ZPKG" AUTHOR="DEV1" CREATED_ON="20200101"/>
</REPOSITORY_OBJECTS>
</ROOT_ELEMENT>
"""


def _panaya_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("export.xml", _PANAYA_XML)
    return buf.getvalue()


def _make_assessment(session) -> int:
    c = Client(name="Evidence API Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Evidence API Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _make_sap_object(session, assessment_id: int) -> int:
    scan = SourceScan(
        assessment_id=assessment_id, source_path="/tmp", status=ScanStatus.COMPLETED.value,
        total_files=1, scanned_files=1,
    )
    session.add(scan)
    session.flush()
    sf = SourceFile(
        scan_id=scan.id, assessment_id=assessment_id, rel_path="x.abap",
        size_bytes=0, mtime=0.0, sha256="a" * 64, category="abap_source",
    )
    session.add(sf)
    session.flush()
    obj = SAPObject(
        assessment_id=assessment_id, source_file_id=sf.id, object_type="CLAS", object_name="ZCL_ORDER",
        canonical_key="CLAS::ZCL_ORDER", description="", line_start=1, attributes={},
    )
    session.add(obj)
    session.commit()
    return obj.id


def _cleanup(session, assessment_id: int) -> None:
    """Remove only the client owning this assessment — cascades to everything under
    it. Never a blanket table wipe against the shared dev database."""
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def test_inspect_unrecognized_file_reports_not_detected(client) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.post(
            f"/assessments/{asmnt_id}/evidence-datasets/inspect",
            files={"file": ("random_export.zip", b"not a real zip", "application/zip")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["detected"] is False
        assert body["dataset_type"] is None
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_safe_basename_strips_traversal_and_rejects_degenerate_names() -> None:
    from api.routes.evidence import _safe_basename

    # Directory components are stripped down to a safe basename, never rejected outright —
    # the caller only ever sees the sanitized leaf name, so no traversal is possible.
    assert _safe_basename("../../etc/panaya.zip") == "panaya.zip"
    assert _safe_basename("/etc/panaya.zip") == "panaya.zip"
    assert _safe_basename("a/b/panaya.zip") == "panaya.zip"

    # A literal backslash survives POSIX-style splitting (no "/" to split on) and is
    # rejected outright rather than risk it being interpreted as a separator downstream.
    import pytest
    from fastapi import HTTPException

    for bad_name in ("..\\..\\windows\\panaya.zip", "..", ".", "", ".hidden.zip"):
        with pytest.raises(HTTPException) as exc_info:
            _safe_basename(bad_name)
        assert exc_info.value.status_code == 400


def test_path_traversal_filename_never_escapes_storage_root(client) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.post(
            f"/assessments/{asmnt_id}/evidence-datasets",
            files={"file": ("../../../panaya.zip", _panaya_zip_bytes(), "application/zip")},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["source_filename"] == "panaya.zip"  # traversal components stripped

        settings = get_settings()
        stored = Path(settings.evidence_storage_path) / str(body["id"]) / "panaya.zip"
        assert stored.exists()
        # Nothing was written above the storage root.
        assert not (Path(settings.evidence_storage_path).parent / "panaya.zip").exists()
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_delete_dataset_removes_record_and_storage_file(client) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    try:
        resp = client.post(
            f"/assessments/{asmnt_id}/evidence-datasets",
            files={"file": ("panaya_export.zip", _panaya_zip_bytes(), "application/zip")},
        )
        assert resp.status_code == 201
        dataset_id = resp.json()["id"]

        settings = get_settings()
        stored = Path(settings.evidence_storage_path) / str(dataset_id) / "panaya_export.zip"
        assert stored.exists()

        del_resp = client.delete(f"/assessments/{asmnt_id}/evidence-datasets/{dataset_id}")
        assert del_resp.status_code == 204

        assert client.get(f"/assessments/{asmnt_id}/evidence-datasets/{dataset_id}").status_code == 404
        assert client.get(f"/assessments/{asmnt_id}/evidence-datasets").json()["total"] == 0
        assert not stored.exists()

        # Deleting again (or a dataset that never existed) 404s instead of erroring.
        assert client.delete(f"/assessments/{asmnt_id}/evidence-datasets/{dataset_id}").status_code == 404
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_create_dataset_imports_and_correlates_to_existing_object(client) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        sap_object_id = _make_sap_object(session, asmnt_id)

    try:
        resp = client.post(
            f"/assessments/{asmnt_id}/evidence-datasets",
            files={"file": ("panaya_export.zip", _panaya_zip_bytes(), "application/zip")},
        )
        assert resp.status_code == 201
        dataset_id = resp.json()["id"]

        # Response body is serialized before the background pipeline task runs
        # (same TestClient behavior as test_sprint06's pipeline-run endpoint test).
        detail = client.get(f"/assessments/{asmnt_id}/evidence-datasets/{dataset_id}").json()
        assert detail["status"] == "IMPORTED_FULL"
        assert detail["dataset_type"] == "PANAYA_ETL"
        assert "TECHNICAL_OBJECT_METADATA" in detail["capabilities"]
        assert detail["records_count"] == 1  # one REPOSITORY_OBJECTS row
        assert detail["correlation_summary"].get("MATCHED_EXACT") == 1

        list_resp = client.get(f"/assessments/{asmnt_id}/evidence-datasets")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 1

        corr_resp = client.get(f"/assessments/{asmnt_id}/objects/{sap_object_id}/evidence-correlations")
        assert corr_resp.status_code == 200
        corr_body = corr_resp.json()
        assert corr_body["total"] == 1
        assert all(c["status"] == "MATCHED_EXACT" for c in corr_body["correlations"])
        assert all(c["dataset_type"] == "PANAYA_ETL" for c in corr_body["correlations"])
        record_types = {c["evidence_record"]["record_type"] for c in corr_body["correlations"]}
        assert record_types == {"panaya_repository_object"}
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
        settings = get_settings()
        storage_dir = Path(settings.evidence_storage_path)
        if storage_dir.exists():
            import shutil
            shutil.rmtree(storage_dir, ignore_errors=True)
