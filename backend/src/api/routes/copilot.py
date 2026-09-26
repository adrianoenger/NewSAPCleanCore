"""AI Copilot route (SPRINT-16, ADR-010) — the only endpoint behind the permanent right-side
Copilot panel. Read-only: never mutates assessment state, never persists the conversation (the
frontend keeps it in the always-mounted CopilotPanel's own state).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ai.copilot import CAPABILITY as COPILOT_CAPABILITY
from ai.copilot.context import CopilotSelection, build_context, render_prompt
from ai.copilot.schema import CopilotAnswerResult, validate_result
from ai.embedding_providers import get_embedding_provider
from ai.provider import AIProviderError, StructuredCompletionRequest
from ai.providers import get_provider
from ai.registry import get_version
from api.schemas.copilot import (
    CopilotAskRequest,
    CopilotAskResponse,
    CopilotNavigationRead,
    CopilotReferenceRead,
)
from persistence.database import get_session
from persistence.models import Assessment
from settings import get_settings

router = APIRouter(prefix="/assessments/{assessment_id}/copilot", tags=["copilot"])

_MAX_HISTORY_TURNS = 10


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


@router.post("/ask", response_model=CopilotAskResponse)
def ask(
    body: CopilotAskRequest,
    assessment_id: int = Path(...),
    session: Session = Depends(get_session),
) -> CopilotAskResponse:
    _require_assessment(assessment_id, session)

    selection = (
        CopilotSelection(kind=body.selection.kind, id=body.selection.id) if body.selection is not None else None
    )
    settings = get_settings()
    embedding_provider = get_embedding_provider(settings)
    context = build_context(session, assessment_id, body.view, selection, body.question, embedding_provider)
    history = [(turn.role, turn.content) for turn in body.history[-_MAX_HISTORY_TURNS:]]

    prompt_version = get_version(COPILOT_CAPABILITY)
    provider = get_provider(settings)

    # ADR-012: schema, evidence-reference and domain rules are validated before the answer is
    # ever returned. A provider/validation failure is a legitimate outcome for one question, not
    # a server error — it is returned as status=FAILED so the Copilot can show a graceful message
    # rather than a broken request.
    try:
        completion = provider.complete_structured(
            StructuredCompletionRequest(
                system_prompt=prompt_version.system_prompt,
                user_prompt=render_prompt(context, body.question, history),
                json_schema=prompt_version.json_schema,
                schema_name=prompt_version.schema_name,
            )
        )
        result = CopilotAnswerResult.model_validate(completion.output)
        domain_errors = validate_result(result, context)
        if domain_errors:
            raise AIProviderError(f"Domain validation failed: {'; '.join(domain_errors)}")
    except (AIProviderError, ValidationError) as exc:
        return CopilotAskResponse(status="FAILED", answer="", references=[], navigation=None, error=str(exc)[:2000])

    items_by_ref = {item.ref_id: item for item in context.items}
    references = [
        CopilotReferenceRead(
            ref_id=ref_id,
            source_type=items_by_ref[ref_id].source_type,
            entity_id=items_by_ref[ref_id].entity_id,
            summary=items_by_ref[ref_id].summary,
        )
        for ref_id in result.evidence_refs
        if ref_id in items_by_ref
    ]

    navigation = None
    if result.navigation_ref is not None:
        nav_item = items_by_ref.get(result.navigation_ref)
        if nav_item is not None and nav_item.navigation is not None:
            navigation = CopilotNavigationRead(kind=nav_item.navigation.kind, id=nav_item.navigation.id)

    return CopilotAskResponse(
        status=result.status.value,
        answer=result.answer,
        references=references,
        navigation=navigation,
        error=None,
    )
