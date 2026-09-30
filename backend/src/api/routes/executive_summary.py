"""Executive Summary routes (SPRINT-18 CAP-005).

`GET` returns the persisted summary produced by the `executive_summary` pipeline stage;
`POST .../regenerate` runs the same generator synchronously (one LLM call) and persists it.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.executive_summary.generator import generate_executive_summary
from ai.providers import get_provider
from api.schemas.executive_summary import ExecutiveSummaryRead
from persistence.database import get_session
from persistence.models import Assessment, ExecutiveSummary
from settings import get_settings

router = APIRouter(prefix="/assessments/{assessment_id}/executive-summary", tags=["executive-summary"])


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


@router.get("", response_model=ExecutiveSummaryRead)
def get_executive_summary(assessment_id: int = Path(...), session: Session = Depends(get_session)) -> ExecutiveSummary:
    _require_assessment(assessment_id, session)
    row = session.scalars(select(ExecutiveSummary).where(ExecutiveSummary.assessment_id == assessment_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Executive summary not generated yet")
    return row


@router.post("/regenerate", response_model=ExecutiveSummaryRead)
def regenerate_executive_summary(
    assessment_id: int = Path(...), session: Session = Depends(get_session)
) -> ExecutiveSummary:
    assessment = _require_assessment(assessment_id, session)
    row = generate_executive_summary(session, assessment_id, assessment.name, get_provider(get_settings()))
    session.commit()
    session.refresh(row)
    return row
