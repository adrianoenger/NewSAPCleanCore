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
    sanitize_result,
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
        recommendation=CleanCoreRecommendation.REMEDIAR,
        recommendation_rationale="Corrigir o finding ATC antes de qualquer outra ação.",
        recommendation_evidence_refs=["ATC-1", "SAPDOC-1"],
        confidence=0.75,
    )
    defaults.update(overrides)
    return CleanCoreAnalysisResult(**defaults)


# ---------------------------------------------------------------------------
# ai.registry registration
# ---------------------------------------------------------------------------


def test_clean_core_analysis_registers_v2_with_7_category_taxonomy():
    version = get_version(CAPABILITY)
    assert version.capability == "clean_core_analysis"
    assert version.version == "v2"
    assert version.schema_name == "clean_core_analysis_result"
    assert "pt-BR" in version.system_prompt
    for category in CleanCoreRecommendation:
        assert category.value in version.system_prompt


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


def test_validate_result_recommendation_requires_evidence():
    errors = validate_result(_completed_result(recommendation_evidence_refs=[]), _package())
    assert any("non-null recommendation requires at least one" in e for e in errors)


def test_validate_result_recommendation_requires_rationale():
    errors = validate_result(_completed_result(recommendation_rationale=""), _package())
    assert any("non-null recommendation requires a non-empty recommendation_rationale" in e for e in errors)


def test_validate_result_null_recommendation_allows_rationale_without_evidence():
    result = _completed_result(
        recommendation=None,
        recommendation_evidence_refs=[],
        recommendation_rationale="Risco e importância conflitam — requer julgamento humano.",
    )
    assert validate_result(result, _package()) == []


def test_validate_result_null_recommendation_rejects_evidence_refs():
    result = _completed_result(recommendation=None, recommendation_evidence_refs=["ATC-1"])
    errors = validate_result(result, _package())
    assert any("must be empty when recommendation is null" in e for e in errors)


def test_validate_result_rejects_legacy_review_value():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _completed_result(recommendation="REVIEW")


def test_validate_result_insufficient_context_with_nothing_determined():
    result = CleanCoreAnalysisResult(
        status=CleanCoreAnalysisStatus.INSUFFICIENT_CONTEXT,
        recommendation_rationale="Sem evidência correlacionada para este cluster.",
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
        confidence=0.1,
    )
    errors = validate_result(result, _package())
    assert any("inconsistent with the result's own fields" in e for e in errors)


def test_validate_result_rejects_status_completed_when_nothing_was_determined():
    result = CleanCoreAnalysisResult(
        status=CleanCoreAnalysisStatus.COMPLETED,
        recommendation_rationale="Not enough evidence either way.",
        confidence=0.1,
    )
    errors = validate_result(result, _package())
    assert any("inconsistent with the result's own fields" in e for e in errors)


def test_validate_result_recommendation_alone_marks_status_completed():
    # A determined recommendation is on its own enough to make status=COMPLETED correct, even with
    # both technical_risk and business_importance left undetermined.
    result = CleanCoreAnalysisResult(
        status=CleanCoreAnalysisStatus.COMPLETED,
        recommendation=CleanCoreRecommendation.SUBSTITUIR_STANDARD,
        recommendation_rationale="Existe processo standard SAP equivalente segundo a orientação SAP.",
        recommendation_evidence_refs=["SAPDOC-1"],
        confidence=0.6,
    )
    assert validate_result(result, _package()) == []


# ---------------------------------------------------------------------------
# sanitize_result (SPRINT-18): misplaced refs are dropped, never fail the whole analysis
# ---------------------------------------------------------------------------


def test_sanitize_drops_out_of_pool_business_ref_and_nulls_that_dimension_only():
    # Live Bedrock case: DEP-* (not in any pool) cited as the only business importance evidence.
    raw = _completed_result(business_importance_evidence_refs=["DEP-6272", "DEP-6273"])
    assert validate_result(raw, _package()) != []
    result = sanitize_result(raw, _package())
    assert result.business_importance is None
    assert result.business_importance_rationale == ""
    assert result.business_importance_evidence_refs == []
    assert result.technical_risk == RiskLevel.HIGH
    assert result.recommendation == CleanCoreRecommendation.REMEDIAR
    assert result.status == CleanCoreAnalysisStatus.COMPLETED
    assert validate_result(result, _package()) == []


def test_sanitize_keeps_valid_refs_and_dedupes():
    raw = _completed_result(recommendation_evidence_refs=["ATC-1", "ATC-1", "INVENTED-9"])
    result = sanitize_result(raw, _package())
    assert result.recommendation_evidence_refs == ["ATC-1"]
    assert result.recommendation == CleanCoreRecommendation.REMEDIAR


