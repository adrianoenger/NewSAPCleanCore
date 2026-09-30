"""Generic MCP client adapter (ADR-007) — connects to a configurable `mcp-sap-docs`/`mcp-abap`
streamable-HTTP endpoint, calls one configured tool, and turns its response into
`KnowledgeReference`s.

SPRINT-18: live-verified against the real public `mcp-sap-docs`/`mcp-abap` hosted instances
(https://github.com/marianfoo/mcp-sap-docs) that its `search` tool's one text content block is a
JSON object `{"results": [{"title", "url", "snippet", ...}, ...]}` — a confirmed, not guessed,
shape (CLAUDE.md forbids guessing an unverified layout, not decoding a verified one).
`_parse_search_results_json` decodes it into one `KnowledgeReference` per result. Any content
block that isn't that exact shape (a different tool, a future provider, a plain-text response)
falls back to the original conservative heuristic: first line becomes the title, the remainder
the summary — never a fabricated field.
"""
from __future__ import annotations

import asyncio
import html
import json
import re

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ai.knowledge_provider import (
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeReference,
    SAPKnowledgeProviderError,
)

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


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

        references: list[KnowledgeReference] = []
        for text in blocks:
            parsed = _parse_search_results_json(self.name, text)
            if parsed is not None:
                references.extend(parsed)
            else:
                references.append(_block_to_reference(self.name, self._tool_name, query.text, text))
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


def _clean_snippet(text: str) -> str:
    """Strip the HTML highlight markup mcp-sap-docs' search results embed in `snippet`
    (e.g. `<b>Clean</b> <b>Core</b>`, `&hellip;`, `&nbsp;`) — never rendered raw to a prompt/UI."""
    return _WHITESPACE.sub(" ", html.unescape(_HTML_TAG.sub("", text))).strip()


def _parse_search_results_json(provider_name: str, text: str) -> list[KnowledgeReference] | None:
    """Decode mcp-sap-docs'/mcp-abap's verified `search` result shape
    (`{"results": [{"title"|"topic", "url", "snippet", ...}, ...]}`).

    Returns `None` — never an empty list — when `text` isn't that shape, so the caller falls back
    to the generic heuristic instead of silently dropping a real (differently-shaped) reference.
    """
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return None

    references: list[KnowledgeReference] = []
    for item in results:
        if not isinstance(item, dict):
            return None  # Not every item matches — this isn't the verified shape; use the fallback.
        title = item.get("title") or item.get("topic") or item.get("id")
        url = item.get("url") or item.get("id")
        if not title or not url:
            return None
        references.append(
            KnowledgeReference(
                title=str(title)[:300],
                reference=str(url)[:500],
                summary=_clean_snippet(str(item.get("snippet", "")))[:2000],
            )
        )
    return references
