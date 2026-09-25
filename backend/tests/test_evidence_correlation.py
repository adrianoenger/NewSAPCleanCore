"""SPRINT-08 CAP-003 — deterministic EvidenceRecord -> SAPObject correlation."""
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy import inspect as sa_inspect

import evidence.correlation as correlation_module
from evidence.correlation import correlate_dataset_records
from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    EvidenceCorrelation,
    EvidenceDataset,
    EvidenceDatasetStatus,
    EvidenceDatasetType,
    EvidenceRecord,
    SAPObject,
    ScanStatus,
    SourceFile,
    SourceScan,
)


def _cleanup(session, assessment_id: int) -> None:
    """Remove only the client owning this assessment — cascades to everything under
    it. Never a blanket table wipe against the shared dev database."""
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def _make_assessment(session) -> int:
    c = Client(name="Evidence Correlation Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Evidence Correlation Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _make_dataset(session, assessment_id: int) -> int:
    ds = EvidenceDataset(
        assessment_id=assessment_id, dataset_type=EvidenceDatasetType.OTHER.value,
        display_name="Test dataset", source_filename="x.zip", source_sha256="a" * 64,
        source_size_bytes=10, importer_name="test", status=EvidenceDatasetStatus.IMPORTED_FULL.value,
    )
    session.add(ds)
    session.flush()
    return ds.id


def _make_source_file(session, assessment_id: int) -> int:
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
    return sf.id


def _make_object(session, assessment_id: int, source_file_id: int, object_type: str, object_name: str) -> int:
    obj = SAPObject(
        assessment_id=assessment_id, source_file_id=source_file_id, object_type=object_type,
        object_name=object_name, canonical_key=f"{object_type.upper()}::{object_name.upper()}",
        description="", line_start=1, attributes={},
    )
    session.add(obj)
    session.flush()
    return obj.id


def _make_record(session, dataset_id: int, source_key: str, object_name: str | None, object_type: str | None) -> int:
    rec = EvidenceRecord(
        dataset_id=dataset_id, record_type="usage_signal", capability="USAGE_SIGNAL",
        source_key=source_key, record_fingerprint=source_key, object_name=object_name,
        object_type=object_type, normalized_payload={}, source_locator={"key": source_key},
    )
    session.add(rec)
    session.flush()
    return rec.id


def test_correlate_exact_heuristic_unmatched_and_ambiguous() -> None:
    with get_session_factory()() as session:
        try:
            asmnt_id = _make_assessment(session)
            ds_id = _make_dataset(session, asmnt_id)
            sf_id = _make_source_file(session, asmnt_id)

            exact_id = _make_object(session, asmnt_id, sf_id, "class", "ZCL_EXACT")
            heuristic_id = _make_object(session, asmnt_id, sf_id, "class", "ZCL_HEUR")
            _make_object(session, asmnt_id, sf_id, "report", "ZCL_DUP")
            _make_object(session, asmnt_id, sf_id, "class", "ZCL_DUP")
            session.commit()

            rec_exact = _make_record(session, ds_id, "k1", "ZCL_EXACT", "CLASS")
            rec_heuristic = _make_record(session, ds_id, "k2", "ZCL_HEUR", "REPORT")  # type mismatch -> name-only
            rec_unmatched = _make_record(session, ds_id, "k3", "ZCL_MISSING", None)
            rec_ambiguous = _make_record(session, ds_id, "k4", "ZCL_DUP", None)
            rec_na = _make_record(session, ds_id, "k5", None, None)
            session.commit()

            summary = correlate_dataset_records(ds_id, asmnt_id, session)
            session.commit()

            def _status_target(rec_id: int) -> tuple[str, int | None]:
                corr = session.scalars(
                    select(EvidenceCorrelation).where(EvidenceCorrelation.evidence_record_id == rec_id)
                ).one()
                return corr.status, corr.target_id

            assert _status_target(rec_exact) == ("MATCHED_EXACT", exact_id)
            assert _status_target(rec_heuristic) == ("MATCHED_HEURISTIC", heuristic_id)
            assert _status_target(rec_unmatched) == ("UNMATCHED", None)
            assert _status_target(rec_ambiguous) == ("AMBIGUOUS", None)
            assert _status_target(rec_na) == ("NOT_APPLICABLE", None)
            assert summary["MATCHED_EXACT"] == 1
            assert summary["MATCHED_HEURISTIC"] == 1
            assert summary["UNMATCHED"] == 1
            assert summary["AMBIGUOUS"] == 1
            assert summary["NOT_APPLICABLE"] == 1

            # Idempotent re-run: no duplicate correlation rows accumulate.
            correlate_dataset_records(ds_id, asmnt_id, session)
            session.commit()
            all_for_exact = list(
                session.scalars(select(EvidenceCorrelation).where(EvidenceCorrelation.evidence_record_id == rec_exact))
            )
            assert len(all_for_exact) == 1
        finally:
            _cleanup(session, asmnt_id)


def test_correlate_paginates_without_detaching_caller_owned_objects(monkeypatch) -> None:
    """Regression: a real Signavio import with 4M+ records for one dataset pushed the backend
    container to ~20GB RSS (every EvidenceRecord loaded as an ORM object at once). Fixed with
    id-ordered pagination — verified here across a forced 3-row page size spanning 3 pages.
    Also regression for the fix's own footgun: pagination used to `session.expunge_all()`,
    which would silently detach whatever *other* objects the caller still holds in the same
    session (e.g. `_evidence_import_finalize`'s `dataset`) — their later attribute changes
    would then never be flushed/committed. Only this function's own per-page EvidenceRecord
    objects must be expunged."""
    monkeypatch.setattr(correlation_module, "_PAGE_SIZE", 3)

    with get_session_factory()() as session:
        try:
            asmnt_id = _make_assessment(session)
            ds_id = _make_dataset(session, asmnt_id)
            dataset = session.get(EvidenceDataset, ds_id)  # caller-owned object, held across the call

            record_ids = [_make_record(session, ds_id, f"k{i}", None, None) for i in range(7)]
            session.commit()

            summary = correlate_dataset_records(ds_id, asmnt_id, session)
            assert summary["NOT_APPLICABLE"] == 7

            correlations = list(
                session.scalars(
                    select(EvidenceCorrelation).where(EvidenceCorrelation.evidence_record_id.in_(record_ids))
                )
            )
            assert len(correlations) == 7

            assert not sa_inspect(dataset).detached
            dataset.error = "still usable after correlate_dataset_records"
            session.commit()
            assert session.get(EvidenceDataset, ds_id).error == "still usable after correlate_dataset_records"
        finally:
            _cleanup(session, asmnt_id)
