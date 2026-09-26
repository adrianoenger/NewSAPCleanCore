"""Business rule discovery routes — browse rules discovered by the durable pipeline's
`business_rule_discovery` stage (Functional View) plus a user-validation hook.

Discovery itself only happens via the durable pipeline (mirrors parsing.py's own note) —
there is no standalone manual generation endpoint here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.business_rules import (
    BusinessRuleListResponse,
    BusinessRuleRead,
    BusinessRuleValidateRequest,
)
from persistence.database import get_session
from persistence.models import Assessment, BusinessRule, BusinessRuleStatus

router = APIRouter(prefix="/assessments/{assessment_id}", tags=["business-rules"])


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


def _require_rule(assessment_id: int, rule_id: int, session: Session) -> BusinessRule:
    rule = session.get(BusinessRule, rule_id)
    if rule is None or rule.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Business rule not found")
    return rule


@router.get("/business-rules", response_model=BusinessRuleListResponse)
def list_business_rules(
    assessment_id: int = Path(...),
    object_id: int | None = None,
    include_merged: bool = False,
    session: Session = Depends(get_session),
) -> BusinessRuleListResponse:
    """Discovered candidate business rules for the assessment. MERGED duplicates are excluded
    by default — their evidence has already been folded into the surviving row
    (`consolidated_into_id`, see `pipeline/stages.py::_business_rule_discovery_finalize`)."""
    _require_assessment(assessment_id, session)

    q = select(BusinessRule).where(BusinessRule.assessment_id == assessment_id)
    if not include_merged:
        q = q.where(BusinessRule.status == BusinessRuleStatus.CANDIDATE.value)
    if object_id is not None:
        q = q.where(BusinessRule.sap_object_id == object_id)

    rows = list(session.scalars(q.order_by(BusinessRule.confidence.desc(), BusinessRule.id)))
    return BusinessRuleListResponse(
        assessment_id=assessment_id,
        rules=[BusinessRuleRead.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.patch("/business-rules/{rule_id}/validate", response_model=BusinessRuleRead)
def validate_business_rule(
    body: BusinessRuleValidateRequest,
    assessment_id: int = Path(...),
    rule_id: int = Path(...),
    session: Session = Depends(get_session),
) -> BusinessRule:
    """User validation hook (Baseline: distinguish AI interpretation, evidence, user-validated
    and user-corrected content). A validated rule is never overwritten by a later
    reprocessing/consolidation run (`pipeline/stages.py` filters on `user_validated`)."""
    _require_assessment(assessment_id, session)
    rule = _require_rule(assessment_id, rule_id, session)

    rule.user_validated = body.user_validated
    rule.user_notes = body.user_notes
    rule.user_validated_at = datetime.now(timezone.utc) if body.user_validated else None
    session.commit()
    session.refresh(rule)
    return rule
