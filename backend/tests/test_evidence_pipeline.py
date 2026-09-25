"""SPRINT-08 CAP-007 — evidence import as a durable, resumable pipeline run
(same PipelineRun/StageRun/WorkItem engine as source processing, ADR-005/ADR-017)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select, text

from evidence.adapters import panaya
from evidence.correlation import correlate_dataset_records
from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    EvidenceCorrelation,
    EvidenceDataset,
    EvidenceDatasetStatus,
    EvidenceRecord,
    PipelineRun,
    SAPObject,
    ScanStatus,
    SourceFile,
    SourceScan,
)
from pipeline.engine import create_pipeline_run, run_pipeline
from settings import get_settings

_XML = """<?xml version="1.0"?>
<ROOT_ELEMENT>
<HEADER SYSTEM_ID="QAS" CLIENT="300" EXPORT_TOOL_VERSION="26.07.15.10_200"/>
<REPOSITORY_OBJECTS>
<TADIR PGMID="R3TR" OBJECT="CLAS" OBJ_NAME="ZCL_ORDER" DEVCLASS="ZPKG" AUTHOR="DEV1" CREATED_ON="20200101"/>
</REPOSITORY_OBJECTS>
</ROOT_ELEMENT>
"""


def _cleanup(session, assessment_id: int) -> None:
    """Remove only the client owning this assessment — cascades to everything under
    it. Never a blanket table wipe against the shared dev database."""
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def _make_assessment(session) -> int:
    c = Client(name="Evidence Pipeline Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Evidence Pipeline Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def test_evidence_import_run_completes_and_correlates(tmp_path: Path) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

        # A pre-existing SAPObject so correlation has something to match exactly.
        scan = SourceScan(
            assessment_id=asmnt_id, source_path="/tmp", status=ScanStatus.COMPLETED.value,
            total_files=1, scanned_files=1,
        )
        session.add(scan)
        session.flush()
        sf = SourceFile(
            scan_id=scan.id, assessment_id=asmnt_id, rel_path="x.abap",
            size_bytes=0, mtime=0.0, sha256="a" * 64, category="abap_source",
        )
        session.add(sf)
        session.flush()
        obj = SAPObject(
            assessment_id=asmnt_id, source_file_id=sf.id, object_type="CLAS", object_name="ZCL_ORDER",
            canonical_key="CLAS::ZCL_ORDER", description="", line_start=1, attributes={},
        )
        session.add(obj)
        session.flush()
        sap_object_id = obj.id

        dataset = EvidenceDataset(
            assessment_id=asmnt_id, dataset_type=panaya.DATASET_TYPE, display_name="ETL_QAS.xml",
            source_filename="ETL_QAS.xml", source_sha256="d" * 64, source_size_bytes=10,
            importer_name="panaya", importer_version=panaya.IMPORTER_VERSION,
            status=EvidenceDatasetStatus.INSPECTED.value,
        )
        session.add(dataset)
        session.commit()
        dataset_id = dataset.id

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            xml_path = Path(tmp) / "ETL_QAS.xml"
            xml_path.write_text(_XML)

            with get_session_factory()() as session:
                run = create_pipeline_run(
                    session, asmnt_id, str(xml_path), kind="evidence_import", evidence_dataset_id=dataset_id,
                )
                run_id = run.id
                assert run.kind == "evidence_import"
                assert run.evidence_dataset_id == dataset_id

            run_pipeline(run_id, settings.database_url)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"

                dataset = session.get(EvidenceDataset, dataset_id)
                assert dataset.status == EvidenceDatasetStatus.IMPORTED_FULL.value
                assert "TECHNICAL_OBJECT_METADATA" in dataset.capabilities
                assert dataset.extracted_at is not None

                records = list(session.scalars(select(EvidenceRecord).where(EvidenceRecord.dataset_id == dataset_id)))
                assert len(records) == 1  # one REPOSITORY_OBJECTS row

                tech_record = records[0]
                assert tech_record.record_type == "panaya_repository_object"
                corr = session.scalars(
                    select(EvidenceCorrelation).where(EvidenceCorrelation.evidence_record_id == tech_record.id)
                ).one()
                assert corr.status == "MATCHED_EXACT"
                assert corr.target_id == sap_object_id
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_evidence_import_prepare_failure_marks_dataset_failed_not_stuck(tmp_path: Path, monkeypatch) -> None:
    """Regression: a real user hit "processing forever" on a Panaya ZIP whose entry used a
    compression method the stdlib `zipfile` can't decode (WinZip AES encryption, etc. — a
    real, not-uncommon export limitation). `adapter.inspect()` used to raise `RuntimeError`
    uncaught inside `prepare`, which `_run_stage` handles by returning "failed" *without*
    ever calling `finalize` — so `dataset.status` stayed stuck at INSPECTED forever even
    though the PipelineRun/StageRun correctly showed "failed". Simulated here via monkeypatch
    since stdlib `zipfile` cannot itself construct an AES-encrypted archive to reproduce
    against; the adapter's own except clause must catch this class of error regardless of
    which unsupported-compression variant a real export triggers."""
    def _raise_unsupported(*args, **kwargs):
        raise NotImplementedError("compression type 99")

    monkeypatch.setattr(panaya, "_open_xml_stream", _raise_unsupported)

    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        dataset = EvidenceDataset(
            assessment_id=asmnt_id, dataset_type=panaya.DATASET_TYPE, display_name="encrypted.xml",
            source_filename="encrypted.xml", source_sha256="e" * 64, source_size_bytes=10,
            importer_name="panaya", importer_version=panaya.IMPORTER_VERSION,
            status=EvidenceDatasetStatus.INSPECTED.value,
        )
        session.add(dataset)
        session.commit()
        dataset_id = dataset.id

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            xml_path = Path(tmp) / "encrypted.xml"
            xml_path.write_text(_XML)

            with get_session_factory()() as session:
                run = create_pipeline_run(
                    session, asmnt_id, str(xml_path), kind="evidence_import", evidence_dataset_id=dataset_id,
                )
                run_id = run.id
            run_pipeline(run_id, settings.database_url)

            with get_session_factory()() as session:
                dataset = session.get(EvidenceDataset, dataset_id)
                # The adapter itself now catches this and reports a clean warning instead of
                # crashing — a readable-but-undecodable package is IMPORTED_PARTIAL, not FAILED.
                assert dataset.status == EvidenceDatasetStatus.IMPORTED_PARTIAL.value
                assert dataset.warning_summary
                assert any("compression" in w for w in dataset.warning_summary)

                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_evidence_import_prepare_exception_marks_dataset_failed(tmp_path: Path) -> None:
    """Direct unit test of the safety net itself: if a prepare-time exception slips past
    the adapter's own handling for any reason, the dataset must end up FAILED with the
    error recorded — never stuck at INSPECTED/IMPORTING. An unregistered dataset_type raises
    inside `_evidence_import_prepare` itself, before any adapter function is even called —
    a case no adapter's own try/except could ever cover."""
    from pipeline.stages import _evidence_import_prepare
    from persistence.models import StageRun

    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        dataset = EvidenceDataset(
            assessment_id=asmnt_id, dataset_type="NOT_A_REGISTERED_ADAPTER", display_name="missing.xml",
            source_filename="missing.xml", source_sha256="f" * 64, source_size_bytes=10,
            importer_name="unknown", status=EvidenceDatasetStatus.INSPECTED.value,
        )
        session.add(dataset)
        session.commit()
        dataset_id = dataset.id

    try:
        with get_session_factory()() as session:
            run = create_pipeline_run(
                session, asmnt_id, str(Path(settings.scan_root) / "does-not-exist.xml"),
                kind="evidence_import", evidence_dataset_id=dataset_id,
            )
            stage = session.scalars(select(StageRun).where(StageRun.pipeline_run_id == run.id)).one()

            raised = False
            try:
                _evidence_import_prepare(stage, run, session)
            except ValueError:
                raised = True
            assert raised

            dataset = session.get(EvidenceDataset, dataset_id)
            assert dataset.status == EvidenceDatasetStatus.FAILED.value
            assert dataset.error
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_reprocessing_source_recorrelates_existing_evidence_datasets(tmp_path: Path) -> None:
    """SPRINT-08 post-completion: `EvidenceCorrelation.target_id` has no DB-level FK (it is a
    polymorphic column, pointing at SAPObject today and possibly other entity types later), so
    removing a SAPObject during parse reconciliation must not leave a dangling correlation, and
    adding one must retroactively match evidence imported before it existed. `_parse_finalize`
    now re-runs `correlate_dataset_records` for every evidence dataset of the assessment right
    after reconciling SAPObjects — no manual re-import of the evidence dataset required."""
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            source_file = Path(tmp) / "ab.abap"
            source_file.write_text("CLASS ZCL_A DEFINITION.\nENDCLASS.\nCLASS ZCL_B DEFINITION.\nENDCLASS.\n")

            with get_session_factory()() as session:
                run1 = create_pipeline_run(session, asmnt_id, tmp)
                run1_id = run1.id
            run_pipeline(run1_id, settings.database_url)

            with get_session_factory()() as session:
                dataset = EvidenceDataset(
                    assessment_id=asmnt_id, dataset_type="OTHER", display_name="usage.csv",
                    source_filename="usage.csv", source_sha256="a" * 64, source_size_bytes=1,
                    importer_name="test", status=EvidenceDatasetStatus.IMPORTED_FULL.value,
                )
                session.add(dataset)
                session.flush()
                dataset_id = dataset.id
                rec_b = EvidenceRecord(
                    dataset_id=dataset_id, record_type="usage_signal", capability="USAGE_SIGNAL",
                    source_key="k-b", record_fingerprint="k-b", object_name="ZCL_B", object_type="CLASS",
                    normalized_payload={}, source_locator={},
                )
                rec_c = EvidenceRecord(
                    dataset_id=dataset_id, record_type="usage_signal", capability="USAGE_SIGNAL",
                    source_key="k-c", record_fingerprint="k-c", object_name="ZCL_C", object_type="CLASS",
                    normalized_payload={}, source_locator={},
                )
                session.add_all([rec_b, rec_c])
                session.commit()
                rec_b_id, rec_c_id = rec_b.id, rec_c.id

                correlate_dataset_records(dataset_id, asmnt_id, session)
                session.commit()

            def _status(session, rec_id: int) -> str:
                return session.scalars(
                    select(EvidenceCorrelation).where(EvidenceCorrelation.evidence_record_id == rec_id)
                ).one().status

            with get_session_factory()() as session:
                assert _status(session, rec_b_id) == "MATCHED_EXACT"  # ZCL_B exists at import time
                assert _status(session, rec_c_id) == "UNMATCHED"  # ZCL_C does not exist yet

            # ZCL_B is removed from the source, ZCL_C is added — reprocess.
            source_file.write_text("CLASS ZCL_A DEFINITION.\nENDCLASS.\nCLASS ZCL_C DEFINITION.\nENDCLASS.\n")

            with get_session_factory()() as session:
                run2 = create_pipeline_run(session, asmnt_id, tmp)
                run2_id = run2.id
            run_pipeline(run2_id, settings.database_url)

            with get_session_factory()() as session:
                # ZCL_B's SAPObject was removed by reconciliation — the old MATCHED_EXACT
                # correlation was replaced with a fresh UNMATCHED, never left dangling.
                assert _status(session, rec_b_id) == "UNMATCHED"
                # ZCL_C now exists — a record imported before the object existed is
                # retroactively matched once the source is reprocessed, with no manual action.
                assert _status(session, rec_c_id) == "MATCHED_EXACT"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_parse_finalize_recorrelation_failure_does_not_lose_reconciliation(
    tmp_path: Path, monkeypatch
) -> None:
    """Safety net for the new re-correlation loop in `_parse_finalize`: `_run_stage` has no
    try/except around its call to `finalize`, so an uncaught exception there would propagate
    out of the background task silently, losing even the stale-object reconciliation that ran
    just before it (never committed) — the same "stuck forever" family of bugs already fixed
    for `_evidence_import_finalize`."""
    import pipeline.stages as stages_module

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated re-correlation failure")

    monkeypatch.setattr(stages_module, "correlate_dataset_records", _raise)

    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        dataset = EvidenceDataset(
            assessment_id=asmnt_id, dataset_type="OTHER", display_name="usage.csv",
            source_filename="usage.csv", source_sha256="b" * 64, source_size_bytes=1,
            importer_name="test", status=EvidenceDatasetStatus.IMPORTED_FULL.value,
        )
        session.add(dataset)
        session.commit()
        dataset_id = dataset.id

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            source_file = Path(tmp) / "ab.abap"
            source_file.write_text("CLASS ZCL_A DEFINITION.\nENDCLASS.\nCLASS ZCL_B DEFINITION.\nENDCLASS.\n")

            with get_session_factory()() as session:
                run1 = create_pipeline_run(session, asmnt_id, tmp)
                run1_id = run1.id
            run_pipeline(run1_id, settings.database_url)  # must not raise despite the simulated crash

            with get_session_factory()() as session:
                run1_after = session.get(PipelineRun, run1_id)
                assert run1_after.status == "completed"

                objs = list(session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)))
                assert {o.object_name for o in objs} == {"ZCL_A", "ZCL_B"}  # not lost despite the crash

                dataset = session.get(EvidenceDataset, dataset_id)
                assert dataset.status == EvidenceDatasetStatus.FAILED.value
                assert "Re-correlation" in dataset.error
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_evidence_import_finalize_correlation_failure_does_not_leave_dataset_stuck(
    tmp_path: Path, monkeypatch
) -> None:
    """Regression: a real ~180k-record Panaya import crashed inside
    `correlate_dataset_records` (a >65535-bind-parameter query — since fixed to use a
    subquery instead of an id-list `IN`). `_run_stage` has no try/except around its call to
    `finalize`, so an uncaught exception there propagates out of `run_pipeline` (silently
    swallowed as a FastAPI BackgroundTask) with the dataset.status change still uncommitted —
    the same "stuck forever" failure mode as a `prepare`-time crash. `_evidence_import_finalize`
    must catch a correlation failure and still leave the dataset in a terminal, visible state."""
    import pipeline.stages as stages_module

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated correlation failure")

    # `stages.py` does `from evidence.correlation import correlate_dataset_records`, binding
    # its own name — patching the origin module's attribute would not affect that binding.
    monkeypatch.setattr(stages_module, "correlate_dataset_records", _raise)

    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        dataset = EvidenceDataset(
            assessment_id=asmnt_id, dataset_type=panaya.DATASET_TYPE, display_name="ETL_QAS.xml",
            source_filename="ETL_QAS.xml", source_sha256="d" * 64, source_size_bytes=10,
            importer_name="panaya", importer_version=panaya.IMPORTER_VERSION,
            status=EvidenceDatasetStatus.INSPECTED.value,
        )
        session.add(dataset)
        session.commit()
        dataset_id = dataset.id

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            xml_path = Path(tmp) / "ETL_QAS.xml"
            xml_path.write_text(_XML)

            with get_session_factory()() as session:
                run = create_pipeline_run(
                    session, asmnt_id, str(xml_path), kind="evidence_import", evidence_dataset_id=dataset_id,
                )
                run_id = run.id
            run_pipeline(run_id, settings.database_url)  # must not raise despite the simulated crash

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"

                dataset = session.get(EvidenceDataset, dataset_id)
                assert dataset.status == EvidenceDatasetStatus.IMPORTED_PARTIAL.value
                assert any("Correlation failed" in w for w in dataset.warning_summary)
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
