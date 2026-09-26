"""Application discovery routes — browse discovered custom applications (Architecture View)
and manual rename/move-object/merge actions (Baseline "Application Discovery" / Sprint 11).

Discovery itself only happens via the durable pipeline's `application_discovery` stage (mirrors
business_rules.py's own note) — there is no standalone manual clustering/naming endpoint here.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.applications import (
    ApplicationDetailRead,
    ApplicationFindingRead,
    ApplicationListResponse,
    ApplicationMemberRead,
    ApplicationMergeRequest,
    ApplicationMoveObjectRequest,
    ApplicationMoveObjectResponse,
    ApplicationRead,
    ApplicationRenameRequest,
)
from api.schemas.business_rules import BusinessRuleRead
from api.schemas.clean_core import CleanCoreAssessmentRead
from persistence.database import get_session
from persistence.models import ATCFinding, Application, ApplicationStatus, Assessment, BusinessRule, BusinessRuleStatus, SAPObject

router = APIRouter(prefix="/assessments/{assessment_id}", tags=["applications"])


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


def _require_application(assessment_id: int, application_id: int, session: Session) -> Application:
    app = session.get(Application, application_id)
    if app is None or app.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def _members(session: Session, application_id: int) -> list[SAPObject]:
    return list(session.scalars(select(SAPObject).where(SAPObject.application_id == application_id)))


def _to_read(app: Application, members: list[SAPObject]) -> ApplicationRead:
    return ApplicationRead(
        id=app.id,
        assessment_id=app.assessment_id,
        name=app.name,
        description=app.description,
        domain=app.domain,
        confidence=app.confidence,
        rationale=app.rationale,
        evidence_refs=app.evidence_refs,
        clustering_signals=app.clustering_signals,
        status=app.status,
        consolidated_into_id=app.consolidated_into_id,
        provider=app.provider,
        model_id=app.model_id,
        prompt_capability=app.prompt_capability,
        prompt_version=app.prompt_version,
        error=app.error,
        created_at=app.created_at,
        updated_at=app.updated_at,
        member_count=len(members),
        members=[ApplicationMemberRead.model_validate(m) for m in members],
        clean_core=CleanCoreAssessmentRead.model_validate(app.clean_core_assessment) if app.clean_core_assessment else None,
    )


@router.get("/applications", response_model=ApplicationListResponse)
def list_applications(
    assessment_id: int = Path(...),
    include_merged: bool = False,
    session: Session = Depends(get_session),
) -> ApplicationListResponse:
    """Discovered candidate applications for the assessment. MERGED-away applications are
    excluded by default — their members have already been reassigned to the surviving
    application (`consolidated_into_id`). An application left with zero members (every object
    moved elsewhere) is never shown — it has nothing left to browse."""
    _require_assessment(assessment_id, session)

    q = select(Application).where(Application.assessment_id == assessment_id)
    if not include_merged:
        q = q.where(Application.status != ApplicationStatus.MERGED.value)

    apps = list(session.scalars(q.order_by(Application.id)))
    reads = []
    for app in apps:
        members = _members(session, app.id)
        if not members and not include_merged:
            continue
        reads.append(_to_read(app, members))

    return ApplicationListResponse(assessment_id=assessment_id, applications=reads, total=len(reads))


@router.get("/applications/{application_id}", response_model=ApplicationDetailRead)
def get_application(
    assessment_id: int = Path(...),
    application_id: int = Path(...),
    session: Session = Depends(get_session),
) -> ApplicationDetailRead:
    """Application detail: its objects, the candidate business rules discovered for those
    objects, correlated ATC findings, and the AI's confidence/rationale — all traceable back to
    Assessment evidence (ADR-008)."""
    _require_assessment(assessment_id, session)
    app = _require_application(assessment_id, application_id, session)
    members = _members(session, app.id)
    member_ids = [m.id for m in members]

    rules = list(
        session.scalars(
            select(BusinessRule).where(
                BusinessRule.sap_object_id.in_(member_ids), BusinessRule.status == BusinessRuleStatus.CANDIDATE.value
            )
        )
        if member_ids
        else []
    )
    findings_rows = list(
        session.scalars(select(ATCFinding).where(ATCFinding.correlated_object_id.in_(member_ids)))
        if member_ids
        else []
    )
    objects_by_id = {m.id: m for m in members}

    base = _to_read(app, members)
    return ApplicationDetailRead(
        **base.model_dump(),
        business_rules=[BusinessRuleRead.model_validate(r) for r in rules],
        findings=[
            ApplicationFindingRead(
                id=f.id,
                object_id=f.correlated_object_id,
                object_name=objects_by_id[f.correlated_object_id].object_name,
                check_title=f.check_title,
                check_message=f.check_message,
            )
            for f in findings_rows
        ],
    )


@router.patch("/applications/{application_id}", response_model=ApplicationRead)
def rename_application(
    body: ApplicationRenameRequest,
    assessment_id: int = Path(...),
    application_id: int = Path(...),
    session: Session = Depends(get_session),
) -> ApplicationRead:
    """Manual rename/description edit (Baseline: distinguish AI interpretation from
    user-corrected content). A renamed application is never overwritten by a later
    reprocessing run (`pipeline/stages.py` skips USER_RENAMED applications)."""
    _require_assessment(assessment_id, session)
    app = _require_application(assessment_id, application_id, session)
    if app.status == ApplicationStatus.MERGED.value:
        raise HTTPException(status_code=409, detail="Cannot rename an application that was merged away")

    if body.name is not None:
        app.name = body.name
    if body.description is not None:
        app.description = body.description
    app.status = ApplicationStatus.USER_RENAMED.value
    session.commit()
    session.refresh(app)
    return _to_read(app, _members(session, app.id))


@router.post("/applications/move-object", response_model=ApplicationMoveObjectResponse)
def move_object(
    body: ApplicationMoveObjectRequest,
    assessment_id: int = Path(...),
    session: Session = Depends(get_session),
) -> ApplicationMoveObjectResponse:
    """Manually move one SAPObject to a different application, or to none (`target_application_id
    = null`) — the durable pipeline's reconciliation never re-groups a user-curated application,
    but it also never automatically re-groups an object moved out of one, until the user acts
    again."""
    _require_assessment(assessment_id, session)
    obj = session.get(SAPObject, body.object_id)
    if obj is None or obj.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="SAP object not found")

    target: Application | None = None
    if body.target_application_id is not None:
        target = _require_application(assessment_id, body.target_application_id, session)
        if target.status == ApplicationStatus.MERGED.value:
            raise HTTPException(status_code=409, detail="Cannot move an object into an application that was merged away")

    obj.application_id = target.id if target is not None else None
    session.commit()

    if target is None:
        return ApplicationMoveObjectResponse(object_id=obj.id, application=None)
    session.refresh(target)
    return ApplicationMoveObjectResponse(object_id=obj.id, application=_to_read(target, _members(session, target.id)))


@router.post("/applications/merge", response_model=ApplicationRead)
def merge_applications(
    body: ApplicationMergeRequest,
    assessment_id: int = Path(...),
    session: Session = Depends(get_session),
) -> ApplicationRead:
    """Manually merge one application into another: the target absorbs the source's members;
    the source is marked MERGED with `consolidated_into_id` pointing at the survivor, mirroring
    `BusinessRule`'s own consolidation pattern rather than being deleted outright."""
    _require_assessment(assessment_id, session)
    if body.source_application_id == body.target_application_id:
        raise HTTPException(status_code=400, detail="Cannot merge an application into itself")

    source = _require_application(assessment_id, body.source_application_id, session)
    target = _require_application(assessment_id, body.target_application_id, session)
    if source.status == ApplicationStatus.MERGED.value or target.status == ApplicationStatus.MERGED.value:
        raise HTTPException(status_code=409, detail="Cannot merge an application that was already merged away")

    for obj in _members(session, source.id):
        obj.application_id = target.id

    seen_refs = {(r.get("ref_id"), r.get("source_type"), r.get("entity_id")) for r in target.evidence_refs}
    for ref in source.evidence_refs:
        key = (ref.get("ref_id"), ref.get("source_type"), ref.get("entity_id"))
        if key not in seen_refs:
            target.evidence_refs = [*target.evidence_refs, ref]
            seen_refs.add(key)

    source.status = ApplicationStatus.MERGED.value
    source.consolidated_into_id = target.id
    session.commit()
    session.refresh(target)
    return _to_read(target, _members(session, target.id))
