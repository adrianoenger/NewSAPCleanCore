"""Object Understanding structured contract (ADR-012).

`ObjectUnderstandingResult` is the only shape a provider is allowed to return for this
capability (enforced via `ai.registry` + forced structured completion). `validate_result`
enforces the domain/evidence-binding rules a schema-valid-but-unfounded response could still
violate: a COMPLETED result must cite real evidence and say something, an INSUFFICIENT_CONTEXT
result must not assert a purpose it has no basis for (ADR-012 — "allow insufficient-context
results rather than forced conclusions").
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ai.object_understanding.evidence_package import ObjectEvidencePackage


class ObjectUnderstandingStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class ObjectUnderstandingResult(BaseModel):
    status: ObjectUnderstandingStatus
    functional_purpose: str = Field(
        default="", description="Business/functional purpose in plain language. Empty if status=INSUFFICIENT_CONTEXT."
    )
    technical_purpose: str = Field(
        default="", description="Technical role/behavior of the object. Empty if status=INSUFFICIENT_CONTEXT."
    )
    concepts: list[str] = Field(
        default_factory=list, description="Short business/technical concept tags, e.g. 'pricing', 'batch job'."
    )
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(default="", description="Brief justification citing evidence_refs.")
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="ref_id values (e.g. 'SRC-1', 'ATC-3', 'EVD-7') from the evidence package actually used.",
    )


def validate_result(result: ObjectUnderstandingResult, package: ObjectEvidencePackage) -> list[str]:
    """Return domain validation error strings; empty means the result may be persisted."""
    errors: list[str] = []

    known_ref_ids = {item.ref_id for item in package.all_items()}
    unknown_refs = sorted(set(result.evidence_refs) - known_ref_ids)
    if unknown_refs:
        errors.append(f"evidence_refs reference ids not present in the evidence package: {unknown_refs}")

    if result.status == ObjectUnderstandingStatus.COMPLETED:
        if not result.functional_purpose.strip() and not result.technical_purpose.strip():
            errors.append("status=COMPLETED requires at least one of functional_purpose/technical_purpose")
        if not result.evidence_refs:
            errors.append("status=COMPLETED requires at least one evidence_refs entry")
    elif result.functional_purpose.strip() or result.technical_purpose.strip():
        errors.append("status=INSUFFICIENT_CONTEXT must not assert functional_purpose/technical_purpose")

    return errors
