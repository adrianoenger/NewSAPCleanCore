"""SPRINT-08 — Supplemental Evidence Foundation: stable SAPObject identity tests.

CAP-001 only (evidence dataset/adapter tests live in their own test modules as
those capabilities land).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select, text

from persistence.database import get_session_factory
from persistence.models import (
    ATCFinding,
    ATCRun,
    ATCRunStatus,
    Assessment,
    AssessmentStatus,
    Client,
    SAPObject,
)
from pipeline.engine import create_pipeline_run, run_pipeline
from pipeline.stages import canonical_object_key
from settings import get_settings

_CLASS_A = "CLASS ZCL_A DEFINITION.\nENDCLASS.\n"
_CLASS_B = "CLASS ZCL_B DEFINITION.\nENDCLASS.\n"


def _make_assessment(session) -> int:
    c = Client(name="Sprint08 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint08 Test", status=AssessmentStatus.CREATED.value)
    session.add(a)
    session.commit()
    return a.id


def _cleanup(session, assessment_id: int) -> None:
    """Remove only the client owning this assessment — cascades to everything under
    it. Never a blanket table wipe against the shared dev database."""
    session.execute(
        text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
        {"aid": assessment_id},
    )
    session.commit()


def test_canonical_object_key_is_normalized() -> None:
    assert canonical_object_key("class", "zcl_order") == canonical_object_key("CLASS", "ZCL_ORDER")
    assert canonical_object_key("class", "zcl_order") != canonical_object_key("report", "zcl_order")


def test_reprocessing_preserves_object_id_and_atc_correlation() -> None:
    """Re-running the parse stage for the same object must upsert, not delete/recreate,
    so an existing ATC correlation to that object survives (ADR-017 / BL-004)."""
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text(_CLASS_A)

            with get_session_factory()() as session:
                run1 = create_pipeline_run(session, asmnt_id, tmp)
                run1_id = run1.id
            run_pipeline(run1_id, settings.database_url)

            with get_session_factory()() as session:
                obj = session.scalars(
                    select(SAPObject).where(SAPObject.assessment_id == asmnt_id)
                ).one()
                original_id = obj.id

                atc_run = ATCRun(
                    assessment_id=asmnt_id, source_filename="x.xlsx",
                    validation_status=ATCRunStatus.ACCEPTED_FULL.value,
                )
                session.add(atc_run)
                session.flush()
                finding = ATCFinding(
                    atc_run_id=atc_run.id, assessment_id=asmnt_id, source_row_number=2,
                    raw_payload={}, object_name_raw="ZCL_A",
                    correlation_status="MATCHED_EXACT", correlated_object_id=original_id,
                )
                session.add(finding)
                session.commit()
                finding_id = finding.id

            # Reprocess the same directory — a second PipelineRun reuses the same
            # SourceScan (SPRINT-07) but gets its own parse StageRun.
            with get_session_factory()() as session:
                run2 = create_pipeline_run(session, asmnt_id, tmp)
                run2_id = run2.id
            run_pipeline(run2_id, settings.database_url)

            with get_session_factory()() as session:
                objs = list(session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)))
                assert len(objs) == 1
                assert objs[0].id == original_id  # same row — no delete/recreate

                refreshed_finding = session.get(ATCFinding, finding_id)
                assert refreshed_finding.correlated_object_id == original_id  # correlation survived
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_object_removed_from_source_is_reconciled_after_reprocessing() -> None:
    """An object no longer produced by any file in the scan is removed once the parse
    stage finishes; an object that is still present keeps its stable id."""
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            source_file = Path(tmp) / "ab.abap"
            source_file.write_text(_CLASS_A + _CLASS_B)

            with get_session_factory()() as session:
                run1 = create_pipeline_run(session, asmnt_id, tmp)
                run1_id = run1.id
            run_pipeline(run1_id, settings.database_url)

            with get_session_factory()() as session:
                objs = {
                    o.object_name: o.id
                    for o in session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id))
                }
                assert set(objs) == {"ZCL_A", "ZCL_B"}
                a_id = objs["ZCL_A"]

            # ZCL_B is removed from the source file entirely.
            source_file.write_text(_CLASS_A)

            with get_session_factory()() as session:
                run2 = create_pipeline_run(session, asmnt_id, tmp)
                run2_id = run2.id
            run_pipeline(run2_id, settings.database_url)

            with get_session_factory()() as session:
                objs = list(session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)))
                assert {o.object_name for o in objs} == {"ZCL_A"}
                assert objs[0].id == a_id  # ZCL_A kept its stable identity
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
