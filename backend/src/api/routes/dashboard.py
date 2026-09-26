"""Results aggregation route (SPRINT-15) — backs the Preliminary Processing Summary and the
Dashboard Geral synthesis page with the cross-entity KPIs the Baseline lists (objects analisados,
customizações identificadas, findings críticos, objetos com alto impacto, regras de negócio
identificadas). The aggregation itself lives in `pipeline.dashboard_summary` (SPRINT-16 extracted
it so the Copilot's structured-query context channel reuses the same definition).

"Customizações identificadas" maps to the count of discovered `Application` rows (excluding
MERGED) — an `Application` is, by `ai.application_discovery`'s own definition, a cluster of custom
SAP objects, so this is the closest real signal without fabricating a distinct AI judgment. The
Baseline's canonical processing flow also lists a separate "customisation identification" AI step
that is not implemented as its own capability yet (see BACKLOG BL-021).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from api.schemas.dashboard import DashboardSummaryRead
from persistence.database import get_session
from persistence.models import Assessment
from pipeline.dashboard_summary import compute_dashboard_summary

router = APIRouter(prefix="/assessments/{assessment_id}", tags=["dashboard"])


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


@router.get("/dashboard-summary", response_model=DashboardSummaryRead)
def get_dashboard_summary(
    assessment_id: int = Path(...),
    session: Session = Depends(get_session),
) -> DashboardSummaryRead:
    _require_assessment(assessment_id, session)
    summary = compute_dashboard_summary(session, assessment_id)
    return DashboardSummaryRead(**summary.__dict__)
