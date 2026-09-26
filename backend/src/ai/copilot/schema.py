"""Copilot structured contract (ADR-012, ADR-010).

`CopilotAnswerResult` is the only shape a provider may return for the `copilot` capability.
Unlike the batch pipeline capabilities (object_understanding, business_rule_discovery, ...), a
Copilot answer is never persisted — it is validated once, per request, before being returned to
the user, so it never presents an unfounded claim or a hallucinated navigation target as if it
were grounded (ADR-010: the Copilot "never mutates assessment state", and by the same logic it
must never assert evidence it was not actually given).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ai.copilot.context import CopilotContext


class CopilotAnswerStatus(str, Enum):
    ANSWERED = "ANSWERED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class CopilotAnswerResult(BaseModel):
    status: CopilotAnswerStatus
    answer: str = Field(
        default="", description="Plain-language answer. Empty only if status=INSUFFICIENT_CONTEXT and there is nothing useful to say."
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="ref_id values from the context package actually used to ground the answer. Never invent one.",
    )
    navigation_ref: str | None = Field(
        default=None,
        description=(
            "Optional ref_id (from the context package) of the single entity the user should navigate to next "
            "for more detail — only set this when a context item is genuinely the best next step, never guess an id."
        ),
    )


def validate_result(result: CopilotAnswerResult, context: CopilotContext) -> list[str]:
    """Return domain validation error strings; empty means the result may be returned to the user."""
    errors: list[str] = []

    known_ref_ids = {item.ref_id for item in context.items}
    unknown_refs = sorted(set(result.evidence_refs) - known_ref_ids)
    if unknown_refs:
        errors.append(f"evidence_refs reference ids not present in the context package: {unknown_refs}")

    if result.navigation_ref is not None and result.navigation_ref not in known_ref_ids:
        errors.append(f"navigation_ref {result.navigation_ref!r} not present in the context package")

    if result.status == CopilotAnswerStatus.ANSWERED:
        if not result.answer.strip():
            errors.append("status=ANSWERED requires a non-empty answer")
        if not result.evidence_refs:
            errors.append("status=ANSWERED requires at least one evidence_refs entry")
    else:
        if result.evidence_refs:
            errors.append("status=INSUFFICIENT_CONTEXT must not cite evidence_refs")

    return errors
