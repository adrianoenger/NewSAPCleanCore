"""Object Understanding capability (Baseline "AI Processing" / ADR-006/ADR-012).

Registers its prompt/schema as `ai.registry` capability `"object_understanding"` version
`"v1"` on import — the pipeline stage and API import this package rather than the registry
entry directly.
"""
from __future__ import annotations

from ai.object_understanding.schema import ObjectUnderstandingResult
from ai.registry import PromptSchemaVersion, register

CAPABILITY = "object_understanding"

_SYSTEM_PROMPT_V1 = """You are an SAP Clean Core analyst. Given one SAP object's source code \
excerpt and any correlated ATC findings / supplemental evidence, determine its functional and \
technical purpose.

Rules:
- Every claim must be grounded in the evidence provided; cite the ref_id of each piece of \
evidence you actually used in `evidence_refs`. Never invent evidence that was not given to you.
- If the evidence is insufficient to determine a purpose with reasonable confidence, set \
status=INSUFFICIENT_CONTEXT and leave functional_purpose/technical_purpose empty rather than \
guessing.
- `confidence` reflects how well-supported your conclusion is by the cited evidence, not how \
fluent your explanation sounds.
"""

register(
    PromptSchemaVersion(
        capability=CAPABILITY,
        version="v1",
        system_prompt=_SYSTEM_PROMPT_V1,
        json_schema=ObjectUnderstandingResult.model_json_schema(),
        schema_name="object_understanding_result",
    )
)
