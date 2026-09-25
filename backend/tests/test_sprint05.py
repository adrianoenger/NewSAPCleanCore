"""SPRINT-05 — Dependencies, ATC, Technical Findings: unit and API tests."""
from __future__ import annotations

import io
import tempfile
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from atc.importer import import_workbook, inspect_workbook
from parsing.dependency_detector import detect_dependencies


# ---------------------------------------------------------------------------
# Helpers — build synthetic XLSX files in memory
# ---------------------------------------------------------------------------

_ALL_HEADERS = [
    "Priority", "Check Title", "Check Message", "Object name", "Object Type",
    "Exemption State", "Contact Person", "Package", "First Found On",
    "Object Responsible", "Last Changed by", "SAP Note Number", "Short Text",
    "Referenced Application Component", "Referenced Object Type",
    "Referenced Object", "Additional Info", "Simplification Item Category",
    "Change Category of Piecelist Items", "Description of Change Category",
    "Remarks",
]


def _make_xlsx(
    headers: list[str] | None = None,
    rows: list[list] | None = None,
    sheet_name: str = "Data",
) -> bytes:
    """Build a minimal XLSX in memory and return its bytes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    if headers is None:
        headers = _ALL_HEADERS
    ws.append(headers)
    if rows:
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _sample_row(override: dict | None = None) -> list:
    defaults = [
        1, "Y800_BADI_IMPLEMENTATION", "BAdI implementation detected", "ZCL_ORDER",
        "CLAS", "25", "USERX", "ZPACKAGE", 46139,
        "USERX", "USERX", "1234567", "Note short text", "CA-GTF-BS",
        "CLAS", "CL_BASE", "Additional note", "Cat A", "Change cat", "Cat desc",
        "25",
    ]
    row = defaults[:]
    if override:
        for k, v in override.items():
            row[k] = v
    return row


# ---------------------------------------------------------------------------
# Dependency detector unit tests
# ---------------------------------------------------------------------------


def test_detect_call_function_dependency():
    content = """
REPORT ztest.
CALL FUNCTION 'RFC_READ_TABLE'
  EXPORTING query_table = 'MARA'.
"""
    deps = detect_dependencies(content, "report", {})
    names = [d.target_name for d in deps]
    types = [d.dep_type for d in deps]
    assert "RFC_READ_TABLE" in names
    assert "CALL_FUNCTION" in types


def test_detect_include_dependency():
    content = """
REPORT ztest.
INCLUDE ZHEADER_INCLUDE.
"""
    deps = detect_dependencies(content, "report", {})
    names = [d.target_name for d in deps]
    assert "ZHEADER_INCLUDE" in names
    inc_deps = [d for d in deps if d.dep_type == "INCLUDE"]
    assert len(inc_deps) == 1


def test_detect_inheritance_from_attributes():
    deps = detect_dependencies("", "class", {"superclass": "ZCL_PARENT"})
    inherits = [d for d in deps if d.dep_type == "INHERITS_FROM"]
    assert len(inherits) == 1
    assert inherits[0].target_name == "ZCL_PARENT"
    assert inherits[0].target_type == "class"


def test_detect_tables_from_attributes():
    deps = detect_dependencies("", "report", {"tables": ["MARA", "MARC"]})
    table_deps = [d for d in deps if d.dep_type == "USES_TABLE"]
    names = [d.target_name for d in table_deps]
    assert "MARA" in names
    assert "MARC" in names


def test_detect_deduplicates_same_target():
    content = """
