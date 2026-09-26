"""Generic MCP client adapter (ADR-007) — connects to a configurable `mcp-sap-docs`/`mcp-abap`
streamable-HTTP endpoint, calls one configured tool, and turns its response into
`KnowledgeReference`s.

We deliberately do not assume a project-specific result shape (`title`/`url`/`summary` fields):
neither `mcp-sap-docs` nor `mcp-abap` publish a stable structured-content schema, and guessing one
would be exactly the kind of unverified layout decoding CLAUDE.md forbids for imported evidence.
Instead each returned MCP content block is treated as one reference: its first line becomes the
title, the remainder becomes the summary, and `reference` records the provider/tool/query that
produced it — honest about what we actually retrieved rather than fabricated metadata.
"""
from __future__ import annotations

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ai.knowledge_provider import (
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeReference,
    SAPKnowledgeProviderError,
)


class MCPKnowledgeProvider:
    """A `SAPKnowledgeProvider` backed by one MCP tool on one streamable-HTTP endpoint."""

    def __init__(self, name: str, endpoint: str, tool_name: str, query_arg: str = "query") -> None:
        self.name = name
        self._endpoint = endpoint
        self._tool_name = tool_name
        self._query_arg = query_arg

    def query(self, query: KnowledgeQuery) -> KnowledgeQueryResult:
        try:
            blocks = asyncio.run(self._call_tool(query))
        except SAPKnowledgeProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 — any transport/protocol failure becomes one error type
            raise SAPKnowledgeProviderError(f"{self.name} MCP call failed: {exc}") from exc

        references = [_block_to_reference(self.name, self._tool_name, query.text, text) for text in blocks]
        return KnowledgeQueryResult(provider=self.name, references=references[: query.max_results])

    async def _call_tool(self, query: KnowledgeQuery) -> list[str]:
        async with streamable_http_client(self._endpoint) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(self._tool_name, {self._query_arg: query.text})

        if result.is_error:
            raise SAPKnowledgeProviderError(f"{self.name} tool '{self._tool_name}' returned an error result")

        return [block.text for block in result.content if getattr(block, "type", None) == "text"]


def _block_to_reference(provider_name: str, tool_name: str, query_text: str, text: str) -> KnowledgeReference:
    first_line, _, rest = text.strip().partition("\n")
    return KnowledgeReference(
        title=first_line[:300] or f"{provider_name} result",
        reference=f"mcp://{provider_name}/{tool_name}?query={query_text[:200]}",
        summary=rest.strip()[:2000],
    )
