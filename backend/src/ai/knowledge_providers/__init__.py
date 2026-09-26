"""Knowledge provider registry (ADR-007) — `get_knowledge_providers(settings)` is the only
supported way domain code should obtain the configured `SAPKnowledgeProvider`s; it never imports
`ai.knowledge_providers.mcp_client` for a provider name directly.

Each provider is optional: an assessment/PoC environment may have no local `mcp-sap-docs`/
`mcp-abap` Docker container running, and ADR-007 does not require both — an unconfigured
endpoint is simply skipped rather than raising, so the rest of the application stays runnable.
"""
from __future__ import annotations

from ai.knowledge_provider import SAPKnowledgeProvider
from ai.knowledge_providers.mcp_client import MCPKnowledgeProvider
from settings import Settings


def get_knowledge_providers(settings: Settings) -> list[SAPKnowledgeProvider]:
    providers: list[SAPKnowledgeProvider] = []
    if settings.sap_docs_mcp_endpoint:
        providers.append(
            MCPKnowledgeProvider(
                name="sap_docs_mcp",
                endpoint=settings.sap_docs_mcp_endpoint,
                tool_name=settings.sap_docs_mcp_tool_name,
            )
        )
    if settings.abap_mcp_endpoint:
        providers.append(
            MCPKnowledgeProvider(
                name="abap_mcp",
                endpoint=settings.abap_mcp_endpoint,
                tool_name=settings.abap_mcp_tool_name,
            )
        )
    return providers
