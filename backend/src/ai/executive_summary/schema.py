"""Executive Summary structured contract (SPRINT-18 CAP-005, ADR-012).

`ExecutiveSummaryResult` is the only shape a provider may return for the `executive_summary`
capability. It is validated before persistence: every cited ref must come from the evidence
package (the assessment catalog) and a COMPLETED summary must have markdown and cite evidence.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ExecutiveSummaryResultStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class ExecutiveSummaryResult(BaseModel):
    status: ExecutiveSummaryResultStatus
    markdown: str = Field(
        default="",
        description="The full executive summary as Markdown (## section headings, bullet lists, bold), in pt-BR.",
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="ref_id values from the context package that ground the summary. Never invent one.",
    )


def validate_result(result: ExecutiveSummaryResult, known_ref_ids: set[str]) -> list[str]:
    """Return domain validation errors; empty means the result may be persisted."""
    errors: list[str] = []
    unknown = sorted(set(result.evidence_refs) - known_ref_ids)
    if unknown:
        errors.append(f"evidence_refs reference ids not present in the context package: {unknown}")
    if result.status == ExecutiveSummaryResultStatus.COMPLETED:
        if not result.markdown.strip():
            errors.append("status=COMPLETED requires a non-empty markdown")
        if not result.evidence_refs:
            errors.append("status=COMPLETED requires at least one evidence_refs entry")
    return errors
