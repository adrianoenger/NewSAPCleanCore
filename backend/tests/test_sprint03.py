"""SPRINT-03 — SAP Object Parsing: parser unit tests and API contract tests."""
import tempfile
from pathlib import Path

import pytest

from parsing.abap_class import parse_abap_class
from parsing.abap_function import parse_abap_function
from parsing.abap_program import parse_abap_program
from parsing.ddic import parse_ddic
from parsing.dispatcher import parse_file


# ---------------------------------------------------------------------------
# Parser unit tests
# ---------------------------------------------------------------------------


def test_parse_abap_class_extracts_name_and_methods() -> None:
    src = """\
CLASS zcl_order DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    METHODS: create_order IMPORTING iv_id TYPE string,
             get_status RETURNING VALUE(rv) TYPE string.
ENDCLASS.
CLASS zcl_order IMPLEMENTATION.
ENDCLASS."""
    objects = parse_abap_class(src)
    assert len(objects) == 1
    obj = objects[0]
    assert obj.object_type == "class"
    assert obj.object_name == "ZCL_ORDER"
    assert "CREATE_ORDER" in obj.attributes["methods"]
    assert obj.line_start == 1
    assert obj.line_end is not None


def test_parse_abap_class_with_inheritance() -> None:
    src = """\
CLASS zcl_child DEFINITION INHERITING FROM zcl_parent.
ENDCLASS.
CLASS zcl_child IMPLEMENTATION.
ENDCLASS."""
    objects = parse_abap_class(src)
    assert len(objects) == 1
    assert objects[0].attributes.get("superclass") == "ZCL_PARENT"


def test_parse_abap_function_module() -> None:
    src = """\
FUNCTION zfm_test.
*"----------------------------------------------------------------------
*"*"Local Interface:
*"  IMPORTING
*"     VALUE(IV_ID) TYPE  STRING
*"  EXPORTING
*"     VALUE(EV_STATUS) TYPE  STRING
*"----------------------------------------------------------------------
  ev_status = 'OK'.
ENDFUNCTION."""
    objects = parse_abap_function(src)
    assert len(objects) == 1
    obj = objects[0]
    assert obj.object_type == "function_module"
    assert obj.object_name == "ZFM_TEST"
    assert obj.line_start == 1


def test_parse_abap_program() -> None:
    src = """\
REPORT zmy_report.
TABLES: mara, marc.
SELECT-OPTIONS: so_matnr FOR mara-matnr.
PARAMETERS: p_date TYPE sy-datum.
START-OF-SELECTION.
  WRITE 'Hello'."""
    objects = parse_abap_program(src)
    assert len(objects) == 1
    obj = objects[0]
    assert obj.object_type == "report"
    assert obj.object_name == "ZMY_REPORT"
    assert "MARA" in obj.attributes.get("tables", [])


def test_parse_ddic_table() -> None:
    src = """\
DDIC Table Definition: ZCUST_HDR
Table Type: Transparent table
Delivery Class: A

Fields:
  MANDT MANDT  3 Client
  HDR_ID CHAR 20 Header ID"""
    objects = parse_ddic(src, "ZCUST_HDR.tabl")
    assert len(objects) == 1
    obj = objects[0]
    assert obj.object_type == "ddic_table"
    assert obj.object_name == "ZCUST_HDR"
    assert "fields" in obj.attributes


def test_parse_ddic_domain() -> None:
    src = """\
DDIC Domain: ZSTATUS_D
Data Type: CHAR
Length: 2

Fixed Values:
  OP Open
  CL Closed"""
    objects = parse_ddic(src, "ZSTATUS_D.doma")
    assert len(objects) == 1
    obj = objects[0]
    assert obj.object_type == "ddic_domain"
    assert obj.object_name == "ZSTATUS_D"
    assert "fixed_values" in obj.attributes


def test_dispatcher_routes_abap_source_to_class_parser() -> None:
    src = """\
CLASS zcl_x DEFINITION.
ENDCLASS.
CLASS zcl_x IMPLEMENTATION.
ENDCLASS."""
    objects = parse_file(src, "ZCL_X.abap", "abap_source")
    assert len(objects) == 1
    assert objects[0].object_type == "class"


