"""Results-summary aggregation (SPRINT-15) — extracted from `api/routes/dashboard.py` so the
Copilot's "structured query" context channel (SPRINT-16) reuses the exact same definition the
Dashboard Geral / Preliminary Processing Summary KPIs use, instead of re-deriving it.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from persistence.models import (
    Application,
    ApplicationStatus,
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


@dataclass(frozen=True)
class DashboardSummary:
    assessment_id: int
    objects_analyzed: int
    customizations_identified: int
    critical_findings: int
    high_impact_objects: int
    business_rules_identified: int
    is_stale: bool


def compute_dashboard_summary(session: Session, assessment_id: int) -> DashboardSummary:
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

    return DashboardSummary(
        assessment_id=assessment_id,
        objects_analyzed=objects_analyzed,
        customizations_identified=customizations_identified,
        critical_findings=critical_findings,
        high_impact_objects=high_impact_objects,
        business_rules_identified=business_rules_identified,
        is_stale=is_stale,
    )
