"""Pydantic schemas for the semantic search debug endpoint (SPRINT-14)."""
from __future__ import annotations

from pydantic import BaseModel

from ai.embeddings.search import SemanticSearchHit


class SemanticSearchHitRead(BaseModel):
    entity_type: str
    entity_id: int
    content_text: str
    metadata: dict
    score: float

    @classmethod
    def from_hit(cls, hit: SemanticSearchHit) -> "SemanticSearchHitRead":
        return cls(
            entity_type=hit.entity_type,
            entity_id=hit.entity_id,
            content_text=hit.content_text,
            metadata=hit.metadata,
            score=hit.score,
        )


class SemanticSearchResponse(BaseModel):
    assessment_id: int
    query: str
    results: list[SemanticSearchHitRead]
