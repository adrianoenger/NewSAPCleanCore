"""SPRINT-08 CAP-004 — Panaya ETL adapter, rewritten against a real ~2.8GB customer export.

The fixture below mirrors the real, verified structure — a bare (unzipped) `.xml` with
`<ROOT_ELEMENT><HEADER .../><ETL_RUN_PARAMS>...</ETL_RUN_PARAMS><REPOSITORY_OBJECTS>...` — not
the invented `<PanayaExport>` profile this adapter originally shipped with before a real sample
was available.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

from sqlalchemy import select, text

from evidence.adapters import panaya
from evidence.adapters.base import SanitizingXMLStream
from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    EvidenceDataset,
    EvidenceDatasetStatus,
    EvidenceRecord,
)

_XML = """<?xml version="1.0" encoding="UTF-8"?>
<ROOT_ELEMENT>
<HEADER SYSTEM_ID="QAS" CLIENT="300" EXPORT_TOOL_VERSION="26.07.15.10_200"/>
<ETL_RUN_PARAMS>
<ETL_RUN_PARAM NAME="EXTRACT_USER_DATA" VALUE="X"/>
</ETL_RUN_PARAMS>
<REPOSITORY_OBJECTS>
<TADIR PGMID="R3TR" OBJECT="CLAS" OBJ_NAME="ZCL_ORDER" DEVCLASS="ZPKG" AUTHOR="DEV1" CREATED_ON="20200101"/>
<TADIR PGMID="R3TR" OBJECT="PROG" OBJ_NAME="ZPROGRAM_REPORT" DEVCLASS="ZPKG" AUTHOR="DEV2" CREATED_ON="20200102"/>
</REPOSITORY_OBJECTS>
<PROGRAMS>
<PROGRAM NAME="ZPROGRAM_REPORT" SUBC="1" CNAM="DEV2" CDAT="20200102"/>
</PROGRAMS>
<FUNCTIONS>
<FUNCTION FUNCNAME="ZFM_PROCESS_ORDER" SHORT_TEXT="Process order"/>
</FUNCTIONS>
<MODIFICATIONS>
<SMODILOG OBJ_TYPE="CLAS" OBJ_NAME="ZCL_ORDER" MOD_USER="DEV1" MOD_DATE="20200103"/>
</MODIFICATIONS>
<NOTES_HEADER>
<CWBNTHEAD NUMM="0000012345" VERSNO="0001"/>
</NOTES_HEADER>
<SCI_HANA_ISSUES>
<TS_HANAA_SCI_CHECK OBJTYPE="CLAS" OBJNAME="ZCL_ORDER" DEVCLASS="ZPKG" AUTHOR="DEV1" KIND="N" TEXT="READ TABLE without INDEX" DETAILS_REF="1"/>
</SCI_HANA_ISSUES>
<SCI_HANA_ISSUES_DETAILS>
<TS_HANA_SCI_CHECK_DETAILS DETAILS_REF="1" TEXT="+CALL_METHOD" INCLUDE="ZPROGRAM_REPORT" LINE="317"/>
</SCI_HANA_ISSUES_DETAILS>
<WHERE_USED_TABLE>
<WBCROSSGT OTYPE="DA" NAME="ZCL_ORDER\\ME:METHOD\\DA:VAR" INCLUDE="ZPROGRAM_REPORT" DIRECT="X"/>
</WHERE_USED_TABLE>
<UNRECOGNIZED_SECTION>
<SOME_ROW FOO="bar"/>
</UNRECOGNIZED_SECTION>
</ROOT_ELEMENT>
"""


def _make_xml(tmp_path: Path, content: str = _XML, name: str = "ETL_QAS_20260101_000000.xml") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _make_assessment(session) -> int:
    c = Client(name="Panaya Adapter Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Panaya Adapter Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _make_dataset(session, assessment_id: int) -> int:
    ds = EvidenceDataset(
        assessment_id=assessment_id, dataset_type=panaya.DATASET_TYPE,
        display_name="ETL_QAS.xml", source_filename="ETL_QAS.xml", source_sha256="a" * 64,
        source_size_bytes=10, importer_name="panaya", importer_version=panaya.IMPORTER_VERSION,
        status=EvidenceDatasetStatus.IMPORTING.value,
    )
    session.add(ds)
    session.flush()
    return ds.id


def _cleanup(session, assessment_id: int) -> None:
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def test_detect_matches_filename_or_content(tmp_path: Path) -> None:
    xml_path = _make_xml(tmp_path)
    assert panaya.detect("Panaya_Export.xml", xml_path)  # filename fast-path
    assert panaya.detect("ETL_QAS_20260101_000000.xml", xml_path)  # content sniffing (EXPORT_TOOL_VERSION)
    assert not panaya.detect("readiness_check.docx", xml_path)

    other = tmp_path / "other.xml"
    other.write_text("<root><foo/></root>")
    assert not panaya.detect("other.xml", other)


def test_detect_also_works_for_zip_wrapped_variant(tmp_path: Path) -> None:
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("export.xml", _XML)
    assert panaya.detect("export.zip", zip_path)


def test_inspect_counts_every_section_and_curated_capabilities(tmp_path: Path) -> None:
    xml_path = _make_xml(tmp_path)
    result = panaya.inspect(xml_path)

    assert result.manifest["section_counts"]["REPOSITORY_OBJECTS"] == 2
    assert result.manifest["section_counts"]["PROGRAMS"] == 1
    assert result.manifest["section_counts"]["FUNCTIONS"] == 1
    assert result.manifest["section_counts"]["MODIFICATIONS"] == 1
    assert result.manifest["section_counts"]["NOTES_HEADER"] == 1
    assert result.manifest["section_counts"]["SCI_HANA_ISSUES"] == 1
    assert result.manifest["section_counts"]["SCI_HANA_ISSUES_DETAILS"] == 1
    assert result.manifest["section_counts"]["WHERE_USED_TABLE"] == 1
    assert result.manifest["section_counts"]["UNRECOGNIZED_SECTION"] == 1  # counted, not dropped silently
    assert set(result.capabilities) == {
        "TECHNICAL_OBJECT_METADATA", "SOURCE_CODE", "S4_CONVERSION_SIGNAL", "DEPENDENCY_SIGNAL",
    }
    assert result.source_system_hint == "QAS"
    assert result.source_client_hint == "300"


def test_import_persists_curated_sections_with_correlatable_object_names(tmp_path: Path) -> None:
    xml_path = _make_xml(tmp_path)
    inspection = panaya.inspect(xml_path)
    batches = panaya.plan_batches(xml_path, inspection)
    assert {b.batch_key for b in batches} == {
        "REPOSITORY_OBJECTS", "PROGRAMS", "FUNCTIONS", "MODIFICATIONS", "NOTES_HEADER",
        "SCI_HANA_ISSUES", "SCI_HANA_ISSUES_DETAILS", "WHERE_USED_TABLE",
    }  # UNRECOGNIZED_SECTION never gets a batch

    with get_session_factory()() as session:
        try:
            asmnt_id = _make_assessment(session)
            ds_id = _make_dataset(session, asmnt_id)
            dataset = session.get(EvidenceDataset, ds_id)

            total = 0
            for batch in batches:
                outcome = panaya.import_batch(xml_path, dataset, batch, session)
                total += outcome.records_imported
                assert outcome.warnings == []  # nothing near the truncation cap in this fixture
            session.commit()
            # 2 repo objects + 1 program + 1 function + 1 modification + 1 note
            # + 1 SCI HANA issue + 1 SCI HANA issue detail + 1 where-used row
            assert total == 9

            records = list(session.scalars(select(EvidenceRecord).where(EvidenceRecord.dataset_id == ds_id)))
            repo_objects = {r.object_name: r.object_type for r in records if r.record_type == "panaya_repository_object"}
            assert repo_objects == {"ZCL_ORDER": "CLAS", "ZPROGRAM_REPORT": "PROG"}

            program = next(r for r in records if r.record_type == "panaya_program")
            assert program.object_name == "ZPROGRAM_REPORT"

            note = next(r for r in records if r.record_type == "panaya_sap_note")
            assert note.object_name is None  # SAP Notes don't correlate to a SAPObject by name
            assert note.normalized_payload["NUMM"] == "0000012345"

            sci_issue = next(r for r in records if r.record_type == "panaya_sci_hana_issue")
            assert (sci_issue.object_name, sci_issue.object_type, sci_issue.package_name) == ("ZCL_ORDER", "CLAS", "ZPKG")
            assert sci_issue.normalized_payload["DETAILS_REF"] == "1"  # preserved for manual join to the detail row

            sci_detail = next(r for r in records if r.record_type == "panaya_sci_hana_issue_detail")
            assert sci_detail.object_name == "ZPROGRAM_REPORT"  # correlates via INCLUDE
            assert sci_detail.normalized_payload["DETAILS_REF"] == "1"  # joins back to the parent check above

            where_used = next(r for r in records if r.record_type == "panaya_where_used")
            assert where_used.object_name == "ZPROGRAM_REPORT"  # correlates via INCLUDE, never NAME
            assert where_used.object_type is None  # OTYPE describes NAME's cross-ref kind, not INCLUDE's type
            assert where_used.normalized_payload["NAME"] == "ZCL_ORDER\\ME:METHOD\\DA:VAR"  # preserved as context only

            # Idempotent re-run.
            repo_batch = next(b for b in batches if b.batch_key == "REPOSITORY_OBJECTS")
            outcome_again = panaya.import_batch(xml_path, dataset, repo_batch, session)
            session.commit()
            assert outcome_again.records_imported == 0
        finally:
            _cleanup(session, asmnt_id)


def test_new_curated_sections_correlate_and_surface_in_clean_core_technical_pool(tmp_path: Path) -> None:
    """SPRINT-19 CAP-003 — SCI_HANA_ISSUES(_DETAILS)/WHERE_USED_TABLE must reach SAPObject
    correlation via the existing generic evidence.correlation pipeline (no new correlation logic)
    and surface, unmodified, in ai.clean_core_analysis.evidence_package's technical pool (both
    S4_CONVERSION_SIGNAL and DEPENDENCY_SIGNAL are already-recognized technical capabilities)."""
    from evidence.correlation import correlate_dataset_records
    from ai.clean_core_analysis.evidence_package import build_clean_core_evidence_package
    from persistence.models import Application, ScanStatus, SourceFile, SourceScan

    xml_path = _make_xml(tmp_path)
    inspection = panaya.inspect(xml_path)
    batches = panaya.plan_batches(xml_path, inspection)

    with get_session_factory()() as session:
        try:
            asmnt_id = _make_assessment(session)
            ds_id = _make_dataset(session, asmnt_id)
            dataset = session.get(EvidenceDataset, ds_id)
            for batch in batches:
                panaya.import_batch(xml_path, dataset, batch, session)
            session.commit()

            scan = SourceScan(assessment_id=asmnt_id, source_path="/tmp", status=ScanStatus.COMPLETED.value,
                               total_files=2, scanned_files=2)
            session.add(scan)
            session.flush()
            sf = SourceFile(scan_id=scan.id, assessment_id=asmnt_id, rel_path="x.abap", size_bytes=0,
                             mtime=0.0, sha256="a" * 64, category="abap_source")
            session.add(sf)
            session.flush()
            from persistence.models import SAPObject
            report_obj = SAPObject(assessment_id=asmnt_id, source_file_id=sf.id, object_type="report",
                                    object_name="ZPROGRAM_REPORT", canonical_key="REPORT::ZPROGRAM_REPORT",
                                    description="", line_start=1, attributes={})
            class_obj = SAPObject(assessment_id=asmnt_id, source_file_id=sf.id, object_type="class",
                                   object_name="ZCL_ORDER", canonical_key="CLASS::ZCL_ORDER",
                                   description="", line_start=1, attributes={})
            app = Application(assessment_id=asmnt_id, name="App")
            session.add_all([report_obj, class_obj, app])
            session.commit()

            correlate_dataset_records(ds_id, asmnt_id, session)
            session.commit()

            package = build_clean_core_evidence_package(session, app, [report_obj.id, class_obj.id])
            supplemental = [i for i in package.technical_items if i.source_type == "SUPPLEMENTAL_EVIDENCE"]
            record_types_seen = {s.split(" / ")[1].split(" (")[0] for s in (i.summary for i in supplemental)}
            assert {"panaya_sci_hana_issue", "panaya_sci_hana_issue_detail", "panaya_where_used"} <= record_types_seen
        finally:
            _cleanup(session, asmnt_id)


def test_sanitizing_stream_strips_illegal_control_bytes_and_charrefs() -> None:
    dirty = (
        b'<ROOT_ELEMENT><HEADER SYSTEM_ID="QAS" EXPORT_TOOL_VERSION="1"/>'
        b'<REPOSITORY_OBJECTS>'
        b'<TADIR OBJECT="CLAS" OBJ_NAME="ZCL_A" NOTE="bad\x1cbyte"/>'
        b'<TADIR OBJECT="CLAS" OBJ_NAME="ZCL_B" NOTE="bad&#0;ref"/>'
        b'</REPOSITORY_OBJECTS></ROOT_ELEMENT>'
    )
    import io
    stream = SanitizingXMLStream(io.BytesIO(dirty))
    cleaned = b""
    while chunk := stream.read(7):  # deliberately tiny chunks to exercise boundary handling
        cleaned += chunk
    assert b"\x1c" not in cleaned
    assert b"&#0;" not in cleaned
    assert b'NOTE="badbyte"' in cleaned
    assert b'NOTE="badref"' in cleaned


def test_import_survives_illegal_characters_in_real_style_data(tmp_path: Path) -> None:
    """A row containing the exact real-world illegal patterns (raw 0x1C, escaped &#0;) must
    still import — the surrounding well-formed structure is not corrupted by sanitization."""
    dirty_xml = _XML.replace(
        '<TADIR PGMID="R3TR" OBJECT="CLAS" OBJ_NAME="ZCL_ORDER" DEVCLASS="ZPKG" AUTHOR="DEV1" CREATED_ON="20200101"/>',
        '<TADIR PGMID="R3TR" OBJECT="CLAS" OBJ_NAME="ZCL_ORDER" DEVCLASS="ZPKG" AUTHOR="DEV1" '
        'CREATED_ON="20200101" GARBLED="bad&#0;ref"/>',
    )
    xml_path = tmp_path / "dirty.xml"
    xml_path.write_bytes(dirty_xml.encode("utf-8").replace(b"AUTHOR=\"DEV2\"", b"AUTHOR=\"DEV2\x1c\""))

    result = panaya.inspect(xml_path)
    assert result.warnings == []
    assert result.manifest["section_counts"]["REPOSITORY_OBJECTS"] == 2


# ---------------------------------------------------------------------------
# SPRINT-20 — Panaya usage/repository XLSX profile (ADR-017 amendment).
#
# A second, real, independently-verified Panaya export format: a flat XLSX "usage/repository"
# report (verified against a real ~143k-row customer export, `export T-systems.xlsx`) — one
# sheet, one header row, one row per SAP object, carrying a per-object usage level and origin no
# curated XML section above has. Detected by header-row signature, never filename or an
# exact-column-match requirement (only one real sample has been reviewed).
# ---------------------------------------------------------------------------

_USAGE_XLSX_HEADERS = [
    "OBJECT NAME", "OBJECT DESCRIPTION", "MODULE", "USAGE LEVEL", "PACKAGE",
    "OBJECT TYPE", "OBJECT SUB TYPE", "ORIGIN", "LAST USED", "LAST CHANGED BY",
]


def _make_usage_xlsx(
    tmp_path: Path, headers: list[str] | None = None, rows: list[list] | None = None, name: str = "export.xlsx",
) -> Path:
    import openpyxl as _openpyxl

    wb = _openpyxl.Workbook()
    ws = wb.active
    ws.append(headers if headers is not None else _USAGE_XLSX_HEADERS)
    for row in rows or []:
        ws.append(row)
    path = tmp_path / name
    wb.save(path)
    return path


_USAGE_SAMPLE_ROWS = [
    ["ZCL_ORDER", "Order handling", "Custom-Code", "Unused", "ZPKG", "Class", "", "Customer", "", "DEV1"],
    ["ZPROGRAM_REPORT", "", "Custom-Code", "Normally Used", "ZPKG", "Program", "", "Customer", "20-Jun-2026", "DEV2"],
    ["SAPMV45A", "Sales order", "SD", "Unknown", "", "Program", "", "SAP Standard", "", ""],
]


def test_detect_recognizes_usage_xlsx_regardless_of_filename(tmp_path: Path) -> None:
    path = _make_usage_xlsx(tmp_path, rows=_USAGE_SAMPLE_ROWS, name="export T-systems.xlsx")
    assert panaya.detect("export T-systems.xlsx", path)
    assert panaya.detect("anything_else.xlsx", path)  # content-sniffed, never filename-dependent


def test_detect_tolerates_reordered_and_extra_columns(tmp_path: Path) -> None:
    """Only one real sample has been reviewed — detection must key off the header *signature*,
    tolerant of column reordering and extra columns, never an exact-match requirement
    (ADR-016/ADR-017's shared principle)."""
    reordered = ["ORIGIN", "OBJECT TYPE", "EXTRA COLUMN", "USAGE LEVEL", "OBJECT NAME"]
    row = ["Customer", "Class", "unused info", "Unused", "ZCL_ORDER"]
    path = _make_usage_xlsx(tmp_path, headers=reordered, rows=[row])
    assert panaya.detect("whatever.xlsx", path)


def test_detect_rejects_unrelated_xlsx(tmp_path: Path) -> None:
    path = _make_usage_xlsx(tmp_path, headers=["Priority", "Check Title", "Object name"], rows=[[1, "x", "ZCL_A"]])
    assert not panaya.detect("atc_export.xlsx", path)


def test_inspect_usage_xlsx_counts_rows_and_distributions(tmp_path: Path) -> None:
    path = _make_usage_xlsx(tmp_path, rows=_USAGE_SAMPLE_ROWS)
    result = panaya.inspect(path)

    assert result.warnings == []
    assert set(result.capabilities) == {"TECHNICAL_OBJECT_METADATA", "USAGE_SIGNAL"}
    assert result.manifest["source_format"] == "xlsx_usage_report"
    assert result.manifest["row_count"] == 3
    assert result.manifest["usage_level_counts"] == {"Unused": 1, "Normally Used": 1, "Unknown": 1}
    assert result.manifest["origin_counts"] == {"Customer": 2, "SAP Standard": 1}
    # No system/client header metadata exists in this format — a real limitation, not guessed.
    assert result.source_system_hint is None
    assert result.source_client_hint is None


def test_import_usage_xlsx_persists_records_and_is_idempotent(tmp_path: Path) -> None:
    path = _make_usage_xlsx(tmp_path, rows=_USAGE_SAMPLE_ROWS)
    inspection = panaya.inspect(path)
    batches = panaya.plan_batches(path, inspection)
    assert len(batches) == 1  # 3 rows, well under the 20,000-row batch size

    with get_session_factory()() as session:
        try:
            asmnt_id = _make_assessment(session)
            ds_id = _make_dataset(session, asmnt_id)
            dataset = session.get(EvidenceDataset, ds_id)

            outcome = panaya.import_batch(path, dataset, batches[0], session)
            session.commit()
            assert outcome.records_imported == 3
            assert outcome.warnings == []

            records = {
                r.object_name: r
                for r in session.scalars(select(EvidenceRecord).where(EvidenceRecord.dataset_id == ds_id))
            }
            assert records.keys() == {"ZCL_ORDER", "ZPROGRAM_REPORT", "SAPMV45A"}
            unused = records["ZCL_ORDER"]
            assert unused.capability == "USAGE_SIGNAL"
            assert unused.record_type == "panaya_usage_object"
            assert unused.object_type == "Class"
            assert unused.package_name == "ZPKG"
            assert unused.normalized_payload["USAGE LEVEL"] == "Unused"
            assert unused.normalized_payload["ORIGIN"] == "Customer"
            assert "OBJECT DESCRIPTION" not in records["ZPROGRAM_REPORT"].normalized_payload or \
                records["ZPROGRAM_REPORT"].normalized_payload.get("OBJECT DESCRIPTION")  # blank cells omitted, never fabricated
            assert records["ZPROGRAM_REPORT"].normalized_payload["LAST USED"] == "20-Jun-2026"

            # Idempotent re-run.
            outcome_again = panaya.import_batch(path, dataset, batches[0], session)
            session.commit()
            assert outcome_again.records_imported == 0
        finally:
            _cleanup(session, asmnt_id)


def test_usage_xlsx_records_correlate_and_surface_in_clean_core_business_pool(tmp_path: Path) -> None:
    """SPRINT-20 CAP-003 — usage-level records must reach SAPObject correlation via the existing
    generic evidence.correlation pipeline (no new correlation logic) and surface, unmodified, in
    ai.clean_core_analysis.evidence_package's *business* pool (USAGE_SIGNAL is already a
    recognized business/PROCESS_USAGE_EVIDENCE capability)."""
    from evidence.correlation import correlate_dataset_records
    from ai.clean_core_analysis.evidence_package import build_clean_core_evidence_package
    from persistence.models import Application, SAPObject, ScanStatus, SourceFile, SourceScan

    path = _make_usage_xlsx(tmp_path, rows=_USAGE_SAMPLE_ROWS)
    inspection = panaya.inspect(path)
    batches = panaya.plan_batches(path, inspection)

    with get_session_factory()() as session:
        try:
            asmnt_id = _make_assessment(session)
            ds_id = _make_dataset(session, asmnt_id)
            dataset = session.get(EvidenceDataset, ds_id)
            for batch in batches:
                panaya.import_batch(path, dataset, batch, session)
            session.commit()

            scan = SourceScan(assessment_id=asmnt_id, source_path="/tmp", status=ScanStatus.COMPLETED.value,
                               total_files=1, scanned_files=1)
            session.add(scan)
            session.flush()
            sf = SourceFile(scan_id=scan.id, assessment_id=asmnt_id, rel_path="x.abap", size_bytes=0,
                             mtime=0.0, sha256="a" * 64, category="abap_source")
            session.add(sf)
            session.flush()
            order_obj = SAPObject(assessment_id=asmnt_id, source_file_id=sf.id, object_type="class",
                                   object_name="ZCL_ORDER", canonical_key="CLASS::ZCL_ORDER",
                                   description="", line_start=1, attributes={})
            app = Application(assessment_id=asmnt_id, name="App")
            session.add_all([order_obj, app])
            session.commit()

            correlate_dataset_records(ds_id, asmnt_id, session)
            session.commit()

            package = build_clean_core_evidence_package(session, app, [order_obj.id])
            business = [i for i in package.business_items if i.source_type == "PROCESS_USAGE_EVIDENCE"]
            record_types_seen = {s.split(" / ")[1].split(" (")[0] for s in (i.summary for i in business)}
            assert "panaya_usage_object" in record_types_seen
        finally:
            _cleanup(session, asmnt_id)
