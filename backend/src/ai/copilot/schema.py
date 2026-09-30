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


def sanitize_result(result: CopilotAnswerResult, context: CopilotContext) -> CopilotAnswerResult:
    """Drop what cannot be grounded instead of rejecting the whole answer (SPRINT-18 CAP-004).

    Unknown evidence_refs / navigation_ref are removed (never shown as citations), and an
    INSUFFICIENT_CONTEXT answer loses any refs it cited. Rejecting the full answer for one stray ref
    made the Copilot fail on most real questions; the remaining refs are still all context-bound.
    """
    known_ref_ids = {item.ref_id for item in context.items}
    refs = list(dict.fromkeys(ref for ref in result.evidence_refs if ref in known_ref_ids))
    if result.status == CopilotAnswerStatus.INSUFFICIENT_CONTEXT:
        refs = []
    navigation_ref = result.navigation_ref if result.navigation_ref in known_ref_ids else None
    return result.model_copy(update={"evidence_refs": refs, "navigation_ref": navigation_ref})


def validate_result(result: CopilotAnswerResult, context: CopilotContext) -> list[str]:
    """Return domain validation error strings for a sanitized result; empty means it may be returned.

    Only an ANSWERED result without an answer or without a single grounded ref is rejected — a
    claim with zero valid evidence is exactly what ADR-012 forbids presenting as grounded.
    """
    errors: list[str] = []

    known_ref_ids = {item.ref_id for item in context.items}
    unknown_refs = sorted(set(result.evidence_refs) - known_ref_ids)
    if unknown_refs:
        errors.append(f"evidence_refs reference ids not present in the context package: {unknown_refs}")

    if result.status == CopilotAnswerStatus.ANSWERED:
        if not result.answer.strip():
            errors.append("status=ANSWERED requires a non-empty answer")
        if not result.evidence_refs:
            errors.append("status=ANSWERED requires at least one evidence_refs entry present in the context package")

    return errors
