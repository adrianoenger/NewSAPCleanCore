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
    assert result.manifest["section_counts"]["UNRECOGNIZED_SECTION"] == 1  # counted, not dropped silently
    assert set(result.capabilities) == {"TECHNICAL_OBJECT_METADATA", "SOURCE_CODE", "S4_CONVERSION_SIGNAL"}
    assert result.source_system_hint == "QAS"
    assert result.source_client_hint == "300"


def test_import_persists_curated_sections_with_correlatable_object_names(tmp_path: Path) -> None:
    xml_path = _make_xml(tmp_path)
    inspection = panaya.inspect(xml_path)
    batches = panaya.plan_batches(xml_path, inspection)
    assert {b.batch_key for b in batches} == {
        "REPOSITORY_OBJECTS", "PROGRAMS", "FUNCTIONS", "MODIFICATIONS", "NOTES_HEADER",
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
            assert total == 6  # 2 repo objects + 1 program + 1 function + 1 modification + 1 note

            records = list(session.scalars(select(EvidenceRecord).where(EvidenceRecord.dataset_id == ds_id)))
            repo_objects = {r.object_name: r.object_type for r in records if r.record_type == "panaya_repository_object"}
            assert repo_objects == {"ZCL_ORDER": "CLAS", "ZPROGRAM_REPORT": "PROG"}

            program = next(r for r in records if r.record_type == "panaya_program")
            assert program.object_name == "ZPROGRAM_REPORT"

            note = next(r for r in records if r.record_type == "panaya_sap_note")
            assert note.object_name is None  # SAP Notes don't correlate to a SAPObject by name
            assert note.normalized_payload["NUMM"] == "0000012345"

            # Idempotent re-run.
            repo_batch = next(b for b in batches if b.batch_key == "REPOSITORY_OBJECTS")
            outcome_again = panaya.import_batch(xml_path, dataset, repo_batch, session)
            session.commit()
            assert outcome_again.records_imported == 0
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
