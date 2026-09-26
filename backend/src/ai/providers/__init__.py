"""Provider registry (ADR-006) — `get_provider(name)` is the only supported way domain code
should obtain an `AIProvider`; it never imports `ai.providers.bedrock`/`azure_foundry` directly."""
from __future__ import annotations

from ai.provider import AIProvider
from ai.providers.azure_foundry import AzureFoundryProvider
from ai.providers.bedrock import BedrockProvider
from settings import Settings

_NAMES = ("bedrock", "azure_foundry")


def get_provider(settings: Settings, name: str | None = None) -> AIProvider:
    """Build the configured `AIProvider`. `name` overrides `settings.llm_provider`."""
    resolved = name or settings.llm_provider
    if resolved == "bedrock":
        return BedrockProvider(model_id=settings.bedrock_model_id, region=settings.aws_region)
    if resolved == "azure_foundry":
        if not (settings.azure_foundry_endpoint and settings.azure_foundry_api_key and settings.azure_foundry_deployment):
            raise ValueError("Azure AI Foundry is not configured (endpoint/api_key/deployment)")
        return AzureFoundryProvider(
            endpoint=settings.azure_foundry_endpoint,
            api_key=settings.azure_foundry_api_key,
            deployment=settings.azure_foundry_deployment,
        )
    raise ValueError(f"Unknown llm_provider={resolved!r} (expected one of {_NAMES})")
