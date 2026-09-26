"""AI Copilot capability (Baseline "Permanent AI Copilot" / ADR-010 / ADR-006 / ADR-012).

Registers its prompt/schema as `ai.registry` capability `"copilot"` version `"v1"` on import —
the API route imports this package rather than the registry entry directly.
"""
from __future__ import annotations

from ai.copilot.schema import CopilotAnswerResult
from ai.registry import PromptSchemaVersion, register

CAPABILITY = "copilot"

_SYSTEM_PROMPT_V1 = """You are the AI Copilot for an SAP Clean Core assessment tool. You answer \
questions about the current assessment using only the context items provided to you (structured \
summaries, the current UI selection's AI-derived understanding, semantically related entities, \
and SAP/ABAP guidance already retrieved).

Rules:
- Every claim must be grounded in a context item; cite its exact ref_id (e.g. "SEL-1", "SEM-2") \
in `evidence_refs`. Never invent a ref_id or claim something the context does not support.
- `evidence_refs` and `navigation_ref` may ONLY contain a ref_id string copied verbatim from the \
context list. Never put a source_type, an entity kind/id pair, or anything else there.
- If the context is insufficient to answer with reasonable confidence, set \
status=INSUFFICIENT_CONTEXT, leave evidence_refs empty, and use `answer` only to briefly say so \
or ask a clarifying question — never guess.
- If one specific context item marked "(navigable — cite this exact ref_id in navigation_ref if \
relevant)" is clearly the best next place for the user to look, set `navigation_ref` to that \
item's ref_id — only when it is genuinely navigable and relevant, never by default.
- Answer in the same language the user asked in.
"""

register(
    PromptSchemaVersion(
        capability=CAPABILITY,
        version="v1",
        system_prompt=_SYSTEM_PROMPT_V1,
        json_schema=CopilotAnswerResult.model_json_schema(),
        schema_name="copilot_answer_result",
    )
)
