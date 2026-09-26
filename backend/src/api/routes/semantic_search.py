"""Debug API for assessment-scoped semantic search (SPRINT-14, Baseline core rule 14).

Read-only: embeds the query and ranks already-persisted `Embedding` rows. Never mutates
assessment state, and never returns another Assessment's rows (persistence-model.md — "Semantic
retrieval is always Assessment-scoped by default").
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from ai.embedding_providers import get_embedding_provider
from ai.embeddings.search import semantic_search
from api.schemas.semantic_search import SemanticSearchHitRead, SemanticSearchResponse
from persistence.database import get_session
from persistence.models import Assessment
from settings import get_settings

router = APIRouter(prefix="/assessments/{assessment_id}/semantic-search", tags=["semantic-search"])


@router.get("", response_model=SemanticSearchResponse)
def search(
    assessment_id: int = Path(...),
    q: str = Query(..., min_length=1, description="Business concept or free-text query"),
    entity_types: list[str] | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> SemanticSearchResponse:
    if session.get(Assessment, assessment_id) is None:
        raise HTTPException(status_code=404, detail="Assessment not found")

    provider = get_embedding_provider(get_settings())
    hits = semantic_search(session, assessment_id, q, provider, entity_types=entity_types, limit=limit)
    return SemanticSearchResponse(
        assessment_id=assessment_id,
        query=q,
        results=[SemanticSearchHitRead.from_hit(hit) for hit in hits],
    )
