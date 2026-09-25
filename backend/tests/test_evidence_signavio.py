"""SPRINT-08 CAP-005 — SAP Signavio Process Insights adapter, rewritten against a real export.

Fixture mirrors the real, verified structure: ABAP-serialized system metadata XML
(`<asx:abap>` / `<item><KEY>/<VALUE>`) plus chunked JSON where everything lives under a
`"dataSet"` key (`header`/`data`, not top-level `header`/`rows` as the original invented
profile assumed).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from sqlalchemy import select, text

from evidence.adapters import signavio
from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    EvidenceDataset,
    EvidenceDatasetStatus,
    EvidenceRecord,
)

_HEADER_XML = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<asx:abap version="1.0" xmlns:asx="http://www.sap.com/abapxml"><asx:values>'
    "<HEADER_DATA>"
    "<item><KEY>UsageSystem</KEY><VALUE>QAS</VALUE></item>"
    "<item><KEY>UsageSystemClient</KEY><VALUE>300</VALUE></item>"
    "<item><KEY>ScenarioName</KEY><VALUE>SAP Signavio Process Insights, discovery edition</VALUE></item>"
    "</HEADER_DATA>"
    "</asx:values></asx:abap>"
)


def _chunk(key_figure_id: str, rows: list[list[str]]) -> bytes:
    return json.dumps({
        "dataSet": {
            "serviceName": "QAS300", "serviceDescr": "QAS (QAS300)", "serviceType": "SAP_BS",
            "keyFigureId": key_figure_id, "timestamp": "20260819185452 ", "completed": "",
            "header": ["BELNR", "BUZEI", "VALUE"], "data": rows,
        }
    }).encode()


def _make_zip(tmp_path: Path, name: str = "signavio_export.zip") -> Path:
    zip_path = tmp_path / name
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("ana_sys_header.xml", _HEADER_XML)
        zf.writestr("ppi_kffi000202_00001.json", _chunk("KFFI000202", [["0400004156", "001", "42"]]))
        zf.writestr("ppi_kffi000302_00001.json", _chunk("KFFI000302", [["0400004200", "002", "17"], ["0400004201", "003", "5"]]))
    return zip_path


def _make_assessment(session) -> int:
    c = Client(name="Signavio Adapter Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Signavio Adapter Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _make_dataset(session, assessment_id: int) -> int:
    ds = EvidenceDataset(
        assessment_id=assessment_id, dataset_type=signavio.DATASET_TYPE,
        display_name="signavio_export.zip", source_filename="signavio_export.zip", source_sha256="b" * 64,
        source_size_bytes=10, importer_name="signavio", importer_version=signavio.IMPORTER_VERSION,
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
    signavio_zip = _make_zip(tmp_path)
    assert signavio.detect("Signavio_Discovery_2026.zip", signavio_zip)  # filename fast-path
    assert signavio.detect("export.zip", signavio_zip)  # content sniffing (dataSet / UsageSystem)

    other_zip = tmp_path / "other.zip"
    with zipfile.ZipFile(other_zip, "w") as zf:
        zf.writestr("data.json", json.dumps({"foo": "bar"}))
    assert not signavio.detect("other.zip", other_zip)


def test_inspect_reports_system_metadata_and_key_figures(tmp_path: Path) -> None:
    zip_path = _make_zip(tmp_path)
    result = signavio.inspect(zip_path)

    assert result.capabilities == ["PROCESS_KPI"]
    assert result.manifest["chunk_count"] == 2
    assert result.manifest["key_figure_ids"] == ["KFFI000202", "KFFI000302"]
    assert result.source_system_hint == "QAS"
    assert result.source_client_hint == "300"
    assert result.warnings == []


def test_inspect_missing_system_xml_is_a_readable_warning(tmp_path: Path) -> None:
    zip_path = tmp_path / "no_system.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("data/chunk.json", _chunk("KFFI000202", [["a", "b", "c"]]))
    result = signavio.inspect(zip_path)
    assert "No system metadata XML found" in result.warnings[0]
    assert result.capabilities == ["PROCESS_KPI"]


def test_inspect_flat_legacy_shape_is_reported_as_zero_capabilities(tmp_path: Path) -> None:
    """The originally-invented profile (top-level header/rows, no 'dataSet' wrapper) must
    not be silently mistaken for the real shape — it should read as zero key figures found,
    not crash and not falsely report PROCESS_KPI capability."""
    zip_path = tmp_path / "legacy_shape.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("ana_sys_header.xml", _HEADER_XML)
        zf.writestr("chunk.json", json.dumps({"keyFigureId": "KFFI1", "header": [], "rows": []}))
    result = signavio.inspect(zip_path)
    assert result.capabilities == []
    assert any("no chunk carried" in w.lower() for w in result.warnings)


def test_import_batches_preserve_key_figure_and_member_provenance(tmp_path: Path) -> None:
    zip_path = _make_zip(tmp_path)
    inspection = signavio.inspect(zip_path)
    batches = signavio.plan_batches(zip_path, inspection)
    assert len(batches) == 2

    with get_session_factory()() as session:
        try:
            asmnt_id = _make_assessment(session)
            ds_id = _make_dataset(session, asmnt_id)
            dataset = session.get(EvidenceDataset, ds_id)

            total_imported = 0
            for batch in batches:
                outcome = signavio.import_batch(zip_path, dataset, batch, session)
                total_imported += outcome.records_imported
            session.commit()
            assert total_imported == 3  # 1 row in KFFI000202 chunk + 2 rows in KFFI000302 chunk

            records = list(session.scalars(select(EvidenceRecord).where(EvidenceRecord.dataset_id == ds_id)))
            assert all(r.capability == "PROCESS_KPI" for r in records)
            kfi202 = [r for r in records if r.normalized_payload["key_figure_id"] == "KFFI000202"]
            assert len(kfi202) == 1
            assert kfi202[0].source_locator["member"] == "ppi_kffi000202_00001.json"
            assert kfi202[0].normalized_payload["service_name"] == "QAS300"
            assert kfi202[0].normalized_payload["row"] == ["0400004156", "001", "42"]

            # Idempotent re-run: re-importing the same batch adds nothing new.
            outcome_again = signavio.import_batch(zip_path, dataset, batches[0], session)
            session.commit()
            assert outcome_again.records_imported == 0
        finally:
            _cleanup(session, asmnt_id)


def test_import_batch_handles_a_chunk_past_the_postgres_bind_parameter_limit(tmp_path: Path) -> None:
    """Regression: a real Signavio chunk with ~9600 rows (x7 columns ~= 67k bind params)
    crashed a single-statement bulk insert with psycopg.OperationalError ("number of
    parameters must be between 0 and 65535") — the same class of failure
    `evidence.correlation.correlate_dataset_records` was fixed for earlier. 10k rows in one
    chunk here reliably exceeds the limit in a single statement."""
    zip_path = tmp_path / "large_chunk.zip"
    big_rows = [[f"BELNR{i:06d}", "001", str(i)] for i in range(10_000)]
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("ana_sys_header.xml", _HEADER_XML)
        zf.writestr("ppi_kffi000202_00001.json", _chunk("KFFI000202", big_rows))

    inspection = signavio.inspect(zip_path)
    batches = signavio.plan_batches(zip_path, inspection)
    assert len(batches) == 1

    with get_session_factory()() as session:
        try:
            asmnt_id = _make_assessment(session)
            ds_id = _make_dataset(session, asmnt_id)
            dataset = session.get(EvidenceDataset, ds_id)

            outcome = signavio.import_batch(zip_path, dataset, batches[0], session)
            session.commit()
            assert outcome.records_imported == 10_000

            total = len(list(session.scalars(select(EvidenceRecord).where(EvidenceRecord.dataset_id == ds_id))))
            assert total == 10_000
        finally:
            _cleanup(session, asmnt_id)
