"""Durable pipeline orchestrator (ADR-005).

Runs stages in dependency order, one work item at a time, persisting all
progress so execution survives process restarts. Designed to be re-entrant:
calling `run_pipeline` again on a PENDING/RUNNING/PAUSED run resumes from the
first incomplete work item.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from persistence.models import PipelineRun, StageRun, WorkItem
from pipeline.stages import STAGES_BY_KIND, StageDefinition

_STAGES_BY_KEY: dict[str, StageDefinition] = {
    s.key: s for stages in STAGES_BY_KIND.values() for s in stages
}

_TERMINAL_STAGE_STATUSES = ("completed", "skipped")

_TERMINAL_PIPELINE_STATUSES = ("completed",)


def create_pipeline_run(
    session: Session,
    assessment_id: int,
    source_path: str,
    kind: str = "source_processing",
    evidence_dataset_id: int | None = None,
) -> PipelineRun:
    """Create a PipelineRun with one StageRun per stage registered for `kind`, in dependency order."""
    run = PipelineRun(
        assessment_id=assessment_id,
        source_path=source_path,
        status="pending",
        kind=kind,
        evidence_dataset_id=evidence_dataset_id,
    )
    session.add(run)
    session.flush()
    for seq, stage_def in enumerate(STAGES_BY_KIND[kind]):
        session.add(
            StageRun(
                pipeline_run_id=run.id,
                stage_key=stage_def.key,
                sequence=seq,
                depends_on=list(stage_def.depends_on),
                status="pending",
            )
        )
    session.commit()
    session.refresh(run)
    return run


def _dependencies_met(stage: StageRun, stages_by_key: dict[str, StageRun]) -> bool:
    return all(stages_by_key[dep].status == "completed" for dep in stage.depends_on)


def run_pipeline(pipeline_run_id: int, db_url: str) -> None:
    """Advance a PipelineRun until it completes, fails, or a pause is requested.

    Safe to invoke repeatedly (background task on start, and again on resume).
    """
    engine = create_engine(db_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as session:
        run = session.get(PipelineRun, pipeline_run_id)
        if run is None or run.status in _TERMINAL_PIPELINE_STATUSES:
            return

        run.status = "running"
        if run.started_at is None:
            run.started_at = datetime.now(timezone.utc)
        session.commit()

        while True:
            session.refresh(run)
            if run.pause_requested:
                run.status = "paused"
                session.commit()
                return

            stages = list(
                session.scalars(
                    select(StageRun)
                    .where(StageRun.pipeline_run_id == run.id)
                    .order_by(StageRun.sequence)
                )
            )
            stages_by_key = {s.stage_key: s for s in stages}

            next_stage = next(
                (
                    s
                    for s in stages
                    if s.status not in _TERMINAL_STAGE_STATUSES and _dependencies_met(s, stages_by_key)
                ),
                None,
            )

            if next_stage is None:
                all_done = all(s.status in _TERMINAL_STAGE_STATUSES for s in stages)
                run.status = "completed" if all_done else "failed"
                run.completed_at = datetime.now(timezone.utc)
                session.commit()
                return

            outcome = _run_stage(next_stage, run, session)
            if outcome == "paused":
                run.status = "paused"
                session.commit()
                return
            if outcome == "failed":
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                session.commit()
                return
            # outcome == "completed": loop again to pick up the next eligible stage


def _run_stage(stage: StageRun, run: PipelineRun, session: Session) -> str:
    defn = _STAGES_BY_KEY[stage.stage_key]

    stage.status = "running"
    if stage.started_at is None:
        stage.started_at = datetime.now(timezone.utc)
    session.commit()

    if stage.total_items == 0:
        try:
            defn.prepare(stage, run, session)
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            stage.status = "failed"
            stage.error = str(exc)[:2000]
            session.commit()
            return "failed"

    while True:
        session.refresh(run)
        if run.pause_requested:
            stage.status = "paused"
            session.commit()
            return "paused"

        item = session.scalars(
            select(WorkItem)
            .where(WorkItem.stage_run_id == stage.id, WorkItem.status == "pending")
            .order_by(WorkItem.id)
            .limit(1)
        ).first()
        if item is None:
            break

        item.status = "running"
        item.started_at = datetime.now(timezone.utc)
        session.commit()

        try:
            with session.begin_nested():
                defn.process_item(item, stage, run, session)
            item.status = "completed"
            item.completed_at = datetime.now(timezone.utc)
            stage.completed_items += 1
            session.commit()
        except Exception as exc:  # noqa: BLE001
            item.attempts += 1
            item.last_error = str(exc)[:2000]
            if item.attempts >= item.max_attempts:
                item.status = "failed"
                stage.failed_items += 1
            else:
                item.status = "pending"
            session.commit()

    stage.status = "failed" if stage.failed_items > 0 else "completed"
    stage.completed_at = datetime.now(timezone.utc)
    session.commit()

    if defn.finalize is not None:
        defn.finalize(stage, run, session)
        session.commit()

    return stage.status


def recover_orphans(session: Session) -> int:
    """Requeue work stuck in a RUNNING state (e.g. after an unclean backend shutdown).

    Called at application startup. Running work items and stage runs are reset to
    PENDING so they are re-attempted; running pipeline runs are marked PAUSED so a
    human explicitly resumes them rather than silently continuing unattended.
    """
    recovered = 0

    session.execute(
        WorkItem.__table__.update()
        .where(WorkItem.status == "running")
        .values(status="pending")
    )
    session.execute(
        StageRun.__table__.update()
        .where(StageRun.status == "running")
        .values(status="pending")
    )

    orphaned_runs = list(session.scalars(select(PipelineRun).where(PipelineRun.status == "running")))
    for run in orphaned_runs:
        run.status = "paused"
        run.pause_requested = True
        recovered += 1

    session.commit()
    return recovered
