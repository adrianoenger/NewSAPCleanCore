"""AIProvider abstraction (ADR-006).

Domain services depend only on this module — `StructuredCompletionRequest`,
`StructuredCompletionResult`, `AIProvider`, `AIProviderError` — never on `boto3`, the Azure SDK,
or any other provider-specific detail. Concrete adapters live in `ai.providers.*`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class AIProviderError(Exception):
    """Raised by any adapter when a completion cannot be produced.

    Wraps the underlying SDK/HTTP exception so callers never need to catch
    provider-specific error types.
    """


@dataclass(frozen=True)
class StructuredCompletionRequest:
    """A request for a structured, schema-conformant completion.

    `json_schema` is a plain JSON Schema object describing the required output shape;
    `schema_name` names it for providers that require a tool/function name (Bedrock's forced
    tool-use, Azure's `response_format.json_schema.name`).
    """

    system_prompt: str
    user_prompt: str
    json_schema: dict[str, Any]
    schema_name: str
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass(frozen=True)
class StructuredCompletionResult:
    """A completion already parsed into a plain dict conforming (best-effort) to the
    request's `json_schema`. `raw_response` is the full provider response, kept for
    provenance/debugging — never persisted directly as the domain result."""

    output: dict[str, Any]
    provider: str
    model_id: str
    raw_response: dict[str, Any]
    stop_reason: str | None = None


class AIProvider(Protocol):
    """Adapters (Bedrock, Azure AI Foundry, ...) implement this Protocol."""

    name: str
    model_id: str

    def complete_structured(self, request: StructuredCompletionRequest) -> StructuredCompletionResult:
        """Return a structured completion for `request`, or raise `AIProviderError`."""
        ...
