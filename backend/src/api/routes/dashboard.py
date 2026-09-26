"""Results aggregation route (SPRINT-15) — backs the Preliminary Processing Summary and the
Dashboard Geral synthesis page with the cross-entity KPIs the Baseline lists (objects analisados,
customizações identificadas, findings críticos, objetos com alto impacto, regras de negócio
identificadas), computed server-side so every consumer (dashboard, future preliminary summary)
reuses one definition instead of re-deriving it client-side per view.

"Customizações identificadas" maps to the count of discovered `Application` rows (excluding
MERGED) — an `Application` is, by `ai.application_discovery`'s own definition, a cluster of custom
SAP objects, so this is the closest real signal without fabricating a distinct AI judgment. The
Baseline's canonical processing flow also lists a separate "customisation identification" AI step
that is not implemented as its own capability yet (see BACKLOG BL-021).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.dashboard import DashboardSummaryRead
from persistence.database import get_session
from persistence.models import (
    Application,
    ApplicationStatus,
    Assessment,
    BusinessRule,
    BusinessRuleStatus,
    CleanCoreAssessment,
    RiskLevel,
    SAPObject,
    SourceFile,
    TechnicalFinding,
    TechnicalFindingSeverity,
)
from pipeline.status import compute_processing_status, get_current_scan

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

    current_scan = get_current_scan(session, assessment_id)
    if current_scan is None:
        objects_analyzed = 0
        high_impact_objects = 0
    else:
        objects_analyzed = (
            session.scalar(
                select(func.count(SAPObject.id))
                .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
                .where(SourceFile.scan_id == current_scan.id)
            )
            or 0
        )
        high_impact_objects = (
            session.scalar(
                select(func.count(SAPObject.id))
                .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
                .join(Application, SAPObject.application_id == Application.id)
                .join(CleanCoreAssessment, CleanCoreAssessment.application_id == Application.id)
                .where(
                    SourceFile.scan_id == current_scan.id,
                    CleanCoreAssessment.technical_risk.in_(
                        [RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]
                    ),
                )
            )
            or 0
        )

    customizations_identified = (
        session.scalar(
            select(func.count(Application.id)).where(
                Application.assessment_id == assessment_id,
                Application.status != ApplicationStatus.MERGED.value,
            )
        )
        or 0
    )

    critical_findings = (
        session.scalar(
            select(func.count(TechnicalFinding.id)).where(
                TechnicalFinding.assessment_id == assessment_id,
                TechnicalFinding.severity == TechnicalFindingSeverity.HIGH.value,
            )
        )
        or 0
    )

    business_rules_identified = (
        session.scalar(
            select(func.count(BusinessRule.id)).where(
                BusinessRule.assessment_id == assessment_id,
                BusinessRule.status == BusinessRuleStatus.CANDIDATE.value,
            )
        )
        or 0
    )

    is_stale = compute_processing_status(session, assessment_id).is_stale

    return DashboardSummaryRead(
        assessment_id=assessment_id,
        objects_analyzed=objects_analyzed,
        customizations_identified=customizations_identified,
        critical_findings=critical_findings,
        high_impact_objects=high_impact_objects,
        business_rules_identified=business_rules_identified,
        is_stale=is_stale,
    )
