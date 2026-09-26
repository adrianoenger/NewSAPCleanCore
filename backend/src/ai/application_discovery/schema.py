"""Application Discovery structured contract (ADR-008/ADR-012).

`ApplicationDiscoveryResult` is the only shape a provider is allowed to return for this
capability. `validate_result` enforces the evidence-binding rules a schema-valid-but-unfounded
response could still violate: a COMPLETED result must name the application and cite real
evidence (ADR-008 — AI output alone is not authoritative evidence); an INSUFFICIENT_CONTEXT
result must not assert a name/description/domain it has no basis for (ADR-012 — "allow
insufficient-context results rather than forced conclusions").
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ai.application_discovery.evidence_package import ApplicationEvidencePackage


class ApplicationDiscoveryStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class ApplicationDiscoveryResult(BaseModel):
    status: ApplicationDiscoveryStatus
    name: str = Field(
        default="", description="Short business-facing application name. Empty if status=INSUFFICIENT_CONTEXT."
    )
    description: str = Field(
        default="",
        description="Plain-language description of what this application does. Empty if status=INSUFFICIENT_CONTEXT.",
    )
    domain: str = Field(
        default="",
        description="Functional/business domain, e.g. 'Order Management'. Empty if status=INSUFFICIENT_CONTEXT.",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(
        default="", description="Brief justification citing evidence_refs and the clustering signals."
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="ref_id values (e.g. 'OBJ-3', 'DEP-7', 'ATC-2', 'EVD-9') from the evidence package actually used.",
    )


def validate_result(result: ApplicationDiscoveryResult, package: ApplicationEvidencePackage) -> list[str]:
    """Return domain validation error strings; empty means the result may be persisted."""
    errors: list[str] = []

    known_ref_ids = {item.ref_id for item in package.all_items()}
    unknown_refs = sorted(set(result.evidence_refs) - known_ref_ids)
    if unknown_refs:
        errors.append(f"evidence_refs reference ids not present in the evidence package: {unknown_refs}")

    if result.status == ApplicationDiscoveryStatus.COMPLETED:
        if not result.name.strip():
            errors.append("status=COMPLETED requires a non-empty name")
        if not result.evidence_refs:
            errors.append("status=COMPLETED requires at least one evidence_refs entry")
    elif result.name.strip() or result.description.strip() or result.domain.strip():
        errors.append("status=INSUFFICIENT_CONTEXT must not assert name/description/domain")

    return errors
