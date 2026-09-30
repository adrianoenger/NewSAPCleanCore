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
- `recommendation` (ADR-018, 7 categories) is independently nullable too: when set it requires
  its own rationale + at least one evidence ref from any pool; when left `None` (the analysis
  could not reach a confident classification — there is no fallback category) its evidence_refs
  must be empty, while a rationale explaining why is allowed;
- `status=COMPLETED` iff at least one of the three was determined; `status=INSUFFICIENT_CONTEXT`
  iff nothing at all could be determined.
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
    MODERNIZAR = "MODERNIZAR"
    MANTER_AS_IS = "MANTER_AS_IS"
    REMEDIAR = "REMEDIAR"
    DESCONTINUAR = "DESCONTINUAR"
    REIMPLEMENTAR_EXTENSAO = "REIMPLEMENTAR_EXTENSAO"
    SUBSTITUIR_STANDARD = "SUBSTITUIR_STANDARD"
    ATUALIZAR_OSS = "ATUALIZAR_OSS"


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
    recommendation: CleanCoreRecommendation | None = Field(
        default=None, description="Null if no confident Clean Core classification is warranted — never guess."
    )
    recommendation_rationale: str = Field(default="")
    recommendation_evidence_refs: list[str] = Field(
        default_factory=list, description="ref_id values from any pool (technical, business or SAP guidance)."
    )
    confidence: float = Field(ge=0.0, le=1.0)


def sanitize_result(result: CleanCoreAnalysisResult, package: CleanCoreEvidencePackage) -> CleanCoreAnalysisResult:
    """Drop refs cited outside each dimension's allowed pool (SPRINT-18, mirrors the Copilot), and
    drop a leftover rationale/refs the model attached to a dimension it itself left null.

    A dimension whose evidence refs are all dropped loses its value and rationale instead of
    failing the whole analysis — nothing is ever asserted without in-pool evidence, but one
    misplaced ref (e.g. a DEP-* cited for business importance) no longer discards a valid
    technical risk/recommendation. `status` is re-derived; `validate_result` still runs after.

    Rodobens 1075 (105 real applications) showed the model routinely writes a short explanation
    for *why* technical_risk/business_importance is null even though the prompt says to leave the
    rationale empty in that case (~30% of applications, e.g. "não há evidência suficiente de
    processo/negócio para este módulo") — a real, harmless (non-asserting) text the strict
    validator was rejecting as a domain violation. It is dropped here rather than failing the
    whole analysis; `recommendation`'s rationale is explicitly allowed to stay when null (ADR-018
    docstring above), so only its evidence_refs are cleared.
    """
    technical = {item.ref_id for item in package.technical_items}
    business = {item.ref_id for item in package.business_items} | {item.ref_id for item in package.guidance_items}
    every = technical | business

    def keep(refs: list[str], allowed: set[str]) -> list[str]:
        return [ref for ref in dict.fromkeys(refs) if ref in allowed]

    update: dict = {
        "technical_risk_evidence_refs": keep(result.technical_risk_evidence_refs, technical),
        "business_importance_evidence_refs": keep(result.business_importance_evidence_refs, business),
        "recommendation_evidence_refs": keep(result.recommendation_evidence_refs, every),
    }
    if result.technical_risk is not None and not update["technical_risk_evidence_refs"]:
        update |= {"technical_risk": None, "technical_risk_rationale": ""}
    if result.business_importance is not None and not update["business_importance_evidence_refs"]:
        update |= {"business_importance": None, "business_importance_rationale": ""}
    if result.technical_risk is None and (result.technical_risk_rationale.strip() or update["technical_risk_evidence_refs"]):
        update |= {"technical_risk_rationale": "", "technical_risk_evidence_refs": []}
    if result.business_importance is None and (
        result.business_importance_rationale.strip() or update["business_importance_evidence_refs"]
    ):
        update |= {"business_importance_rationale": "", "business_importance_evidence_refs": []}
    if result.recommendation is None and update["recommendation_evidence_refs"]:
        update |= {"recommendation_evidence_refs": []}
    if result.recommendation is not None and not update["recommendation_evidence_refs"]:
        update |= {"recommendation": None}
    sanitized = result.model_copy(update=update)
    determined = any(
        v is not None for v in (sanitized.technical_risk, sanitized.business_importance, sanitized.recommendation)
    )
    return sanitized.model_copy(
        update={"status": CleanCoreAnalysisStatus.COMPLETED if determined else CleanCoreAnalysisStatus.INSUFFICIENT_CONTEXT}
    )


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

    # recommendation: independently nullable (ADR-018 — no fallback category).
    if result.recommendation is not None:
        if not result.recommendation_rationale.strip():
            errors.append("a non-null recommendation requires a non-empty recommendation_rationale")
        if not result.recommendation_evidence_refs:
            errors.append("a non-null recommendation requires at least one recommendation_evidence_refs entry")
    elif result.recommendation_evidence_refs:
        errors.append("recommendation_evidence_refs must be empty when recommendation is null")

    determined_something = (
        result.technical_risk is not None
        or result.business_importance is not None
        or result.recommendation is not None
    )
    expected_status = CleanCoreAnalysisStatus.COMPLETED if determined_something else CleanCoreAnalysisStatus.INSUFFICIENT_CONTEXT
    if result.status != expected_status:
        errors.append(
            f"status={result.status.value} is inconsistent with the result's own fields "
            f"(expected status={expected_status.value})"
        )

    return errors
