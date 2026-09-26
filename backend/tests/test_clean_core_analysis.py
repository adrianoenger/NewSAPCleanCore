"""SPRINT-13 — Clean Core Analysis: registry registration and domain-validator unit tests
(ADR-008/ADR-012, Baseline core rule 8/11). Mirrors test_application_discovery.py's own
domain-validator test pattern.
"""
from __future__ import annotations

from ai.clean_core_analysis import CAPABILITY
from ai.clean_core_analysis.evidence_package import CleanCoreEvidencePackage, EvidenceItem
from ai.clean_core_analysis.schema import (
    CleanCoreAnalysisResult,
    CleanCoreAnalysisStatus,
    CleanCoreRecommendation,
    ImportanceLevel,
    RiskLevel,
    validate_result,
)
from ai.registry import get_version
from persistence.models import Application


def _package() -> CleanCoreEvidencePackage:
    return CleanCoreEvidencePackage(
        application=Application(),  # unsaved — validate_result never reads it
        members=[],
        technical_items=[
            EvidenceItem(ref_id="OBJ-1", source_type="SAP_OBJECT", entity_id=1, summary="report ZA"),
            EvidenceItem(ref_id="ATC-1", source_type="ATC_FINDING", entity_id=1, summary="a finding"),
        ],
        business_items=[
            EvidenceItem(ref_id="OBJ-1", source_type="SAP_OBJECT", entity_id=1, summary="report ZA"),
            EvidenceItem(ref_id="EVD-1", source_type="PROCESS_USAGE_EVIDENCE", entity_id=1, summary="usage signal"),
        ],
        guidance_items=[EvidenceItem(ref_id="SAPDOC-1", source_type="SAP_KNOWLEDGE", entity_id=1, summary="a note")],
    )


def _completed_result(**overrides) -> CleanCoreAnalysisResult:
    defaults = dict(
        status=CleanCoreAnalysisStatus.COMPLETED,
        technical_risk=RiskLevel.HIGH,
        technical_risk_rationale="High risk because of an open ATC finding.",
        technical_risk_evidence_refs=["ATC-1"],
        business_importance=ImportanceLevel.MEDIUM,
        business_importance_rationale="Used moderately per usage signal.",
        business_importance_evidence_refs=["EVD-1"],
        recommendation=CleanCoreRecommendation.REMEDIATE,
        recommendation_rationale="Fix the finding before retiring or replatforming.",
        recommendation_evidence_refs=["ATC-1", "SAPDOC-1"],
        confidence=0.75,
    )
    defaults.update(overrides)
    return CleanCoreAnalysisResult(**defaults)


# ---------------------------------------------------------------------------
# ai.registry registration
# ---------------------------------------------------------------------------


def test_clean_core_analysis_registers_v1():
    version = get_version(CAPABILITY)
    assert version.capability == "clean_core_analysis"
    assert version.version == "v1"
    assert version.schema_name == "clean_core_analysis_result"


# ---------------------------------------------------------------------------
# CleanCoreAnalysisResult domain validators (ai.clean_core_analysis.schema)
# ---------------------------------------------------------------------------


def test_validate_result_valid_completed_has_no_errors():
    assert validate_result(_completed_result(), _package()) == []


def test_validate_result_allows_technical_risk_undetermined_when_others_are():
    # Real live-Bedrock behavior: a sparse cluster can still support a determined
    # business_importance/recommendation while technical_risk stays undetermined — each
    # dimension's determinability is independent (Baseline core rule 8).
    result = _completed_result(
        technical_risk=None, technical_risk_rationale="", technical_risk_evidence_refs=[]
    )
    assert validate_result(result, _package()) == []


def test_validate_result_allows_business_importance_undetermined_when_others_are():
    result = _completed_result(
        business_importance=None, business_importance_rationale="", business_importance_evidence_refs=[]
    )
    assert validate_result(result, _package()) == []


