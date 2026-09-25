"""SPRINT-08 (post-completion extension) — HANA Sizing Report adapter."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select, text

from evidence.adapters import hana_sizing
from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    EvidenceDataset,
    EvidenceDatasetStatus,
    EvidenceRecord,
)

_SAMPLE = """
--------------------------------------------------------------------------------
| SIZING RESULTS IN GiB                                                        |
|------------------------------------------------------------------------------|
| The anticipated maximum requirements for the HANA DATABASE SERVER are:       |
|                                                                              |
| - Memory requirement                                                 3.765,0 |
| - Net data volume size on disk                                       8.578,8 |
--------------------------------------------------------------------------------

 SID                                                                       QAS
 NW release:                                                         731 SP 14

--------------------------------------------------------------------------------
|   LARGEST COLUMN              ESTIMATED MEMORY              ESTIMATED RECORD |
|   LOADABLE TABLES               SIZE IN GiB                      COUNT       |
|------------------------------------------------------------------------------|
| DBTABLOG                                230,0                   651.620.305  |
| ACDOCA                                   77,6                 1.699.689.986  |
--------------------------------------------------------------------------------
"""


def _make_txt(tmp_path: Path, content: str = _SAMPLE, name: str = "HANA_SIZING_QAS.TXT") -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def _make_assessment(session) -> int:
    c = Client(name="HANA Sizing Adapter Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="HANA Sizing Adapter Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _make_dataset(session, assessment_id: int) -> int:
    ds = EvidenceDataset(
        assessment_id=assessment_id, dataset_type=hana_sizing.DATASET_TYPE,
        display_name="HANA_SIZING_QAS.TXT", source_filename="HANA_SIZING_QAS.TXT",
        source_sha256="a" * 64, source_size_bytes=10, importer_name="hana_sizing",
        importer_version=hana_sizing.IMPORTER_VERSION, status=EvidenceDatasetStatus.IMPORTING.value,
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
    txt_path = _make_txt(tmp_path)
    assert hana_sizing.detect("HANA_SIZING_QAS0000093517.TXT", txt_path)  # filename fast-path
    assert hana_sizing.detect("export.txt", txt_path)  # content sniffing
    assert not hana_sizing.detect("export.docx", txt_path)  # wrong extension

    other = tmp_path / "other.txt"
    other.write_text("just some random text file, nothing to do with sizing")
    assert not hana_sizing.detect("other.txt", other)


def test_inspect_extracts_metadata_and_box_counts(tmp_path: Path) -> None:
    txt_path = _make_txt(tmp_path)
    result = hana_sizing.inspect(txt_path)

    assert result.capabilities == ["USAGE_SIGNAL"]
    assert result.manifest["box_count"] == 2
    assert result.manifest["table_metric_rows"] == 2  # DBTABLOG, ACDOCA
    assert result.manifest["metric_rows"] == 2  # Memory requirement, Net data volume
    assert result.manifest["metadata"]["SID"] == "QAS"
    assert result.source_system_hint == "QAS"


def test_import_batch_persists_table_metrics_and_dataset_metrics(tmp_path: Path) -> None:
    txt_path = _make_txt(tmp_path)
    inspection = hana_sizing.inspect(txt_path)
    batches = hana_sizing.plan_batches(txt_path, inspection)
    assert len(batches) == 1

    with get_session_factory()() as session:
        try:
            asmnt_id = _make_assessment(session)
            ds_id = _make_dataset(session, asmnt_id)
            dataset = session.get(EvidenceDataset, ds_id)

            outcome = hana_sizing.import_batch(txt_path, dataset, batches[0], session)
            session.commit()
            assert outcome.records_imported == 4

            records = list(session.scalars(select(EvidenceRecord).where(EvidenceRecord.dataset_id == ds_id)))
            table_records = [r for r in records if r.record_type == "hana_sizing_table_metric"]
            assert {r.object_name for r in table_records} == {"DBTABLOG", "ACDOCA"}
            dbtablog = next(r for r in table_records if r.object_name == "DBTABLOG")
            assert dbtablog.normalized_payload["values"][0]["parsed"] == 230.0
            assert dbtablog.normalized_payload["values"][1]["parsed"] == 651620305.0

            metric_records = [r for r in records if r.record_type == "hana_sizing_metric"]
            assert len(metric_records) == 2
            assert all(r.object_name is None for r in metric_records)

            # Idempotent re-run.
            outcome_again = hana_sizing.import_batch(txt_path, dataset, batches[0], session)
            session.commit()
            assert outcome_again.records_imported == 0
        finally:
            _cleanup(session, asmnt_id)


def test_inspect_non_sizing_file_is_readable_not_crashing(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("nothing here")
    result = hana_sizing.inspect(path)
    assert result.capabilities == []
    assert "No recognized sizing-report boxes" in result.warnings[0]
