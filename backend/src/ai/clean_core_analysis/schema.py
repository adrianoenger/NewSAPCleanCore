"""Clean Core Analysis structured contract (ADR-008/ADR-012, Baseline core rule 8/11).

`CleanCoreAnalysisResult` is the only shape a provider is allowed to return for this capability.
`validate_result` enforces the evidence-binding and dimension-separation rules a schema-valid-but-
unfounded response could still violate.

Baseline core rule 8 requires Technical Risk, Business Importance and Recommendation to stay
*separate* — which means each one's determinability is independent too: a live Bedrock run
confirmed the model routinely determines a `technical_risk` for a sparsely-evidenced single-object
cluster (e.g. "no findings, no risky dependencies" already supports LOW) while still judging the
cluster's business/naming evidence too thin for a confident `recommendation`. An earlier version of
this validator tied `technical_risk`/`business_importance` nullability to one blanket `status`
field, which made every such (legitimate, evidence-grounded) partial result fail domain validation
100% of the time in that live run — the opposite of ADR-012's "allow insufficient-context results
rather than forced conclusions" intent. Each dimension is now independently nullable:

- whenever `technical_risk`/`business_importance` is set, its own rationale + at least one
  evidence ref from its own pool (never the other dimension's pool for technical_risk; business
  guidance is allowed for business_importance) is required;
- whenever it is left `None`, its rationale/evidence_refs must be empty — never assert without
  determining;
- `recommendation` is always required. A non-`REVIEW` recommendation requires its own rationale +
  evidence; `REVIEW` — the explicit fallback — requires only a rationale explaining why (evidence
  may be empty), and is the only valid value when the model could determine neither dimension;
- `status=COMPLETED` iff at least one dimension was determined or the recommendation is not
  `REVIEW`; `status=INSUFFICIENT_CONTEXT` iff nothing at all could be determined.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ai.clean_core_analysis.evidence_package import CleanCoreEvidencePackage


class CleanCoreAnalysisStatus(str, Enum):
    COMPLETED = "COMPLETED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ImportanceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CleanCoreRecommendation(str, Enum):
    RETAIN = "RETAIN"
    REMEDIATE = "REMEDIATE"
    REPLATFORM = "REPLATFORM"
    RETIRE = "RETIRE"
    REVIEW = "REVIEW"


class CleanCoreAnalysisResult(BaseModel):
    status: CleanCoreAnalysisStatus
    technical_risk: RiskLevel | None = Field(
        default=None, description="Null if the technical evidence is too thin to determine a level — never guess."
    )
    technical_risk_rationale: str = Field(default="", description="Justification citing only technical evidence_refs.")
    technical_risk_evidence_refs: list[str] = Field(
        default_factory=list, description="ref_id values from the technical evidence pool only."
    )
    business_importance: ImportanceLevel | None = Field(
        default=None, description="Null if the business context is too thin to determine a level — never guess."
    )
    business_importance_rationale: str = Field(default="", description="Justification citing only business evidence_refs.")
    business_importance_evidence_refs: list[str] = Field(
        default_factory=list, description="ref_id values from the business evidence pool only."
    )
    recommendation: CleanCoreRecommendation
    recommendation_rationale: str = Field(default="")
    recommendation_evidence_refs: list[str] = Field(
        default_factory=list, description="ref_id values from any pool (technical, business or SAP guidance)."
    )
    confidence: float = Field(ge=0.0, le=1.0)


def validate_result(result: CleanCoreAnalysisResult, package: CleanCoreEvidencePackage) -> list[str]:
    """Return domain validation error strings; empty means the result may be persisted."""
    errors: list[str] = []

    technical_ref_ids = {item.ref_id for item in package.technical_items}
    business_ref_ids = {item.ref_id for item in package.business_items}
    guidance_ref_ids = {item.ref_id for item in package.guidance_items}
    all_ref_ids = technical_ref_ids | business_ref_ids | guidance_ref_ids

    unknown_technical = sorted(set(result.technical_risk_evidence_refs) - technical_ref_ids)
    if unknown_technical:
        errors.append(f"technical_risk_evidence_refs must come from the technical evidence pool: {unknown_technical}")

    unknown_business = sorted(set(result.business_importance_evidence_refs) - (business_ref_ids | guidance_ref_ids))
    if unknown_business:
        errors.append(
            f"business_importance_evidence_refs must come from the business evidence pool or SAP guidance: {unknown_business}"
        )

    unknown_recommendation = sorted(set(result.recommendation_evidence_refs) - all_ref_ids)
    if unknown_recommendation:
        errors.append(f"recommendation_evidence_refs reference ids not present in the evidence package: {unknown_recommendation}")

    # technical_risk: independently nullable — asserted iff evidence-backed.
    if result.technical_risk is not None:
        if not result.technical_risk_rationale.strip():
            errors.append("a non-null technical_risk requires a non-empty technical_risk_rationale")
        if not result.technical_risk_evidence_refs:
            errors.append("a non-null technical_risk requires at least one technical_risk_evidence_refs entry")
    elif result.technical_risk_rationale.strip() or result.technical_risk_evidence_refs:
        errors.append("technical_risk_rationale/technical_risk_evidence_refs must be empty when technical_risk is null")

    # business_importance: independently nullable — asserted iff evidence-backed.
    if result.business_importance is not None:
        if not result.business_importance_rationale.strip():
            errors.append("a non-null business_importance requires a non-empty business_importance_rationale")
        if not result.business_importance_evidence_refs:
            errors.append("a non-null business_importance requires at least one business_importance_evidence_refs entry")
    elif result.business_importance_rationale.strip() or result.business_importance_evidence_refs:
        errors.append("business_importance_rationale/business_importance_evidence_refs must be empty when business_importance is null")

    # recommendation is always required; REVIEW is the fallback when a confident non-REVIEW call
    # is not warranted (independent of whether either dimension above was determined).
    if not result.recommendation_rationale.strip():
        errors.append("recommendation_rationale is always required")
    if result.recommendation != CleanCoreRecommendation.REVIEW and not result.recommendation_evidence_refs:
        errors.append("a non-REVIEW recommendation requires at least one recommendation_evidence_refs entry")

    determined_something = (
        result.technical_risk is not None
        or result.business_importance is not None
        or result.recommendation != CleanCoreRecommendation.REVIEW
    )
    expected_status = CleanCoreAnalysisStatus.COMPLETED if determined_something else CleanCoreAnalysisStatus.INSUFFICIENT_CONTEXT
    if result.status != expected_status:
        errors.append(
            f"status={result.status.value} is inconsistent with the result's own fields "
            f"(expected status={expected_status.value})"
        )

    return errors
