"""SPRINT-07 — Consolidate Processing Flow: scan reuse, processing status, and

Step-3 scoping (list_objects invalidation) tests.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, text

from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    PipelineRun,
    ScanStatus,
    SourceFile,
    SourceScan,
    StageRun,
    WorkItem,
)
from pipeline.engine import _run_stage, create_pipeline_run, run_pipeline
from pipeline.status import compute_processing_status
from settings import get_settings


def _make_assessment(session) -> int:
    c = Client(name="Sprint07 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint07 Test", status=AssessmentStatus.CREATED.value)
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


# ---------------------------------------------------------------------------
# Idempotent scan stage: reuse Step 1's ingestion instead of re-walking disk
# ---------------------------------------------------------------------------


def test_second_pipeline_run_reuses_completed_scan_without_rescanning() -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            with get_session_factory()() as session:
                run1 = create_pipeline_run(session, asmnt_id, tmp)
                run1_id = run1.id
            run_pipeline(run1_id, settings.database_url)

            with get_session_factory()() as session:
                run1 = session.get(PipelineRun, run1_id)
                assert run1.status == "completed"
                scan1_id = run1.source_scan_id
                scan_count_before = session.scalar(
                    select(func.count()).select_from(SourceScan).where(SourceScan.assessment_id == asmnt_id)
                )
                file_count_before = session.scalar(
                    select(func.count()).select_from(SourceFile).where(SourceFile.assessment_id == asmnt_id)
                )

            with get_session_factory()() as session:
                run2 = create_pipeline_run(session, asmnt_id, tmp)
                run2_id = run2.id
            run_pipeline(run2_id, settings.database_url)

            with get_session_factory()() as session:
                run2 = session.get(PipelineRun, run2_id)
                assert run2.status == "completed"
                assert run2.source_scan_id == scan1_id  # reused, not a fresh scan

                scan_stage = session.scalars(
                    select(StageRun).where(StageRun.pipeline_run_id == run2_id, StageRun.stage_key == "scan")
                ).first()
                assert scan_stage.status == "completed"
                work_items = session.scalar(
                    select(func.count()).select_from(WorkItem).where(WorkItem.stage_run_id == scan_stage.id)
                )
                assert work_items == 0  # no physical re-scan performed

                scan_count_after = session.scalar(
                    select(func.count()).select_from(SourceScan).where(SourceScan.assessment_id == asmnt_id)
                )
                file_count_after = session.scalar(
                    select(func.count()).select_from(SourceFile).where(SourceFile.assessment_id == asmnt_id)
                )
                assert scan_count_after == scan_count_before
                assert file_count_after == file_count_before
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# compute_processing_status: current scan + staleness derivation
# ---------------------------------------------------------------------------


def test_processing_status_no_scan_yet() -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        status = compute_processing_status(session, asmnt_id)
        assert status.current_scan_id is None
        assert status.is_processed is False
        assert status.is_stale is False
        _cleanup(session, asmnt_id)


def test_processing_status_scan_completed_but_not_yet_processed() -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            with get_session_factory()() as session:
                run = create_pipeline_run(session, asmnt_id, tmp)
                run_id = run.id
                scan_stage = session.scalars(
                    select(StageRun).where(StageRun.pipeline_run_id == run_id, StageRun.stage_key == "scan")
                ).first()
                assert _run_stage(scan_stage, run, session) == "completed"  # only scan, not parse/dependencies

            with get_session_factory()() as session:
                status = compute_processing_status(session, asmnt_id)
                assert status.current_scan_id is not None
                assert status.is_processed is False
                assert status.is_stale is True
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_processing_status_fully_processed() -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            with get_session_factory()() as session:
                run = create_pipeline_run(session, asmnt_id, tmp)
                run_id = run.id
            run_pipeline(run_id, settings.database_url)

            with get_session_factory()() as session:
                status = compute_processing_status(session, asmnt_id)
                assert status.is_processed is True
                assert status.is_stale is False
                assert status.latest_run_id == run_id
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_processing_status_stale_when_newer_ingestion_not_yet_processed() -> None:
    """A later ingestion (Step 1) supersedes an already-processed earlier one — even

    though *that* earlier scan was fully processed, the current one is not, so
    is_stale must reflect the newer scan, not the old processed one.
    """
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp1:
            (Path(tmp1) / "first.abap").write_text("REPORT zfirst.")
            with get_session_factory()() as session:
                run1 = create_pipeline_run(session, asmnt_id, tmp1)
                run1_id = run1.id
            run_pipeline(run1_id, settings.database_url)

        with tempfile.TemporaryDirectory(dir=scan_root) as tmp2:
            (Path(tmp2) / "second.abap").write_text("REPORT zsecond.")
            # A fresh ingestion (Step 1) over a different directory, strictly newer.
            with get_session_factory()() as session:
                new_scan = SourceScan(
                    assessment_id=asmnt_id,
                    source_path=tmp2,
                    status=ScanStatus.COMPLETED.value,
                    total_files=1,
                    scanned_files=1,
                    completed_at=datetime.now(timezone.utc),
                )
                session.add(new_scan)
                session.commit()

            with get_session_factory()() as session:
                status = compute_processing_status(session, asmnt_id)
                assert status.current_scan_source_path == tmp2
                assert status.is_processed is False
                assert status.is_stale is True
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# API contract: GET .../pipeline-runs/processing-status
# ---------------------------------------------------------------------------


def test_processing_status_endpoint_no_ingestion(client) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.get(f"/assessments/{asmnt_id}/pipeline-runs/processing-status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["current_scan_id"] is None
        assert body["is_stale"] is False
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_processing_status_endpoint_after_pipeline_run_via_api(client) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            resp = client.post(f"/assessments/{asmnt_id}/pipeline-runs", json={"source_path": tmp})
            assert resp.status_code == 201

            status_resp = client.get(f"/assessments/{asmnt_id}/pipeline-runs/processing-status")
            assert status_resp.status_code == 200
            body = status_resp.json()
            assert body["is_processed"] is True
            assert body["is_stale"] is False
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# /objects scoped to the current scan — a new ingestion invalidates stale results
# ---------------------------------------------------------------------------


def test_list_objects_scoped_to_current_scan(client) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp1:
            (Path(tmp1) / "first.abap").write_text("REPORT zfirst.")
            with get_session_factory()() as session:
                run1 = create_pipeline_run(session, asmnt_id, tmp1)
                run1_id = run1.id
            run_pipeline(run1_id, settings.database_url)

        with tempfile.TemporaryDirectory(dir=scan_root) as tmp2:
            (Path(tmp2) / "second.abap").write_text("REPORT zsecond.")
            with get_session_factory()() as session:
                run2 = create_pipeline_run(session, asmnt_id, tmp2)
                run2_id = run2.id
            run_pipeline(run2_id, settings.database_url)

            resp = client.get(f"/assessments/{asmnt_id}/objects")
            assert resp.status_code == 200
            names = {o["object_name"] for o in resp.json()}
            assert names == {"ZSECOND"}
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_list_objects_empty_when_no_ingestion(client) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.get(f"/assessments/{asmnt_id}/objects")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# Standalone manual parse endpoint removed — parsing only via the durable pipeline
# ---------------------------------------------------------------------------


def test_manual_parse_route_removed(client) -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
    try:
        resp = client.post(f"/assessments/{asmnt_id}/scans/1/parse")
        assert resp.status_code == 404
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
