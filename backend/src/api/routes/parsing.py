"""SAP object parsing routes — browse objects parsed by the durable pipeline (Step 3), object detail.

Parsing itself is triggered only by the durable pipeline (SPRINT-07 consolidation) —
there is no standalone manual parse endpoint anymore.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.parsing import SAPObjectDetailRead, SAPObjectRead
from persistence.database import get_session
from persistence.models import Assessment, SAPObject, SourceFile
from pipeline.status import get_current_scan

router = APIRouter(prefix="/assessments", tags=["parsing"])


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


@router.get("/{assessment_id}/objects", response_model=list[SAPObjectRead])
def list_objects(
    assessment_id: int,
    object_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[SAPObject]:
    """Objects parsed from the *current* ingestion only — an older, superseded scan's
    objects are not returned, so a new ingestion invalidates stale results (SPRINT-07)."""
    _require_assessment(assessment_id, session)
    current_scan = get_current_scan(session, assessment_id)
    if current_scan is None:
        return []

    q = (
        select(SAPObject)
        .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
        .where(SourceFile.scan_id == current_scan.id)
    )
    if object_type:
        q = q.where(SAPObject.object_type == object_type)
    return list(
        session.scalars(q.order_by(SAPObject.object_name).offset(offset).limit(limit))
    )


@router.get("/{assessment_id}/objects/{object_id}", response_model=SAPObjectDetailRead)
def get_object(
    assessment_id: int,
    object_id: int,
    session: Session = Depends(get_session),
) -> SAPObject:
    _require_assessment(assessment_id, session)
    obj = session.get(SAPObject, object_id)
    if obj is None or obj.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="SAP object not found")
    return obj
