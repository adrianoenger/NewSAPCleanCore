"""CAP-002 (SPRINT-17) — bounded source-snippet endpoint backing Monaco in Technical View."""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import text

from persistence.database import get_session_factory
from persistence.models import (
    ArtifactCategory,
    Assessment,
    AssessmentStatus,
    Client,
    SAPObject,
    ScanStatus,
    SourceFile,
    SourceScan,
)


def _cleanup(session, assessment_id: int) -> None:
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def _seed_object(session, tmp_dir: str, rel_path: str, content: str, category: str) -> tuple[int, int]:
    c = Client(name="Sprint17 Source Snippet Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint17 Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.flush()

    (Path(tmp_dir) / rel_path).write_text(content, encoding="utf-8")

    scan = SourceScan(
        assessment_id=a.id,
        source_path=tmp_dir,
        status=ScanStatus.COMPLETED.value,
        total_files=1,
        scanned_files=1,
    )
    session.add(scan)
    session.flush()

    sf = SourceFile(
        scan_id=scan.id,
        assessment_id=a.id,
        rel_path=rel_path,
        size_bytes=len(content.encode("utf-8")),
        mtime=0.0,
        sha256="0" * 64,
        category=category,
    )
    session.add(sf)
    session.flush()

    obj = SAPObject(
        assessment_id=a.id,
        source_file_id=sf.id,
        object_type="class",
        object_name="ZCL_TEST",
        canonical_key="class:zcl_test",
        description="",
        line_start=1,
        line_end=3,
        attributes={},
    )
    session.add(obj)
    session.commit()
    return a.id, obj.id


def test_get_source_returns_bounded_content_with_language(client) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with get_session_factory()() as session:
            asmnt_id, obj_id = _seed_object(
                session, tmp, "ZCL_TEST.abap", "CLASS zcl_test.\nENDCLASS.\n", ArtifactCategory.ABAP_SOURCE.value
            )
        try:
            resp = client.get(f"/assessments/{asmnt_id}/objects/{obj_id}/source")
            assert resp.status_code == 200
            data = resp.json()
            assert data["language"] == "abap"
            assert "CLASS zcl_test" in data["content"]
            assert data["truncated"] is False
            assert data["line_start"] == 1
            assert data["line_end"] == 3
        finally:
            with get_session_factory()() as session:
                _cleanup(session, asmnt_id)


def test_get_source_truncates_large_file(client) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        big_content = "* comment line\n" * 60_000  # well over the 512_000-byte cap
        with get_session_factory()() as session:
            asmnt_id, obj_id = _seed_object(
                session, tmp, "ZBIG.abap", big_content, ArtifactCategory.ABAP_SOURCE.value
            )
        try:
            resp = client.get(f"/assessments/{asmnt_id}/objects/{obj_id}/source")
            assert resp.status_code == 200
            data = resp.json()
            assert data["truncated"] is True
            assert len(data["content"].encode("utf-8")) <= 512_000
        finally:
            with get_session_factory()() as session:
                _cleanup(session, asmnt_id)


def _seed_object_with_raw_rel_path(session, scan_root: str, rel_path: str, category: str) -> tuple[int, int]:
    """Like `_seed_object`, but does not write the file under `scan_root` — used to simulate a
    poisoned/legacy `SourceFile.rel_path` that escapes the scan directory."""
    c = Client(name="Sprint17 Source Snippet Traversal Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint17 Traversal Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.flush()

    scan = SourceScan(
        assessment_id=a.id,
        source_path=scan_root,
        status=ScanStatus.COMPLETED.value,
        total_files=1,
        scanned_files=1,
    )
    session.add(scan)
    session.flush()

    sf = SourceFile(
        scan_id=scan.id,
        assessment_id=a.id,
        rel_path=rel_path,
        size_bytes=0,
        mtime=0.0,
        sha256="0" * 64,
        category=category,
    )
    session.add(sf)
    session.flush()

    obj = SAPObject(
        assessment_id=a.id,
        source_file_id=sf.id,
        object_type="class",
        object_name="ZCL_TRAVERSAL",
        canonical_key="class:zcl_traversal",
        description="",
        line_start=1,
        line_end=1,
        attributes={},
    )
    session.add(obj)
    session.commit()
    return a.id, obj.id


def test_get_source_rejects_rel_path_escaping_scan_root(client) -> None:
    """A `..`-relative `rel_path` must never let the endpoint read a file outside the scan
    directory, even though it is normally trustworthy first-party data (defense in depth)."""
    with tempfile.TemporaryDirectory() as parent:
        scan_root = Path(parent) / "scan_root"
        scan_root.mkdir()
        secret_dir = Path(parent) / "secret"
        secret_dir.mkdir()
        (secret_dir / "secret.txt").write_text("TOP SECRET", encoding="utf-8")

        escaping_rel_path = str(Path("..") / "secret" / "secret.txt")
        with get_session_factory()() as session:
            asmnt_id, obj_id = _seed_object_with_raw_rel_path(
                session, str(scan_root), escaping_rel_path, ArtifactCategory.ABAP_SOURCE.value
            )
        try:
            resp = client.get(f"/assessments/{asmnt_id}/objects/{obj_id}/source")
            assert resp.status_code == 422
        finally:
            with get_session_factory()() as session:
                _cleanup(session, asmnt_id)


def test_get_source_rejects_absolute_rel_path(client) -> None:
    with tempfile.TemporaryDirectory() as parent:
        scan_root = Path(parent) / "scan_root"
        scan_root.mkdir()
        secret_file = Path(parent) / "secret.txt"
        secret_file.write_text("TOP SECRET", encoding="utf-8")

        with get_session_factory()() as session:
            asmnt_id, obj_id = _seed_object_with_raw_rel_path(
                session, str(scan_root), str(secret_file), ArtifactCategory.ABAP_SOURCE.value
            )
        try:
            resp = client.get(f"/assessments/{asmnt_id}/objects/{obj_id}/source")
            assert resp.status_code == 422
        finally:
            with get_session_factory()() as session:
                _cleanup(session, asmnt_id)


def test_get_source_404_for_unknown_object(client) -> None:
    with get_session_factory()() as session:
        c = Client(name="Sprint17 Source Snippet 404 Client")
        session.add(c)
        session.flush()
        a = Assessment(client_id=c.id, name="Sprint17 404 Test", status=AssessmentStatus.CREATED.value)
        session.add(a)
        session.commit()
        asmnt_id = a.id
    try:
        resp = client.get(f"/assessments/{asmnt_id}/objects/999999/source")
        assert resp.status_code == 404
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
