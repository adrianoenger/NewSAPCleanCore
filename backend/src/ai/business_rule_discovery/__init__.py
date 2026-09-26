"""Business Rule Discovery capability (Baseline "AI Processing" / ADR-008/ADR-012).

Registers its prompt/schema as `ai.registry` capability `"business_rule_discovery"` version
`"v1"` on import — the pipeline stage and API import this package rather than the registry
entry directly.
"""
from __future__ import annotations

from ai.business_rule_discovery.schema import BusinessRuleDiscoveryResult
from ai.registry import PromptSchemaVersion, register

CAPABILITY = "business_rule_discovery"

_SYSTEM_PROMPT_V1 = """You are an SAP Clean Core analyst extracting explicit business rules from \
one SAP object. You are given the object's persisted functional/technical understanding as \
context, plus its source code excerpt and any correlated ATC findings / supplemental evidence as \
citable evidence.

Rules:
- A business rule has a condition (when it applies) and an action (what happens/is enforced). \
Only report rules that are explicit in the evidence — e.g. a validation check, an authorization \
gate, a calculation/derivation, a workflow branch — never a rule you inferred solely from the \
persisted understanding's narrative without evidence to back it.
- Every rule must cite the ref_id of each piece of evidence that actually grounds it in \
evidence_refs. Never invent evidence that was not given to you, and never cite the persisted \
understanding itself (it is interpretation, not evidence).
- If this object has no explicit business rule, return status=COMPLETED with an empty rules list \
rather than fabricating one.
- If the evidence is too limited to tell either way, set status=INSUFFICIENT_CONTEXT and leave \
rules empty rather than guessing.
- `confidence` reflects how well-supported each rule is by its cited evidence, not how fluent the \
description sounds.
"""

register(
    PromptSchemaVersion(
        capability=CAPABILITY,
        version="v1",
        system_prompt=_SYSTEM_PROMPT_V1,
        json_schema=BusinessRuleDiscoveryResult.model_json_schema(),
        schema_name="business_rule_discovery_result",
    )
)
