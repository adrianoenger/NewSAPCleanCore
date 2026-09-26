"""Assessment-scoped semantic search service (Baseline core rule 14, persistence-model.md
"Semantic retrieval is always Assessment-scoped by default").

Embeds the query text with the same configured `EmbeddingProvider` used to build the index, then
ranks `Embedding` rows by pgvector cosine distance — always filtered by `assessment_id` so a
search can never leak another Assessment's rules/applications/objects/process evidence.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.embedding_provider import EmbeddingProvider, EmbeddingRequest
from persistence.models import Embedding


@dataclass(frozen=True)
class SemanticSearchHit:
    entity_type: str
    entity_id: int
    content_text: str
    metadata: dict
    score: float  # cosine similarity in [-1, 1]; higher is more relevant


def semantic_search(
    session: Session,
    assessment_id: int,
    query_text: str,
    provider: EmbeddingProvider,
    *,
    entity_types: list[str] | None = None,
    limit: int = 10,
) -> list[SemanticSearchHit]:
    result = provider.embed(EmbeddingRequest(texts=[query_text]))
    query_vector = result.vectors[0]

    distance = Embedding.vector.cosine_distance(query_vector)
    stmt = select(Embedding, distance.label("distance")).where(Embedding.assessment_id == assessment_id)
    if entity_types:
        stmt = stmt.where(Embedding.entity_type.in_(entity_types))
    stmt = stmt.order_by(distance).limit(limit)

    return [
        SemanticSearchHit(
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            content_text=row.content_text,
            metadata=row.entity_metadata,
            score=1.0 - dist,
        )
        for row, dist in session.execute(stmt).all()
    ]