def test_dispatcher_routes_ddic_category() -> None:
    src = "DDIC Table Definition: ZTBL\nTable Type: Transparent table\nDelivery Class: A\n\nFields:\n  COL1 CHAR 10 Column"
    objects = parse_file(src, "ZTBL.tabl", "ddic")
    assert len(objects) == 1
    assert objects[0].object_type == "ddic_table"


def test_dispatcher_returns_empty_for_unsupported_category() -> None:
    objects = parse_file("<data>value</data>", "meta.xml", "xml_metadata")
    assert objects == []


# ---------------------------------------------------------------------------
# API contract tests
# ---------------------------------------------------------------------------


def _setup_assessment_with_files(session, scan_root: str) -> tuple[int, int]:
    """Create minimal assessment + scan + source files; return (assessment_id, scan_id)."""
    from persistence.models import (
        ArtifactCategory,
        Assessment,
        AssessmentStatus,
        Client,
        SourceFile,
        SourceScan,
        ScanStatus,
    )

    c = Client(name="Parse Test Client")
    session.add(c)
    session.flush()
    asmnt = Assessment(client_id=c.id, name="Parse Test", status=AssessmentStatus.CREATED.value)
    session.add(asmnt)
    session.flush()

    p = Path(scan_root)
    abap_file = p / "ZCL_TEST.abap"
    abap_file.write_text(
        "CLASS zcl_test DEFINITION.\n  PUBLIC SECTION.\n    METHODS: run.\nENDCLASS.\n"
        "CLASS zcl_test IMPLEMENTATION.\nENDCLASS.\n"
    )

    scan = SourceScan(
        assessment_id=asmnt.id,
        source_path=scan_root,
        status=ScanStatus.COMPLETED.value,
        total_files=1,
        scanned_files=1,
    )
    session.add(scan)
    session.flush()

    sf = SourceFile(
        scan_id=scan.id,
        assessment_id=asmnt.id,
        rel_path="ZCL_TEST.abap",
        size_bytes=abap_file.stat().st_size,
        mtime=abap_file.stat().st_mtime,
        sha256="a" * 64,
        category=ArtifactCategory.ABAP_SOURCE.value,
    )
    session.add(sf)
    session.commit()
    return asmnt.id, scan.id


def _cleanup(session) -> None:
    from sqlalchemy import text
    for tbl in ("sap_object", "source_file", "source_scan", "assessment", "client"):
        session.execute(text(f"DELETE FROM {tbl}"))
    session.commit()


def test_parse_endpoint_returns_accepted(client) -> None:
    from persistence.database import get_session_factory
    from settings import get_settings

    scan_root = Path(get_settings().scan_root)
    with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
        with get_session_factory()() as session:
            asmnt_id, scan_id = _setup_assessment_with_files(session, tmp)
        try:
            resp = client.post(f"/assessments/{asmnt_id}/scans/{scan_id}/parse")
            assert resp.status_code == 202
            assert resp.json()["status"] == "accepted"
        finally:
            with get_session_factory()() as session:
                _cleanup(session)


def test_list_objects_empty_for_new_assessment(client) -> None:
    from persistence.database import get_session_factory
    from settings import get_settings

    scan_root = Path(get_settings().scan_root)
    with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
        with get_session_factory()() as session:
            asmnt_id, scan_id = _setup_assessment_with_files(session, tmp)
        try:
            resp = client.get(f"/assessments/{asmnt_id}/objects")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            with get_session_factory()() as session:
                _cleanup(session)


def test_list_objects_unknown_assessment_returns_404(client) -> None:
    resp = client.get("/assessments/99999/objects")
    assert resp.status_code == 404


def test_get_object_not_found(client) -> None:
    from persistence.database import get_session_factory
    from settings import get_settings

    scan_root = Path(get_settings().scan_root)
    with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
        with get_session_factory()() as session:
            asmnt_id, _ = _setup_assessment_with_files(session, tmp)
        try:
            resp = client.get(f"/assessments/{asmnt_id}/objects/99999")
            assert resp.status_code == 404
        finally:
            with get_session_factory()() as session:
                _cleanup(session)
