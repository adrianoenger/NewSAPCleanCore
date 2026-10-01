"""Results-summary aggregation (SPRINT-15) — extracted from `api/routes/dashboard.py` so the
Copilot's "structured query" context channel (SPRINT-16) reuses the exact same definition the
Dashboard Geral / Preliminary Processing Summary KPIs use, instead of re-deriving it.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from persistence.models import (
    ATCFinding,
    ATCRun,
    Application,
    ApplicationStatus,
    BusinessRule,
    BusinessRuleStatus,
    CleanCoreAssessment,
    EvidenceCorrelation,
    EvidenceCorrelationStatus,
    EvidenceRecord,
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


# ---------------------------------------------------------------------------
# Dashboard overview (SPRINT-18 CAP-003, ADR-019) — the reference dashboard's panels.
# ---------------------------------------------------------------------------

UNCLASSIFIED = "UNCLASSIFIED"

_MATCHED_STATUSES = (EvidenceCorrelationStatus.MATCHED_EXACT.value, EvidenceCorrelationStatus.MATCHED_HEURISTIC.value)
_TARGET_SAP_OBJECT = "SAP_OBJECT"
_USAGE_LEVEL_KEY = "USAGE LEVEL"
_UNUSED_LEVEL = "Unused"


def _usage_signal_correlation_rows():
    """Base `(SAPObject id, USAGE LEVEL)` query shared by the dashboard aggregation and the
    `/object-list` drill-down filter (SPRINT-20, Panaya usage/repository XLSX profile — ADR-017
    amendment).

    Filters on the `normalized_payload` JSONB key actually being present rather than on any
    provider-specific `record_type`, so a HANA Sizing Report `USAGE_SIGNAL` row (per-table sizing
    metrics, no `USAGE LEVEL` key) is naturally excluded without hard-coding provider identity —
    consistent with ADR-017's capability-oriented, provider-agnostic evidence model. Reuses the
    existing generic `evidence.correlation` pipeline's `MATCHED_*` correlations unchanged (no new
    correlation logic).
    """
    return (
        select(EvidenceCorrelation.target_id.label("object_id"), EvidenceRecord.normalized_payload[_USAGE_LEVEL_KEY].astext.label("usage_level"))
        .join(EvidenceRecord, EvidenceCorrelation.evidence_record_id == EvidenceRecord.id)
        .where(
            EvidenceCorrelation.target_type == _TARGET_SAP_OBJECT,
            EvidenceCorrelation.status.in_(_MATCHED_STATUSES),
            EvidenceRecord.capability == "USAGE_SIGNAL",
            EvidenceRecord.normalized_payload[_USAGE_LEVEL_KEY].astext.is_not(None),
        )
    )


def usage_signal_object_ids_by_level(session: Session, in_scan) -> dict[str, set[int]]:
    """Current-scan `SAPObject` ids grouped by their correlated `USAGE_SIGNAL` evidence's
    `USAGE LEVEL`. An object can carry more than one matching record (e.g. a re-import); each
    object is counted once per level via the `set`, never once per record."""
    rows = session.execute(_usage_signal_correlation_rows().where(EvidenceCorrelation.target_id.in_(in_scan))).all()
    by_level: dict[str, set[int]] = {}
    for obj_id, level in rows:
        if obj_id is None:
            continue
        by_level.setdefault(level, set()).add(obj_id)
    return by_level


def usage_level_correlation_subquery():
    """One row per correlated object (`object_id`, `usage_level`) for an outer-join drill-down
    filter/column — `usage_level` is a `MAX` tie-break on the rare chance more than one distinct
    level somehow correlates to the same object; the realistic case is exactly one."""
    return (
        select(
            EvidenceCorrelation.target_id.label("object_id"),
            func.max(EvidenceRecord.normalized_payload[_USAGE_LEVEL_KEY].astext).label("usage_level"),
        )
        .join(EvidenceRecord, EvidenceCorrelation.evidence_record_id == EvidenceRecord.id)
        .where(
            EvidenceCorrelation.target_type == _TARGET_SAP_OBJECT,
            EvidenceCorrelation.status.in_(_MATCHED_STATUSES),
            EvidenceRecord.capability == "USAGE_SIGNAL",
            EvidenceRecord.normalized_payload[_USAGE_LEVEL_KEY].astext.is_not(None),
        )
        .group_by(EvidenceCorrelation.target_id)
        .subquery()
    )


def custom_object_filter():
    """Customer-namespace objects: Z*/Y* or a registered `/NAMESPACE/` prefix (SAP convention)."""
    name = func.upper(SAPObject.object_name)
    return or_(name.like("Z%"), name.like("Y%"), name.like("/%"))


def get_current_atc_run(session: Session, assessment_id: int) -> ATCRun | None:
    return session.scalars(
        select(ATCRun)
        .where(ATCRun.assessment_id == assessment_id)
        .order_by(ATCRun.imported_at.desc(), ATCRun.id.desc())
        .limit(1)
    ).first()


@dataclass(frozen=True)
class DashboardOverview:
    summary: DashboardSummary
    objects_total: int
    objects_custom: int
    objects_by_type: dict[str, int]
    atc_run_id: int | None
    atc_total: int
    atc_by_priority: dict[str, int]
    objects_classified: int
    clean_core_objects: dict[str, int]
    clean_core_applications: dict[str, int]
    usage_signal_by_level: dict[str, int]
    unused_custom_objects: int


def compute_dashboard_overview(session: Session, assessment_id: int) -> DashboardOverview:
    summary = compute_dashboard_summary(session, assessment_id)
    current_scan = get_current_scan(session, assessment_id)

    objects_by_type: dict[str, int] = {}
    objects_custom = 0
    clean_core_objects: dict[str, int] = {}
    usage_signal_by_level: dict[str, int] = {}
    unused_custom_objects = 0
    if current_scan is not None:
        in_scan = (
            select(SAPObject.id)
            .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
            .where(SourceFile.scan_id == current_scan.id)
        )
        objects_by_type = dict(
            session.execute(
                select(SAPObject.object_type, func.count(SAPObject.id))
                .where(SAPObject.id.in_(in_scan))
                .group_by(SAPObject.object_type)
            ).all()
        )
        objects_custom = (
            session.scalar(
                select(func.count(SAPObject.id)).where(SAPObject.id.in_(in_scan), custom_object_filter())
            )
            or 0
        )
        # Objects inherit their owning Application's classification (ADR-018).
        for recommendation, count in session.execute(
            select(CleanCoreAssessment.recommendation, func.count(SAPObject.id))
            .select_from(SAPObject)
            .outerjoin(CleanCoreAssessment, CleanCoreAssessment.application_id == SAPObject.application_id)
            .where(SAPObject.id.in_(in_scan))
            .group_by(CleanCoreAssessment.recommendation)
        ).all():
            key = recommendation or UNCLASSIFIED
            clean_core_objects[key] = clean_core_objects.get(key, 0) + count

        usage_object_ids_by_level = usage_signal_object_ids_by_level(session, in_scan)
        usage_signal_by_level = {level: len(ids) for level, ids in usage_object_ids_by_level.items()}
        unused_object_ids = usage_object_ids_by_level.get(_UNUSED_LEVEL)
        if unused_object_ids:
            unused_custom_objects = (
                session.scalar(
                    select(func.count(SAPObject.id)).where(
                        SAPObject.id.in_(unused_object_ids), custom_object_filter()
                    )
                )
                or 0
            )

    clean_core_applications: dict[str, int] = {}
    for recommendation, count in session.execute(
        select(CleanCoreAssessment.recommendation, func.count(Application.id))
        .select_from(Application)
        .outerjoin(CleanCoreAssessment, CleanCoreAssessment.application_id == Application.id)
        .where(Application.assessment_id == assessment_id, Application.status != ApplicationStatus.MERGED.value)
        .group_by(CleanCoreAssessment.recommendation)
    ).all():
        key = recommendation or UNCLASSIFIED
        clean_core_applications[key] = clean_core_applications.get(key, 0) + count

    atc_run = get_current_atc_run(session, assessment_id)
    atc_by_priority: dict[str, int] = {}
    if atc_run is not None:
        for priority, count in session.execute(
            select(ATCFinding.priority, func.count(ATCFinding.id))
            .where(ATCFinding.atc_run_id == atc_run.id)
            .group_by(ATCFinding.priority)
        ).all():
            atc_by_priority[str(priority) if priority is not None else "none"] = count

    return DashboardOverview(
        summary=summary,
        objects_total=summary.objects_analyzed,
        objects_custom=objects_custom,
        objects_by_type=objects_by_type,
        atc_run_id=atc_run.id if atc_run else None,
        atc_total=sum(atc_by_priority.values()),
        atc_by_priority=atc_by_priority,
        objects_classified=sum(c for k, c in clean_core_objects.items() if k != UNCLASSIFIED),
        clean_core_objects=clean_core_objects,
        usage_signal_by_level=usage_signal_by_level,
        unused_custom_objects=unused_custom_objects,
        clean_core_applications=clean_core_applications,
    )
