"""SPRINT-06 — Durable Pipeline Execution: engine and API contract tests."""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import select, text

from persistence.database import get_session_factory
from persistence.models import (
    Assessment,
    AssessmentStatus,
    Client,
    PipelineRun,
    SAPObject,
    SAPObjectDependency,
    SourceFile,
    StageRun,
    WorkItem,
)
from pipeline.engine import _run_stage, create_pipeline_run, recover_orphans, run_pipeline
from settings import get_settings


def _make_assessment(session) -> int:
    c = Client(name="Sprint06 Test Client")
    session.add(c)
    session.flush()
    a = Assessment(client_id=c.id, name="Sprint06 Test", status=AssessmentStatus.CREATED.value)
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
# Engine: orphan recovery
# ---------------------------------------------------------------------------


def test_recover_orphans_requeues_running_work() -> None:
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)
        run = PipelineRun(assessment_id=asmnt_id, source_path="/workspace", status="running")
        session.add(run)
        session.flush()
        stage = StageRun(pipeline_run_id=run.id, stage_key="scan", sequence=0, depends_on=[], status="running")
        session.add(stage)
        session.flush()
        item = WorkItem(stage_run_id=stage.id, item_key="a.abap", payload={}, status="running")
        session.add(item)
        session.commit()

        recovered = recover_orphans(session)
        assert recovered == 1

        session.refresh(run)
        session.refresh(stage)
        session.refresh(item)
        assert run.status == "paused"
        assert run.pause_requested is True
        assert stage.status == "pending"
        assert item.status == "pending"

        _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# Engine: full run + cooperative pause/resume + bounded retry
# ---------------------------------------------------------------------------