def test_sanitize_drops_leftover_rationale_on_a_dimension_the_model_itself_left_null():
    # Rodobens 1075 case (~30% of 105 real applications): the model leaves technical_risk/
    # business_importance null (correctly, per the prompt) but still writes a short explanation —
    # sanitize_result drops the leftover text/refs instead of failing domain validation.
    raw = _completed_result(
        technical_risk=None,
        technical_risk_rationale="Evidência técnica insuficiente para este módulo.",
        technical_risk_evidence_refs=[],
        business_importance=None,
        business_importance_rationale="Não há sinal de uso/processo suficiente.",
        business_importance_evidence_refs=["EVD-1"],
        recommendation=None,
        recommendation_rationale="Falta contexto para uma classificação confiável.",
        recommendation_evidence_refs=["ATC-1"],
    )
    assert validate_result(raw, _package()) != []
    result = sanitize_result(raw, _package())
    assert result.technical_risk_rationale == ""
    assert result.business_importance_rationale == ""
    assert result.business_importance_evidence_refs == []
    assert result.recommendation_evidence_refs == []
    assert result.recommendation_rationale == "Falta contexto para uma classificação confiável."  # allowed to stay
    assert result.status == CleanCoreAnalysisStatus.INSUFFICIENT_CONTEXT
    assert validate_result(result, _package()) == []


def test_sanitize_all_dimensions_unbacked_becomes_insufficient_context():
    raw = _completed_result(
        technical_risk_evidence_refs=["X-1"],
        business_importance_evidence_refs=["X-2"],
        recommendation_evidence_refs=["X-3"],
    )
    result = sanitize_result(raw, _package())
    assert (result.technical_risk, result.business_importance, result.recommendation) == (None, None, None)
    assert result.status == CleanCoreAnalysisStatus.INSUFFICIENT_CONTEXT
    assert validate_result(result, _package()) == []


def test_evidence_package_is_bounded_most_severe_first_and_omitted_not_citable():
    """SPRINT-18 — a large application (Rodobens: 421 objects) overflowed the model input; the
    package now caps each citable pool, keeps the most severe ATC findings and reports totals."""
    from sqlalchemy import text

    from ai.clean_core_analysis.evidence_package import (
        _MAX_ITEMS,
        build_clean_core_evidence_package,
        render_prompt,
    )
    from persistence.database import get_session_factory
    from persistence.models import ATCFinding, ATCRun, Assessment, AssessmentStatus, Client, SAPObject, SourceFile, SourceScan

    with get_session_factory()() as session:
        c = Client(name="Sprint18 Budget Test Client")
        session.add(c)
        session.flush()
        a = Assessment(client_id=c.id, name="Sprint18 Budget", status=AssessmentStatus.CREATED.value)
        session.add(a)
        session.commit()
        aid = a.id
    try:
        with get_session_factory()() as session:
            scan = SourceScan(assessment_id=aid, source_path="/tmp/fixture", status="completed")
            session.add(scan)
            session.flush()
            sf = SourceFile(
                scan_id=scan.id, assessment_id=aid, rel_path="ZA.abap", size_bytes=1, mtime=0.0,
                sha256="0" * 64, category="abap",
            )
            session.add(sf)
            session.flush()
            obj = SAPObject(
                assessment_id=aid, source_file_id=sf.id, object_type="report", object_name="ZA",
                canonical_key="REPORT::ZA",
            )
            app = Application(assessment_id=aid, name="App")
            session.add_all([obj, app])
            session.flush()
            run = ATCRun(assessment_id=aid, source_filename="atc.xlsx")
            session.add(run)
            session.flush()
            # 150 findings: 100 P3 first, then 50 P1 — only 80 fit, all 50 P1 must be kept.
            for i in range(150):
                session.add(
                    ATCFinding(
                        atc_run_id=run.id, assessment_id=aid, source_row_number=i, raw_payload={},
                        priority=3 if i < 100 else 1, check_title=f"check {i}", correlated_object_id=obj.id,
                    )
                )
            session.commit()

            package = build_clean_core_evidence_package(session, app, [obj.id])
            atc = [i for i in package.technical_items if i.source_type == "ATC_FINDING"]
            assert len(atc) == _MAX_ITEMS["ATC"]
            assert sum(1 for i in atc if i.summary.startswith("P1 ")) == 50
            assert package.omitted == {"ATC": 70}
            assert package.atc_priority_totals == {1: 50, 3: 100}
            prompt = render_prompt(package)
            assert "P1=50, P3=100" in prompt
            assert "ATC: +70" in prompt
            assert sum(1 for line in prompt.splitlines() if line.startswith("- ATC-")) == _MAX_ITEMS["ATC"]
    finally:
        with get_session_factory()() as session:
            session.execute(
                text("DELETE FROM client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)"),
                {"aid": aid},
            )
            session.commit()
