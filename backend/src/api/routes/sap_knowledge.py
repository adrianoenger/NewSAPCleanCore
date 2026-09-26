"""API routes for SAP knowledge (MCP) guidance — render "SAP Guidance" in a finding/application
detail view (ADR-007). `GET` only reads what was already retrieved; `POST` is the explicit,
user-triggered enrichment call (never automatic/bulk) that queries or reuses cached guidance.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from ai.knowledge_providers import get_knowledge_providers
from ai.knowledge_service import SapKnowledgeTargetNotFound, fetch_guidance, list_guidance
from api.schemas.sap_knowledge import SapKnowledgeGuidanceResponse, SapKnowledgeReferenceRead
from persistence.database import get_session
from persistence.models import Assessment, SapKnowledgeReference, SapKnowledgeTargetType
from settings import get_settings

router = APIRouter(prefix="/assessments/{assessment_id}/sap-knowledge", tags=["sap-knowledge"])

_TARGET_KIND_TO_TYPE = {
    "applications": SapKnowledgeTargetType.APPLICATION.value,
    "business-rules": SapKnowledgeTargetType.BUSINESS_RULE.value,
}


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


def _resolve_target_type(target_kind: str) -> str:
    target_type = _TARGET_KIND_TO_TYPE.get(target_kind)
    if target_type is None:
        raise HTTPException(status_code=404, detail=f"Unknown SAP knowledge target kind '{target_kind}'")
    return target_type


def _to_response(
    assessment_id: int, target_type: str, target_id: int, rows: list[SapKnowledgeReference]
) -> SapKnowledgeGuidanceResponse:
    return SapKnowledgeGuidanceResponse(
        assessment_id=assessment_id,
        target_type=target_type,
        target_id=target_id,
        references=[SapKnowledgeReferenceRead.from_orm_row(r) for r in rows],
    )


@router.get("/{target_kind}/{target_id}", response_model=SapKnowledgeGuidanceResponse)
def get_guidance(
    assessment_id: int = Path(...),
    target_kind: str = Path(...),
    target_id: int = Path(...),
    session: Session = Depends(get_session),
) -> SapKnowledgeGuidanceResponse:
    """Guidance already retrieved for this target — never triggers an MCP call."""
    _require_assessment(assessment_id, session)
    target_type = _resolve_target_type(target_kind)
    rows = list_guidance(session, assessment_id, target_type, target_id)
    return _to_response(assessment_id, target_type, target_id, rows)


@router.post("/{target_kind}/{target_id}", response_model=SapKnowledgeGuidanceResponse)
def request_guidance(
    assessment_id: int = Path(...),
    target_kind: str = Path(...),
    target_id: int = Path(...),
    session: Session = Depends(get_session),
) -> SapKnowledgeGuidanceResponse:
    """Explicit, user-triggered enrichment: query every configured provider for this target,
    reusing a cached equivalent retrieval when one exists."""
    _require_assessment(assessment_id, session)
    target_type = _resolve_target_type(target_kind)
    settings = get_settings()
    providers = get_knowledge_providers(settings)

    try:
        rows = fetch_guidance(session, assessment_id, target_type, target_id, providers)
    except SapKnowledgeTargetNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _to_response(assessment_id, target_type, target_id, rows)