def test_pipeline_full_run_wraps_scan_parse_dependencies() -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            p = Path(tmp)
            (p / "prog.abap").write_text(
                "REPORT ztest.\nCALL FUNCTION 'RFC_READ_TABLE'\n  EXPORTING query_table = 'MARA'.\n"
            )
            (p / "readme.md").write_text("# Not ABAP")

            with get_session_factory()() as session:
                run = create_pipeline_run(session, asmnt_id, tmp)
                run_id = run.id

            run_pipeline(run_id, settings.database_url)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
                stages = {
                    s.stage_key: s
                    for s in session.scalars(select(StageRun).where(StageRun.pipeline_run_id == run_id))
                }
                assert stages["scan"].status == "completed"
                assert stages["scan"].total_items == 2
                assert stages["parse"].status == "completed"
                assert stages["parse"].total_items == 1
                assert stages["detect_dependencies"].status == "completed"
                assert stages["detect_dependencies"].completed_items == 1

                files = list(session.scalars(select(SourceFile).where(SourceFile.assessment_id == asmnt_id)))
                assert len(files) == 2
                objects = list(session.scalars(select(SAPObject).where(SAPObject.assessment_id == asmnt_id)))
                assert len(objects) == 1
                deps = list(
                    session.scalars(select(SAPObjectDependency).where(SAPObjectDependency.assessment_id == asmnt_id))
                )
                assert any(d.target_name == "RFC_READ_TABLE" for d in deps)
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_second_pipeline_run_dependencies_stage_ignores_other_scans() -> None:
    """A later PipelineRun's detect_dependencies stage must only cover objects

    parsed from *its own* scan — not every object ever parsed for the
    assessment — otherwise a deleted/moved earlier scan's files would fail
    this run's stage even though they are unrelated to it.
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
            with get_session_factory()() as session:
                assert session.get(PipelineRun, run1_id).status == "completed"
        # tmp1 is now deleted — its SourceFile/SAPObject rows remain in the DB.

        with tempfile.TemporaryDirectory(dir=scan_root) as tmp2:
            (Path(tmp2) / "second.abap").write_text("REPORT zsecond.")
            with get_session_factory()() as session:
                run2 = create_pipeline_run(session, asmnt_id, tmp2)
                run2_id = run2.id
            run_pipeline(run2_id, settings.database_url)

            with get_session_factory()() as session:
                run2 = session.get(PipelineRun, run2_id)
                assert run2.status == "completed"
                deps_stage = session.scalars(
                    select(StageRun).where(StageRun.pipeline_run_id == run2_id, StageRun.stage_key == "detect_dependencies")
                ).first()
                assert deps_stage.total_items == 1
                assert deps_stage.failed_items == 0
                assert deps_stage.completed_items == 1
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_pause_after_first_stage_then_resume() -> None:
    """Cooperative pause: a pause requested between stages must stop the run

    before the next stage starts, and resuming (clearing the flag) must let it
    finish the remaining stages.
    """
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
                assert _run_stage(scan_stage, run, session) == "completed"

                # A pause request arrives right after the scan stage finishes.
                run.pause_requested = True
                session.commit()

            run_pipeline(run_id, settings.database_url)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "paused"
                stages = {
                    s.stage_key: s
                    for s in session.scalars(select(StageRun).where(StageRun.pipeline_run_id == run_id))
                }
                assert stages["scan"].status == "completed"
                assert stages["parse"].status == "pending"  # never started

            # Resume: clear the flag and re-run to completion.
            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                run.pause_requested = False
                run.status = "pending"
                session.commit()

            run_pipeline(run_id, settings.database_url)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_bounded_retry_marks_item_failed_then_manual_retry_succeeds() -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            tmp_path = Path(tmp)
            broken = tmp_path / "broken.abap"
            broken.write_text("REPORT zbroken.")

            with get_session_factory()() as session:
                run = create_pipeline_run(session, asmnt_id, tmp)
                run_id = run.id

                # Drive the scan stage to completion first (file still present).
                scan_stage = session.scalars(
                    select(StageRun).where(StageRun.pipeline_run_id == run_id, StageRun.stage_key == "scan")
                ).first()
                assert _run_stage(scan_stage, run, session) == "completed"

                # Now remove the file so the parse work item fails deterministically.
                broken.unlink()

                parse_stage = session.scalars(
                    select(StageRun).where(StageRun.pipeline_run_id == run_id, StageRun.stage_key == "parse")
                ).first()
                assert _run_stage(parse_stage, run, session) == "failed"

                session.refresh(parse_stage)
                assert parse_stage.failed_items == 1
                failed_item = session.scalars(
                    select(WorkItem).where(WorkItem.stage_run_id == parse_stage.id, WorkItem.status == "failed")
                ).first()
                assert failed_item.attempts == failed_item.max_attempts
                item_id = failed_item.id
                stage_id = parse_stage.id
                run.status = "failed"
                session.commit()

            # Fix the underlying issue, retry the item (as the API endpoint would), then resume.
            broken.write_text("REPORT zbroken.")
            with get_session_factory()() as session:
                item = session.get(WorkItem, item_id)
                stage = session.get(StageRun, stage_id)
                item.status = "pending"
                item.attempts = 0
                item.last_error = None
                stage.failed_items = max(0, stage.failed_items - 1)
                run = session.get(PipelineRun, run_id)
                run.status = "pending"
                run.pause_requested = False
                session.commit()

            run_pipeline(run_id, settings.database_url)

            with get_session_factory()() as session:
                run = session.get(PipelineRun, run_id)
                assert run.status == "completed"
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


# ---------------------------------------------------------------------------
# API contract tests
# ---------------------------------------------------------------------------


def test_start_pipeline_run_endpoint(client) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            resp = client.post(f"/assessments/{asmnt_id}/pipeline-runs", json={"source_path": tmp})
            assert resp.status_code == 201
            data = resp.json()
            run_id = data["id"]
            assert len(data["stages"]) == 6
            assert {s["stage_key"] for s in data["stages"]} == {
                "scan", "parse", "detect_dependencies", "object_understanding", "business_rule_discovery",
                "application_discovery",
            }

            # The background task runs synchronously within the request lifecycle
            # under TestClient, but the response body was serialized before it ran —
            # fetch the run again to observe the final state.
            detail_resp = client.get(f"/assessments/{asmnt_id}/pipeline-runs/{run_id}")
            assert detail_resp.status_code == 200
            assert detail_resp.json()["status"] == "completed"

            list_resp = client.get(f"/assessments/{asmnt_id}/pipeline-runs")
            assert list_resp.status_code == 200
            assert list_resp.json()["total"] == 1
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_pause_endpoint_rejects_non_running_run(client) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            resp = client.post(f"/assessments/{asmnt_id}/pipeline-runs", json={"source_path": tmp})
            run_id = resp.json()["id"]

            # The synchronous background task already finished (status completed).
            pause_resp = client.post(f"/assessments/{asmnt_id}/pipeline-runs/{run_id}/pause")
            assert pause_resp.status_code == 409
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_retry_endpoint_success_path_then_resume_completes(client) -> None:
    """The real HTTP retry endpoint resets a failed item and lets resume finish the run.

    The failure itself is manufactured directly in the DB (TestClient runs the
    background task synchronously, so a real mid-run file deletion cannot be
    interleaved) but the retry and resume calls below go through the actual
    HTTP routes, exercising their success path end to end.
    """
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")

            resp = client.post(f"/assessments/{asmnt_id}/pipeline-runs", json={"source_path": tmp})
            run_id = resp.json()["id"]
            detail = client.get(f"/assessments/{asmnt_id}/pipeline-runs/{run_id}").json()
            assert detail["status"] == "completed"
            parse_stage = next(s for s in detail["stages"] if s["stage_key"] == "parse")

            # Manufacture a failure on the parse stage's single work item.
            with get_session_factory()() as session:
                stage = session.get(StageRun, parse_stage["id"])
                item = session.scalars(select(WorkItem).where(WorkItem.stage_run_id == stage.id)).first()
                item.status = "failed"
                item.attempts = item.max_attempts
                item.last_error = "manufactured for test"
                stage.failed_items = 1
                stage.status = "failed"
                run = session.get(PipelineRun, run_id)
                run.status = "failed"
                session.commit()
                item_id = item.id

            items_resp = client.get(f"/assessments/{asmnt_id}/pipeline-runs/{run_id}/work-items?status=failed")
            assert items_resp.json()["total"] == 1

            retry_resp = client.post(
                f"/assessments/{asmnt_id}/pipeline-runs/{run_id}/work-items/{item_id}/retry"
            )
            assert retry_resp.status_code == 200
            retried = retry_resp.json()
            assert retried["status"] == "pending"
            assert retried["attempts"] == 0

            detail = client.get(f"/assessments/{asmnt_id}/pipeline-runs/{run_id}").json()
            parse_stage = next(s for s in detail["stages"] if s["stage_key"] == "parse")
            assert parse_stage["failed_items"] == 0

            resume_resp = client.post(f"/assessments/{asmnt_id}/pipeline-runs/{run_id}/resume")
            assert resume_resp.status_code == 200

            final = client.get(f"/assessments/{asmnt_id}/pipeline-runs/{run_id}").json()
            assert final["status"] == "completed"
            assert all(s["status"] == "completed" for s in final["stages"])
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)


def test_retry_endpoint_rejects_non_failed_item(client) -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        asmnt_id = _make_assessment(session)

    scan_root = Path(settings.scan_root)
    try:
        with tempfile.TemporaryDirectory(dir=scan_root) as tmp:
            (Path(tmp) / "a.abap").write_text("REPORT za.")
            resp = client.post(f"/assessments/{asmnt_id}/pipeline-runs", json={"source_path": tmp})
            run_id = resp.json()["id"]

            items_resp = client.get(f"/assessments/{asmnt_id}/pipeline-runs/{run_id}/work-items")
            assert items_resp.status_code == 200
            item_id = items_resp.json()["items"][0]["id"]

            retry_resp = client.post(
                f"/assessments/{asmnt_id}/pipeline-runs/{run_id}/work-items/{item_id}/retry"
            )
            assert retry_resp.status_code == 409
    finally:
        with get_session_factory()() as session:
            _cleanup(session, asmnt_id)
