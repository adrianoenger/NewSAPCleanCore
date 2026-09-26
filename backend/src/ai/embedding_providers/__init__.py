"""Embedding provider registry (ADR-006) — `get_embedding_provider(settings)` is the only
supported way domain code should obtain an `EmbeddingProvider`; it never imports
`ai.embedding_providers.bedrock`/`azure_foundry` directly."""
from __future__ import annotations

from ai.embedding_provider import EmbeddingProvider
from ai.embedding_providers.azure_foundry import AzureFoundryEmbeddingProvider
from ai.embedding_providers.bedrock import BedrockEmbeddingProvider
from settings import Settings

_NAMES = ("bedrock", "azure_foundry")


def get_embedding_provider(settings: Settings, name: str | None = None) -> EmbeddingProvider:
    """Build the configured `EmbeddingProvider`. `name` overrides `settings.embedding_provider`."""
    resolved = name or settings.embedding_provider
    if resolved == "bedrock":
        return BedrockEmbeddingProvider(
            model_id=settings.bedrock_embedding_model_id,
            region=settings.aws_region,
            dimensions=settings.embedding_dimensions,
        )
    if resolved == "azure_foundry":
        if not (
            settings.azure_foundry_endpoint
            and settings.azure_foundry_api_key
            and settings.azure_foundry_embedding_deployment
        ):
            raise ValueError("Azure AI Foundry embeddings are not configured (endpoint/api_key/embedding_deployment)")
        return AzureFoundryEmbeddingProvider(
            endpoint=settings.azure_foundry_endpoint,
            api_key=settings.azure_foundry_api_key,
            deployment=settings.azure_foundry_embedding_deployment,
            dimensions=settings.embedding_dimensions,
        )
    raise ValueError(f"Unknown embedding_provider={resolved!r} (expected one of {_NAMES})")
