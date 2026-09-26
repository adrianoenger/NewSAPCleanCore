"""Azure AI Foundry embedding adapter (ADR-006) — OpenAI-compatible `/embeddings` endpoint.

No Azure AI Foundry credentials were available at implementation time (mirrors the
`ai.providers.azure_foundry` structured-completion adapter's own precedent since SPRINT-09/12);
this adapter is unit-tested against a mocked HTTP layer only — live validation is deferred until
credentials are configured.
"""
from __future__ import annotations

import json

import httpx

from ai.embedding_provider import EmbeddingProviderError, EmbeddingRequest, EmbeddingResult


class AzureFoundryEmbeddingProvider:
    name = "azure_foundry"

    def __init__(
        self, endpoint: str, api_key: str, deployment: str, dimensions: int, api_version: str = "2024-05-01-preview"
    ) -> None:
        self.model_id = deployment
        self.dimensions = dimensions
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._api_version = api_version

    def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        url = f"{self._endpoint}/embeddings?api-version={self._api_version}"
        body = {"model": self.model_id, "input": request.texts}
        try:
            response = httpx.post(
                url,
                json=body,
                headers={"api-key": self._api_key, "Content-Type": "application/json"},
                timeout=60.0,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise EmbeddingProviderError(f"Azure AI Foundry embedding invocation failed: {exc}") from exc

        data = payload.get("data")
        if not isinstance(data, list) or not data:
            raise EmbeddingProviderError("Azure AI Foundry embedding response contained no 'data' array")

        vectors = [item["embedding"] for item in sorted(data, key=lambda item: item.get("index", 0))]
        return EmbeddingResult(vectors=vectors, provider=self.name, model_id=self.model_id, dimensions=self.dimensions)
