"""Business Rule Discovery structured contract (ADR-008/ADR-012).

`BusinessRuleDiscoveryResult` is the only shape a provider is allowed to return for this
capability. `validate_result` enforces the evidence-binding rules a schema-valid-but-unfounded
response could still violate: every candidate rule must cite real evidence (ADR-008 — AI output
alone is not authoritative evidence) and an INSUFFICIENT_CONTEXT result must not smuggle in rules
it has no basis for (ADR-012). A COMPLETED result with zero rules is a valid outcome — "reviewed,
no explicit business rule found" — rather than forcing the model to fabricate one.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ai.business_rule_discovery.evidence_package import BusinessRuleEvidencePackage


class BusinessRuleDiscoveryStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class BusinessRuleType(str, Enum):
    VALIDATION = "VALIDATION"
    CALCULATION = "CALCULATION"
    AUTHORIZATION = "AUTHORIZATION"
    WORKFLOW = "WORKFLOW"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    OTHER = "OTHER"


class BusinessRuleCandidate(BaseModel):
    rule_type: BusinessRuleType
    condition: str = Field(description="The business condition that triggers the rule, in plain language.")
    action: str = Field(description="The action/outcome enforced when the condition holds, in plain language.")
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(default="", description="Brief justification citing evidence_refs.")
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="ref_id values (e.g. 'SRC-1', 'ATC-3', 'EVD-7') from the evidence package that ground this rule.",
    )


class BusinessRuleDiscoveryResult(BaseModel):
    status: BusinessRuleDiscoveryStatus
    rules: list[BusinessRuleCandidate] = Field(
        default_factory=list,
        description="Candidate business rules found. Empty if none were found or evidence was insufficient.",
    )


def validate_result(result: BusinessRuleDiscoveryResult, package: BusinessRuleEvidencePackage) -> list[str]:
    """Return domain validation error strings; empty means the result may be persisted."""
    errors: list[str] = []

    known_ref_ids = {item.ref_id for item in package.all_items()}
    for idx, rule in enumerate(result.rules):
        unknown_refs = sorted(set(rule.evidence_refs) - known_ref_ids)
        if unknown_refs:
            errors.append(f"rules[{idx}].evidence_refs reference ids not present in the evidence package: {unknown_refs}")
        if not rule.condition.strip() or not rule.action.strip():
            errors.append(f"rules[{idx}] requires non-empty condition and action")
        if not rule.evidence_refs:
            errors.append(f"rules[{idx}] requires at least one evidence_refs entry")

    if result.status == BusinessRuleDiscoveryStatus.INSUFFICIENT_CONTEXT and result.rules:
        errors.append("status=INSUFFICIENT_CONTEXT must not include any rules")

    return errors