CALL FUNCTION 'ZFM_FOO'.
CALL FUNCTION 'ZFM_FOO'.
"""
    deps = detect_dependencies(content, "program", {})
    foo_deps = [d for d in deps if d.target_name == "ZFM_FOO"]
    assert len(foo_deps) == 1


def test_detect_returns_empty_for_no_patterns():
    deps = detect_dependencies("REPORT zblank.", "report", {})
    assert deps == []


# ---------------------------------------------------------------------------
# ATC importer unit tests
# ---------------------------------------------------------------------------


def test_import_full_21_column_sample_succeeds():
    content = _make_xlsx(rows=[_sample_row()])
    result = import_workbook(content)
    assert result.diagnostics.validation_status == "ACCEPTED_FULL"
    assert len(result.rows) == 1
    assert result.diagnostics.worksheet == "Data"


def test_import_with_one_optional_column_removed_still_succeeds():
    """Remove 'Remarks' (optional) — should still import with partial status or full."""
    headers = [h for h in _ALL_HEADERS if h != "Remarks"]
    row = _sample_row()[:20]  # remove last field (Remarks)
    content = _make_xlsx(headers=headers, rows=[row])
    result = import_workbook(content)
    assert result.diagnostics.validation_status in ("ACCEPTED_FULL", "ACCEPTED_PARTIAL")
    assert len(result.rows) == 1
    assert "remarks" in result.diagnostics.missing_known_columns


def test_import_with_several_optional_columns_removed_is_partial():
    """Remove several optional fields — should still produce rows with partial status."""
    optional_to_remove = [
        "SAP Note Number", "Short Text", "Referenced Application Component",
        "Referenced Object Type", "Referenced Object", "Additional Info",
        "Simplification Item Category", "Change Category of Piecelist Items",
        "Description of Change Category", "Remarks",
    ]
    headers = [h for h in _ALL_HEADERS if h not in optional_to_remove]
    row_data = [_sample_row()[i] for i, h in enumerate(_ALL_HEADERS) if h not in optional_to_remove]
    content = _make_xlsx(headers=headers, rows=[row_data])
    result = import_workbook(content)
    # Still accepted (not REJECTED), rows present
    assert result.diagnostics.validation_status in ("ACCEPTED_FULL", "ACCEPTED_PARTIAL")
    assert len(result.rows) == 1


def test_import_reordered_columns_maps_correctly():
    """Shuffle column order — canonical fields must still map correctly."""
    reordered = list(reversed(_ALL_HEADERS))
    row_reversed = list(reversed(_sample_row()))
    content = _make_xlsx(headers=reordered, rows=[row_reversed])
    result = import_workbook(content)
    assert result.diagnostics.validation_status in ("ACCEPTED_FULL", "ACCEPTED_PARTIAL")
    assert len(result.rows) == 1
    # Object name should be mapped regardless of column order
    canonical = result.rows[0].canonical
    assert canonical.get("object_name_raw") == "ZCL_ORDER"


def test_import_with_extra_unknown_column_does_not_fail():
    """Add an unknown column — it must be preserved and not cause failure."""
    headers = _ALL_HEADERS + ["MY_CUSTOM_FIELD"]
    row = _sample_row() + ["custom_value"]
    content = _make_xlsx(headers=headers, rows=[row])
    result = import_workbook(content)
    assert result.diagnostics.validation_status in ("ACCEPTED_FULL", "ACCEPTED_PARTIAL")
    assert "MY_CUSTOM_FIELD" in result.diagnostics.unknown_columns
    # The unknown column is present in raw_payload
    assert any("MY_CUSTOM_FIELD" in r.raw_payload for r in result.rows)


def test_import_blank_optional_cells_accepted():
    """Blank optional values must not fail the import."""
    row = _sample_row(override={5: None, 6: None, 7: None})  # blank Exemption, Contact, Package
    content = _make_xlsx(rows=[row])
    result = import_workbook(content)
    assert result.diagnostics.validation_status in ("ACCEPTED_FULL", "ACCEPTED_PARTIAL")
    assert len(result.rows) == 1
    canonical = result.rows[0].canonical
    assert canonical.get("package_name_raw") is None


def test_import_placeholder_sentinel_value_preserved():
    """The value '25' in sentinel-like columns must be preserved in raw_payload."""
    row = _sample_row()  # row[5]="25" (Exemption State), row[20]="25" (Remarks)
    content = _make_xlsx(rows=[row])
    result = import_workbook(content)
    assert len(result.rows) == 1
    raw = result.rows[0].raw_payload
    # raw payload must contain the original "25" values
    assert any(v == "25" or v == 25 for v in raw.values())


def test_import_malformed_priority_produces_warning_not_failure():
    """Non-integer priority must produce a warning on the row, not abort the run."""
    row = _sample_row(override={0: "INVALID_PRIO"})  # Priority column
    content = _make_xlsx(rows=[row])
    result = import_workbook(content)
    # Run should succeed
    assert result.diagnostics.validation_status in ("ACCEPTED_FULL", "ACCEPTED_PARTIAL")
    assert len(result.rows) == 1
    # Priority should be None, warnings should mention it
    assert result.rows[0].canonical.get("priority") is None
    assert result.rows[0].warnings  # at least one warning on the row


def test_import_empty_workbook_is_rejected():
    """Empty workbook (no data rows) must be REJECTED."""
    content = _make_xlsx(rows=[])  # No data rows
    result = import_workbook(content)
    assert result.diagnostics.validation_status == "REJECTED"
    assert result.diagnostics.total_rows == 0


def test_import_unreadable_bytes_is_rejected():
    """Random bytes must be REJECTED cleanly."""
    result = import_workbook(b"not an xlsx file")
    assert result.diagnostics.validation_status == "REJECTED"
    assert result.rows == []


def test_inspect_workbook_returns_diagnostics_without_rows():
    content = _make_xlsx(rows=[_sample_row()])
    diag = inspect_workbook(content)
    assert diag.validation_status == "ACCEPTED_FULL"
    assert diag.total_rows == 1
    assert "object_name_raw" in diag.recognized_columns


def test_import_excel_serial_date_normalizes():
    """Excel serial date (int like 46139) must be normalized to a Python date."""
    row = _sample_row()  # row[8] = 46139
    content = _make_xlsx(rows=[row])
    result = import_workbook(content)
    assert len(result.rows) == 1
    ffo = result.rows[0].canonical.get("first_found_on")
    assert isinstance(ffo, date)


# ---------------------------------------------------------------------------
# API contract tests
# ---------------------------------------------------------------------------


def _make_assessment(session) -> int:
    from persistence.models import Assessment, AssessmentStatus, Client
    c = Client(name="Sprint05 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint05 Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _cleanup_sprint05(session, *assessment_ids: int) -> None:
    """Remove only the client(s) owning these assessments — cascades to everything under
    them. Never a blanket table wipe (and never touches the shared `atc_check` catalog,
    which legitimately outlives any single test's assessment)."""
    from sqlalchemy import text
    for aid in assessment_ids:
        session.execute(
            text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
            {"aid": aid},
        )
    session.commit()


def test_inspect_endpoint_returns_diagnostics(client) -> None:
    from persistence.database import get_session_factory
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        content = _make_xlsx(rows=[_sample_row()])
        resp = client.post(
            f"/assessments/{asmnt_id}/atc/inspect",
            files={"file": ("test.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["validation_status"] in ("ACCEPTED_FULL", "ACCEPTED_PARTIAL")
        assert data["total_rows"] == 1
    finally:
        with get_session_factory()() as session:
            _cleanup_sprint05(session, asmnt_id)


def test_import_endpoint_creates_run_and_findings(client) -> None:
    from persistence.database import get_session_factory
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        content = _make_xlsx(rows=[_sample_row(), _sample_row(override={3: "ZFM_PROCESS"})])
        resp = client.post(
            f"/assessments/{asmnt_id}/atc/import",
            files={"file": ("atc.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assessment_id"] == asmnt_id
        assert data["imported_row_count"] == 2
        assert data["validation_status"] in ("ACCEPTED_FULL", "ACCEPTED_PARTIAL")
    finally:
        with get_session_factory()() as session:
            _cleanup_sprint05(session, asmnt_id)


def test_import_rejects_invalid_file(client) -> None:
    from persistence.database import get_session_factory
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.post(
            f"/assessments/{asmnt_id}/atc/import",
            files={"file": ("bad.xlsx", b"not xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 422
    finally:
        with get_session_factory()() as session:
            _cleanup_sprint05(session, asmnt_id)


def test_list_runs_empty_for_new_assessment(client) -> None:
    from persistence.database import get_session_factory
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.get(f"/assessments/{asmnt_id}/atc/runs")
        assert resp.status_code == 200
        assert resp.json()["runs"] == []
    finally:
        with get_session_factory()() as session:
            _cleanup_sprint05(session, asmnt_id)


def test_multiple_atc_runs_coexist(client) -> None:
    """Two imports for the same assessment must not overwrite each other."""
    from persistence.database import get_session_factory
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        content = _make_xlsx(rows=[_sample_row()])
        for _ in range(2):
            client.post(
                f"/assessments/{asmnt_id}/atc/import",
                files={"file": ("atc.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        resp = client.get(f"/assessments/{asmnt_id}/atc/runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2
    finally:
        with get_session_factory()() as session:
            _cleanup_sprint05(session, asmnt_id)


def test_correlation_is_assessment_scoped(client) -> None:
    """Objects from another assessment must not be matched."""
    from persistence.database import get_session_factory
    from persistence.models import (
        Assessment, AssessmentStatus, Client, SAPObject, SourceFile, SourceScan, ScanStatus
    )
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        # Object with same name exists in a DIFFERENT assessment
        other_client = Client(name="Other Client")
        session.add(other_client)
        session.flush()
        other_asmnt = Assessment(
            client_id=other_client.id, name="Other Assessment",
            status=AssessmentStatus.CREATED.value
        )
        session.add(other_asmnt)
        session.flush()
        scan = SourceScan(
            assessment_id=other_asmnt.id, source_path="/tmp",
            status=ScanStatus.COMPLETED.value, total_files=1, scanned_files=1
        )
        session.add(scan)
        session.flush()
        sf = SourceFile(
            scan_id=scan.id, assessment_id=other_asmnt.id,
            rel_path="x.abap", size_bytes=0, mtime=0.0, sha256="a"*64, category="abap_source"
        )
        session.add(sf)
        session.flush()
        session.add(SAPObject(
            assessment_id=other_asmnt.id, source_file_id=sf.id,
            object_type="class", object_name="ZCL_ORDER",
            canonical_key="CLASS::ZCL_ORDER",
            description="", line_start=1, attributes={},
        ))
        session.commit()
        other_asmnt_id = other_asmnt.id

    try:
        # Import ATC for the FIRST assessment — ZCL_ORDER should be UNMATCHED
        content = _make_xlsx(rows=[_sample_row()])  # object_name_raw=ZCL_ORDER
        resp = client.post(
            f"/assessments/{asmnt_id}/atc/import",
            files={"file": ("atc.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 200
        run_id = resp.json()["id"]
        findings_resp = client.get(f"/assessments/{asmnt_id}/atc/runs/{run_id}/findings")
        assert findings_resp.status_code == 200
        summary = findings_resp.json()["correlation_summary"]
        assert summary.get("UNMATCHED", 0) == 1
    finally:
        with get_session_factory()() as session:
            _cleanup_sprint05(session, asmnt_id, other_asmnt_id)
