"""Azure AI Foundry adapter (ADR-006) — chat completions with a JSON Schema `response_format`,
via the Azure AI Model Inference REST API (OpenAI-compatible `/chat/completions` shape).

No Azure AI Foundry credentials were available at SPRINT-09 implementation time; this adapter
is unit-tested against a mocked HTTP layer only (see `tests/test_ai_providers.py`) — live
validation is explicitly deferred until credentials are configured (see SESSION_HANDOFF.md).
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from ai.provider import AIProviderError, StructuredCompletionRequest, StructuredCompletionResult


class AzureFoundryProvider:
    name = "azure_foundry"

    def __init__(self, endpoint: str, api_key: str, deployment: str, api_version: str = "2024-05-01-preview") -> None:
        self.model_id = deployment
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._api_version = api_version

    def complete_structured(self, request: StructuredCompletionRequest) -> StructuredCompletionResult:
        url = f"{self._endpoint}/chat/completions?api-version={self._api_version}"
        body = {
            "model": self.model_id,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": request.schema_name, "schema": request.json_schema, "strict": True},
            },
        }
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
            raise AIProviderError(f"Azure AI Foundry invocation failed: {exc}") from exc

        output = _extract_message_json(payload)
        if output is None:
            raise AIProviderError("Azure AI Foundry response contained no parseable structured message content")

        return StructuredCompletionResult(
            output=output,
            provider=self.name,
            model_id=self.model_id,
            raw_response=payload,
            stop_reason=(payload.get("choices") or [{}])[0].get("finish_reason"),
        )


def _extract_message_json(payload: dict[str, Any]) -> dict[str, Any] | None:
    choices = payload.get("choices") or []
    if not choices:
        return None
    content = choices[0].get("message", {}).get("content")
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None
