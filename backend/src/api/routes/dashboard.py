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

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from api.schemas.dashboard import (
    ATCFindingDetailRead,
    ATCFindingListItem,
    ATCFindingListResponse,
    DashboardOverviewRead,
    DashboardSummaryRead,
    ObjectListItem,
    ObjectListResponse,
)
from persistence.database import get_session
from persistence.models import (
    Application,
    Assessment,
    ATCFinding,
    CleanCoreAssessment,
    RiskLevel,
    SAPObject,
    SourceFile,
)
from pipeline.dashboard_summary import (
    UNCLASSIFIED,
    compute_dashboard_overview,
    compute_dashboard_summary,
    custom_object_filter,
    get_current_atc_run,
    usage_level_correlation_subquery,
)
from pipeline.status import get_current_scan

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


@router.get("/dashboard-overview", response_model=DashboardOverviewRead)
def get_dashboard_overview(
    assessment_id: int = Path(...),
    session: Session = Depends(get_session),
) -> DashboardOverviewRead:
    _require_assessment(assessment_id, session)
    overview = compute_dashboard_overview(session, assessment_id)
    data = dict(overview.__dict__)
    data["summary"] = DashboardSummaryRead(**overview.summary.__dict__)
    return DashboardOverviewRead(**data)


@router.get("/object-list", response_model=ObjectListResponse)
def list_objects_for_drilldown(
    assessment_id: int = Path(...),
    object_type: str | None = None,
    recommendation: str | None = Query(None, description=f"A Clean Core category or {UNCLASSIFIED}."),
    custom_only: bool = False,
    high_impact: bool = False,
    application_id: int | None = None,
    usage_level: str | None = Query(None, description="A correlated Panaya USAGE_SIGNAL level, e.g. 'Unused'."),
    q: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> ObjectListResponse:
    """Dashboard drill-down object list (ADR-019): current-scan objects enriched with their owning
    Application, inherited Clean Core classification (ADR-018) and correlated ATC finding count."""
    _require_assessment(assessment_id, session)
    current_scan = get_current_scan(session, assessment_id)
    if current_scan is None:
        return ObjectListResponse(items=[], total=0)

    atc_run = get_current_atc_run(session, assessment_id)
    atc_counts = (
        select(ATCFinding.correlated_object_id.label("object_id"), func.count(ATCFinding.id).label("n"))
        .where(ATCFinding.atc_run_id == (atc_run.id if atc_run else -1))
        .group_by(ATCFinding.correlated_object_id)
        .subquery()
    )
    usage_sub = usage_level_correlation_subquery()
    is_custom = custom_object_filter()
    base = (
        select(
            SAPObject,
            is_custom.label("is_custom"),
            Application.name,
            CleanCoreAssessment.recommendation,
            CleanCoreAssessment.technical_risk,
            func.coalesce(atc_counts.c.n, 0),
            usage_sub.c.usage_level,
        )
        .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
        .outerjoin(Application, Application.id == SAPObject.application_id)
        .outerjoin(CleanCoreAssessment, CleanCoreAssessment.application_id == SAPObject.application_id)
        .outerjoin(atc_counts, atc_counts.c.object_id == SAPObject.id)
        .outerjoin(usage_sub, usage_sub.c.object_id == SAPObject.id)
        .where(SourceFile.scan_id == current_scan.id)
    )
    if object_type:
        base = base.where(SAPObject.object_type == object_type)
    if recommendation == UNCLASSIFIED:
        base = base.where(CleanCoreAssessment.recommendation.is_(None))
    elif recommendation:
        base = base.where(CleanCoreAssessment.recommendation == recommendation)
    if custom_only:
        base = base.where(is_custom)
    if high_impact:
        base = base.where(CleanCoreAssessment.technical_risk.in_([RiskLevel.HIGH.value, RiskLevel.CRITICAL.value]))
    if application_id is not None:
        base = base.where(SAPObject.application_id == application_id)
    if usage_level:
        base = base.where(usage_sub.c.usage_level == usage_level)
    if q:
        pattern = f"%{q}%"
        base = base.where(or_(SAPObject.object_name.ilike(pattern), SAPObject.description.ilike(pattern)))

    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(base.order_by(SAPObject.object_name).offset(offset).limit(limit)).all()
    items = [
        ObjectListItem(
            id=obj.id,
            object_type=obj.object_type,
            object_name=obj.object_name,
            description=obj.description,
            is_custom=bool(custom),
            application_id=obj.application_id,
            application_name=app_name,
            recommendation=rec,
            technical_risk=risk,
            atc_findings=n,
            usage_level=usage,
        )
        for obj, custom, app_name, rec, risk, n, usage in rows
    ]
    return ObjectListResponse(items=items, total=total)


@router.get("/atc-findings", response_model=ATCFindingListResponse)
def list_current_atc_findings(
    assessment_id: int = Path(...),
    priority: int | None = None,
    object_id: int | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> ATCFindingListResponse:
    """Findings of the assessment's current (latest imported) ATC run, filterable for drill-down."""
    _require_assessment(assessment_id, session)
    atc_run = get_current_atc_run(session, assessment_id)
    if atc_run is None:
        return ATCFindingListResponse(atc_run_id=None, items=[], total=0)

    base = select(ATCFinding).where(ATCFinding.atc_run_id == atc_run.id)
    if priority is not None:
        base = base.where(ATCFinding.priority == priority)
    if object_id is not None:
        base = base.where(ATCFinding.correlated_object_id == object_id)
    if q:
        pattern = f"%{q}%"
        base = base.where(
            or_(
                ATCFinding.check_title.ilike(pattern),
                ATCFinding.check_message.ilike(pattern),
                ATCFinding.object_name_raw.ilike(pattern),
            )
        )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    findings = session.scalars(
        base.order_by(ATCFinding.priority.asc().nulls_last(), ATCFinding.source_row_number).offset(offset).limit(limit)
    ).all()
    return ATCFindingListResponse(
        atc_run_id=atc_run.id,
        items=[ATCFindingListItem.model_validate(f) for f in findings],
        total=total,
    )


@router.get("/atc-findings/{finding_id}", response_model=ATCFindingDetailRead)
def get_atc_finding(
    assessment_id: int = Path(...),
    finding_id: int = Path(...),
    session: Session = Depends(get_session),
) -> ATCFindingDetailRead:
    _require_assessment(assessment_id, session)
    finding = session.get(ATCFinding, finding_id)
    if finding is None or finding.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="ATC finding not found")
    return ATCFindingDetailRead.model_validate(finding)
