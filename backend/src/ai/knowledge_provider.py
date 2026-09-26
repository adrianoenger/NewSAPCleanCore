"""SAPKnowledgeProvider abstraction (ADR-007).

Domain services depend only on this module — `KnowledgeQuery`, `KnowledgeReference`,
`KnowledgeQueryResult`, `SAPKnowledgeProvider`, `SAPKnowledgeProviderError` — never on the `mcp`
SDK's transport details directly. Concrete adapters live in `ai.knowledge_providers.*`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SAPKnowledgeProviderError(Exception):
    """Raised by any adapter when a knowledge query cannot be answered.

    Wraps the underlying MCP transport/tool exception so callers never need to catch
    provider-specific error types.
    """


@dataclass(frozen=True)
class KnowledgeQuery:
    """A contextual request for SAP/ABAP guidance — never a free-text search unrelated to a
    specific finding/application (ADR-007: contextual enrichment, not indiscriminate RAG)."""

    text: str
    max_results: int = 3


@dataclass(frozen=True)
class KnowledgeReference:
    """One retrieved piece of guidance. `reference` is a locator back to the MCP tool/content that
    produced it — never a fabricated document URL/ID we cannot stand behind."""

    title: str
    reference: str
    summary: str


@dataclass(frozen=True)
class KnowledgeQueryResult:
    provider: str
    references: list[KnowledgeReference]


class SAPKnowledgeProvider(Protocol):
    """Adapters (mcp-sap-docs, mcp-abap, ...) implement this Protocol."""

    name: str

    def query(self, query: KnowledgeQuery) -> KnowledgeQueryResult:
        """Return guidance for `query`, or raise `SAPKnowledgeProviderError`."""
        ...
