"""API routes for durable pipeline execution (SPRINT-06 / ADR-005)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.routes.ingestion import _validate_scan_path
from api.schemas.pipeline import (
    PipelineRunCreate,
    PipelineRunListResponse,
    PipelineRunRecord,
    ProcessingStatusRecord,
    StageRunRecord,
    WorkItemRecord,
    WorkItemsResponse,
)
from persistence.database import get_session
from persistence.models import Assessment, PipelineRun, PipelineRunKind, StageRun, WorkItem
from pipeline.engine import create_pipeline_run, run_pipeline
from pipeline.status import compute_processing_status
from settings import get_settings

router = APIRouter(prefix="/assessments/{assessment_id}/pipeline-runs", tags=["pipeline"])

_RESUMABLE_STATUSES = ("pending", "paused", "failed")
# Both kinds only re-run AI stages over an already-parsed scan; either counts as "AI-only" for
# the "is a full run already running" guard and never blocks/gets blocked by the other.
_AI_ONLY_KINDS = (PipelineRunKind.AI_REPROCESSING.value, PipelineRunKind.AI_REPROCESSING_APPLICATIONS.value)
_FROM_STAGE_TO_KIND = {
    "object_understanding": PipelineRunKind.AI_REPROCESSING.value,
    "application_discovery": PipelineRunKind.AI_REPROCESSING_APPLICATIONS.value,
}


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


def _to_record(run: PipelineRun, session: Session) -> PipelineRunRecord:
    stages = list(
        session.scalars(
            select(StageRun).where(StageRun.pipeline_run_id == run.id).order_by(StageRun.sequence)
        )
    )
    return PipelineRunRecord(
        id=run.id,
        assessment_id=run.assessment_id,
        kind=run.kind,
        source_path=run.source_path,
        source_scan_id=run.source_scan_id,
        status=run.status,
        pause_requested=run.pause_requested,
        error=run.error,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        stages=[StageRunRecord.model_validate(s) for s in stages],
    )


def _require_run(assessment_id: int, run_id: int, session: Session) -> PipelineRun:
    run = session.get(PipelineRun, run_id)
    if run is None or run.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


@router.post("", response_model=PipelineRunRecord, status_code=201)
def start_pipeline_run(
    assessment_id: int,
    body: PipelineRunCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> PipelineRunRecord:
    _require_assessment(assessment_id, session)
    settings = get_settings()
    validated = _validate_scan_path(body.source_path, settings.scan_root)
    validated_str = str(validated)

    existing = session.scalars(
        select(PipelineRun).where(
            PipelineRun.assessment_id == assessment_id,
            PipelineRun.kind == PipelineRunKind.SOURCE_PROCESSING.value,
            PipelineRun.source_path == validated_str,
            PipelineRun.status.in_(["pending", "running", "paused", "failed"]),
        )
    ).first()

    run = existing if existing is not None else create_pipeline_run(session, assessment_id, validated_str)

    if run.status != "running":
        background_tasks.add_task(run_pipeline, run.id, settings.database_url)

    return _to_record(run, session)


@router.post("/reprocess-ai", response_model=PipelineRunRecord, status_code=201)
def reprocess_ai(
    assessment_id: int,
    background_tasks: BackgroundTasks,
    from_stage: Literal["object_understanding", "application_discovery"] = Query("object_understanding"),
    session: Session = Depends(get_session),
) -> PipelineRunRecord:
    """SPRINT-18 CAP-006/CAP-007: re-run only the AI stages over the scan of the latest completed
    full run (no rescan/reparse). `from_stage=application_discovery` skips object_understanding
    and business_rule_discovery too, reusing their already-persisted results — useful when only
    the clustering/Clean Core/summary stages need to regenerate. An unfinished run of the same
    kind is resumed instead of duplicated."""
    _require_assessment(assessment_id, session)
    settings = get_settings()
    kind = _FROM_STAGE_TO_KIND[from_stage]

    running = session.scalars(
        select(PipelineRun).where(
            PipelineRun.assessment_id == assessment_id,
            PipelineRun.kind.not_in(_AI_ONLY_KINDS),
            PipelineRun.status == "running",
        )
    ).first()
    if running is not None:
        raise HTTPException(status_code=409, detail="Há um processamento em execução para este assessment")

    base = session.scalars(
        select(PipelineRun)
        .where(
            PipelineRun.assessment_id == assessment_id,
            PipelineRun.kind == PipelineRunKind.SOURCE_PROCESSING.value,
            PipelineRun.status == "completed",
            PipelineRun.source_scan_id.is_not(None),
        )
        .order_by(PipelineRun.id.desc())
    ).first()
    if base is None:
        raise HTTPException(status_code=409, detail="Nenhum processamento completo para reaproveitar — execute o processamento primeiro")

    run = session.scalars(
        select(PipelineRun).where(
            PipelineRun.assessment_id == assessment_id,
            PipelineRun.kind == kind,
            PipelineRun.status.in_(["pending", "running", "paused", "failed"]),
        )
    ).first()
    if run is None:
        run = create_pipeline_run(session, assessment_id, base.source_path, kind=kind)
        run.source_scan_id = base.source_scan_id
        session.commit()

    if run.status != "running":
        background_tasks.add_task(run_pipeline, run.id, settings.database_url)

    return _to_record(run, session)


@router.get("", response_model=PipelineRunListResponse)
def list_pipeline_runs(
    assessment_id: int,
    session: Session = Depends(get_session),
) -> PipelineRunListResponse:
    _require_assessment(assessment_id, session)
    runs = list(
        session.scalars(
            select(PipelineRun)
            .where(PipelineRun.assessment_id == assessment_id)
            .order_by(PipelineRun.created_at.desc())
        )
    )
    return PipelineRunListResponse(
        assessment_id=assessment_id,
        runs=[_to_record(r, session) for r in runs],
        total=len(runs),
    )


@router.get("/processing-status", response_model=ProcessingStatusRecord)
def get_processing_status(
    assessment_id: int,
    session: Session = Depends(get_session),
) -> ProcessingStatusRecord:
    """Current ingestion for this Assessment and whether Step 3 already processed it."""
    _require_assessment(assessment_id, session)
    status = compute_processing_status(session, assessment_id)
    return ProcessingStatusRecord(**status.__dict__)


@router.get("/{run_id}", response_model=PipelineRunRecord)
def get_pipeline_run(
    assessment_id: int,
    run_id: int = Path(...),
    session: Session = Depends(get_session),
) -> PipelineRunRecord:
    _require_assessment(assessment_id, session)
    run = _require_run(assessment_id, run_id, session)
    return _to_record(run, session)


@router.get("/{run_id}/work-items", response_model=WorkItemsResponse)
def list_work_items(
    assessment_id: int,
    run_id: int = Path(...),
    stage_key: str | None = None,
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> WorkItemsResponse:
    _require_assessment(assessment_id, session)
    _require_run(assessment_id, run_id, session)

    q = select(WorkItem).join(StageRun).where(StageRun.pipeline_run_id == run_id)
    if stage_key:
        q = q.where(StageRun.stage_key == stage_key)
    if status:
        q = q.where(WorkItem.status == status)

    items = list(session.scalars(q.order_by(WorkItem.id).offset(offset).limit(limit)))

    count_q = select(func.count(WorkItem.id)).join(StageRun).where(StageRun.pipeline_run_id == run_id)
    if stage_key:
        count_q = count_q.where(StageRun.stage_key == stage_key)
    if status:
        count_q = count_q.where(WorkItem.status == status)
    total = session.scalar(count_q) or 0

    return WorkItemsResponse(items=[WorkItemRecord.model_validate(i) for i in items], total=total)


@router.post("/{run_id}/pause", response_model=PipelineRunRecord)
def pause_pipeline_run(
    assessment_id: int,
    run_id: int = Path(...),
    session: Session = Depends(get_session),
) -> PipelineRunRecord:
    _require_assessment(assessment_id, session)
    run = _require_run(assessment_id, run_id, session)
    if run.status != "running":
        raise HTTPException(status_code=409, detail=f"Cannot pause a run in status '{run.status}'")
    run.pause_requested = True
    session.commit()
    return _to_record(run, session)


@router.post("/{run_id}/resume", response_model=PipelineRunRecord)
def resume_pipeline_run(
    assessment_id: int,
    background_tasks: BackgroundTasks,
    run_id: int = Path(...),
    session: Session = Depends(get_session),
) -> PipelineRunRecord:
    _require_assessment(assessment_id, session)
    run = _require_run(assessment_id, run_id, session)
    if run.status not in _RESUMABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Cannot resume a run in status '{run.status}'")
    run.pause_requested = False
    run.status = "pending"
    run.error = None
    session.commit()

    settings = get_settings()
    background_tasks.add_task(run_pipeline, run.id, settings.database_url)
    return _to_record(run, session)


@router.post("/{run_id}/work-items/{item_id}/retry", response_model=WorkItemRecord)
def retry_work_item(
    assessment_id: int,
    run_id: int = Path(...),
    item_id: int = Path(...),
    session: Session = Depends(get_session),
) -> WorkItemRecord:
    _require_assessment(assessment_id, session)
    _require_run(assessment_id, run_id, session)

    item = session.get(WorkItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Work item not found")
    stage = session.get(StageRun, item.stage_run_id)
    if stage is None or stage.pipeline_run_id != run_id:
        raise HTTPException(status_code=404, detail="Work item not found")
    if item.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed work items can be retried")

    item.status = "pending"
    item.attempts = 0
    item.last_error = None
    item.started_at = None
    item.completed_at = None
    stage.failed_items = max(0, stage.failed_items - 1)
    session.commit()
    return WorkItemRecord.model_validate(item)
