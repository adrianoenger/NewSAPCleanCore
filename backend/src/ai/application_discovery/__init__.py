"""Application Discovery capability (Baseline "AI Processing" / ADR-008/ADR-012).

Registers its prompt/schema as `ai.registry` capability `"application_discovery"` version
`"v1"` on import — the pipeline stage and API import this package rather than the registry
entry directly.
"""
from __future__ import annotations

from ai.application_discovery.schema import ApplicationDiscoveryResult
from ai.registry import PromptSchemaVersion, register

CAPABILITY = "application_discovery"

_SYSTEM_PROMPT_V1 = """You are an SAP Clean Core analyst naming a candidate custom application — \
a cluster of SAP objects already grouped by deterministic signals (dependencies, shared package, \
shared concepts) given to you as context. Each member's persisted understanding and discovered \
business rules are also given as context — they are prior AI interpretation, not evidence.

Rules:
- Propose a short, business-facing `name`, a plain-language `description` of what this \
application does, and its functional/business `domain` (e.g. "Order Management", "Pricing").
- Ground your rationale in the deterministic clustering signals and the cited evidence_refs — \
never invent evidence that was not given to you, and never cite the persisted understanding or \
business rules themselves (they are interpretation, not evidence).
- If the cluster is too sparse or unrelated to name/describe with reasonable confidence, set \
status=INSUFFICIENT_CONTEXT and leave name/description/domain empty rather than guessing.
- `confidence` reflects how well-supported the grouping and name are by the cited evidence and \
clustering signals, not how fluent the description sounds.
"""

register(
    PromptSchemaVersion(
        capability=CAPABILITY,
        version="v1",
        system_prompt=_SYSTEM_PROMPT_V1,
        json_schema=ApplicationDiscoveryResult.model_json_schema(),
        schema_name="application_discovery_result",
    )
)
