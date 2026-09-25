"""Processing status derivation (SPRINT-07).

Answers "what is the current ingestion for this Assessment, and has the durable
pipeline already fully processed it?" — fully derived from existing rows
(SourceScan/PipelineRun/StageRun); no new persisted state or migration.

"Current" means the most recently completed SourceScan: a later ingestion always
supersedes an earlier one, and anything derived from a superseded scan is
implicitly stale until Step 3 reprocesses the current one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import PipelineRun, ScanStatus, SourceScan, StageRun

_PROCESSING_STAGES = ("parse", "detect_dependencies")


@dataclass(frozen=True)
class ProcessingStatus:
    current_scan_id: int | None
    current_scan_source_path: str | None
    current_scan_completed_at: datetime | None
    is_processed: bool
    is_stale: bool
    latest_run_id: int | None
    latest_run_status: str | None


def get_current_scan(session: Session, assessment_id: int) -> SourceScan | None:
    """Most recently completed SourceScan for an assessment (last ingestion wins)."""
    return session.scalars(
        select(SourceScan)
        .where(
            SourceScan.assessment_id == assessment_id,
            SourceScan.status == ScanStatus.COMPLETED.value,
        )
        .order_by(SourceScan.completed_at.desc())
    ).first()


def _latest_run_for_scan(session: Session, assessment_id: int, scan_id: int) -> PipelineRun | None:
    return session.scalars(
        select(PipelineRun)
        .where(PipelineRun.assessment_id == assessment_id, PipelineRun.source_scan_id == scan_id)
        .order_by(PipelineRun.id.desc())
    ).first()


def _fully_processed(session: Session, pipeline_run_id: int) -> bool:
    statuses = dict(
        session.execute(
            select(StageRun.stage_key, StageRun.status).where(
                StageRun.pipeline_run_id == pipeline_run_id,
                StageRun.stage_key.in_(_PROCESSING_STAGES),
            )
        ).all()
    )
    return all(statuses.get(key) == "completed" for key in _PROCESSING_STAGES)


def compute_processing_status(session: Session, assessment_id: int) -> ProcessingStatus:
    current = get_current_scan(session, assessment_id)
    if current is None:
        return ProcessingStatus(
            current_scan_id=None,
            current_scan_source_path=None,
            current_scan_completed_at=None,
            is_processed=False,
            is_stale=False,
            latest_run_id=None,
            latest_run_status=None,
        )

    run = _latest_run_for_scan(session, assessment_id, current.id)
    is_processed = run is not None and _fully_processed(session, run.id)

    return ProcessingStatus(
        current_scan_id=current.id,
        current_scan_source_path=current.source_path,
        current_scan_completed_at=current.completed_at,
        is_processed=is_processed,
        is_stale=not is_processed,
        latest_run_id=run.id if run is not None else None,
        latest_run_status=run.status if run is not None else None,
    )
