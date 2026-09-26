"""EmbeddingProvider abstraction (ADR-006, mirroring `ai.provider`).

Domain services depend only on this module — `EmbeddingRequest`, `EmbeddingResult`,
`EmbeddingProvider`, `EmbeddingProviderError` — never on `boto3`, the Azure SDK, or any other
provider-specific detail. Concrete adapters live in `ai.embedding_providers.*`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class EmbeddingProviderError(Exception):
    """Raised by any adapter when embeddings cannot be produced.

    Wraps the underlying SDK/HTTP exception so callers never need to catch
    provider-specific error types.
    """


@dataclass(frozen=True)
class EmbeddingRequest:
    """A request to embed one or more texts with the same provider/model."""

    texts: list[str]


@dataclass(frozen=True)
class EmbeddingResult:
    """`vectors[i]` is the embedding for `request.texts[i]` — order preserved."""

    vectors: list[list[float]]
    provider: str
    model_id: str
    dimensions: int


class EmbeddingProvider(Protocol):
    """Adapters (Bedrock, Azure AI Foundry, ...) implement this Protocol."""

    name: str
    model_id: str
    dimensions: int

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        """Return embeddings for `request.texts`, or raise `EmbeddingProviderError`."""
        ...