def test_validate_result_rejects_technical_risk_without_rationale():
    result = _completed_result(technical_risk_rationale="")
    errors = validate_result(result, _package())
    assert any("technical_risk requires a non-empty technical_risk_rationale" in e for e in errors)


def test_validate_result_rejects_null_technical_risk_with_leftover_rationale():
    result = _completed_result(technical_risk=None, technical_risk_evidence_refs=[])
    errors = validate_result(result, _package())
    assert any("must be empty when technical_risk is null" in e for e in errors)


def test_validate_result_rejects_technical_risk_evidence_from_business_pool():
    # EVD-1 is only in the business pool, never the technical pool.
    errors = validate_result(_completed_result(technical_risk_evidence_refs=["EVD-1"]), _package())
    assert any("technical_risk_evidence_refs must come from the technical evidence pool" in e for e in errors)


def test_validate_result_allows_business_importance_evidence_from_guidance_pool():
    result = _completed_result(business_importance_evidence_refs=["SAPDOC-1"])
    assert validate_result(result, _package()) == []


def test_validate_result_rejects_unknown_recommendation_evidence_ref():
    errors = validate_result(_completed_result(recommendation_evidence_refs=["ATC-999"]), _package())
    assert any("not present in the evidence package" in e for e in errors)


def test_validate_result_non_review_recommendation_requires_evidence():
    errors = validate_result(_completed_result(recommendation_evidence_refs=[]), _package())
    assert any("non-REVIEW recommendation requires" in e for e in errors)


def test_validate_result_review_recommendation_allows_empty_evidence_with_rationale():
    result = _completed_result(
        recommendation=CleanCoreRecommendation.REVIEW,
        recommendation_evidence_refs=[],
        recommendation_rationale="Risk and importance conflict — needs human judgment.",
    )
    assert validate_result(result, _package()) == []


def test_validate_result_insufficient_context_allows_review_only():
    result = CleanCoreAnalysisResult(
        status=CleanCoreAnalysisStatus.INSUFFICIENT_CONTEXT,
        recommendation=CleanCoreRecommendation.REVIEW,
        recommendation_rationale="No correlated evidence for this cluster yet.",
        confidence=0.1,
    )
    assert validate_result(result, _package()) == []


def test_validate_result_rejects_status_insufficient_context_when_a_dimension_was_determined():
    # A well-formed, evidence-backed technical_risk was actually determined — claiming
    # status=INSUFFICIENT_CONTEXT alongside it is a self-contradiction the model must not smuggle in.
    result = CleanCoreAnalysisResult(
        status=CleanCoreAnalysisStatus.INSUFFICIENT_CONTEXT,
        technical_risk=RiskLevel.HIGH,
        technical_risk_rationale="High risk because of an open ATC finding.",
        technical_risk_evidence_refs=["ATC-1"],
        recommendation=CleanCoreRecommendation.REVIEW,
        recommendation_rationale="r",
        confidence=0.1,
    )
    errors = validate_result(result, _package())
    assert any("inconsistent with the result's own fields" in e for e in errors)


def test_validate_result_rejects_status_completed_when_nothing_was_determined():
    result = CleanCoreAnalysisResult(
        status=CleanCoreAnalysisStatus.COMPLETED,
        recommendation=CleanCoreRecommendation.REVIEW,
        recommendation_rationale="Not enough evidence either way.",
        confidence=0.1,
    )
    errors = validate_result(result, _package())
    assert any("inconsistent with the result's own fields" in e for e in errors)


def test_validate_result_non_review_recommendation_marks_status_completed():
    # recommendation != REVIEW is on its own enough to make status=COMPLETED correct, even with
    # both technical_risk and business_importance left undetermined.
    result = CleanCoreAnalysisResult(
        status=CleanCoreAnalysisStatus.COMPLETED,
        recommendation=CleanCoreRecommendation.RETIRE,
        recommendation_rationale="Superseded by a standard SAP process per SAP guidance.",
        recommendation_evidence_refs=["SAPDOC-1"],
        confidence=0.6,
    )
    assert validate_result(result, _package()) == []
