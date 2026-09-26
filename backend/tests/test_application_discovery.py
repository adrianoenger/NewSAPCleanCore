"""SPRINT-11 — Application Discovery: registry registration and domain-validator unit tests
(ADR-008/ADR-012). Mirrors test_business_rule_discovery.py's own domain-validator test pattern.
"""
from __future__ import annotations

from ai.application_discovery import CAPABILITY
from ai.application_discovery.evidence_package import ApplicationEvidencePackage, EvidenceItem
from ai.application_discovery.schema import ApplicationDiscoveryResult, ApplicationDiscoveryStatus, validate_result
from ai.registry import get_version


def _package() -> ApplicationEvidencePackage:
    return ApplicationEvidencePackage(
        object_items=[EvidenceItem(ref_id="OBJ-1", source_type="SAP_OBJECT", entity_id=1, summary="report ZA")],
        dependency_items=[EvidenceItem(ref_id="DEP-1", source_type="DEPENDENCY", entity_id=1, summary="ZA -> ZB")],
        atc_items=[],
        supplemental_items=[],
    )


def _result(**overrides) -> ApplicationDiscoveryResult:
    defaults = dict(
        status=ApplicationDiscoveryStatus.COMPLETED,
        name="Order Management",
        description="Handles order validation and posting.",
        domain="Order Management",
        confidence=0.8,
        rationale="r",
        evidence_refs=["OBJ-1", "DEP-1"],
    )
    defaults.update(overrides)
    return ApplicationDiscoveryResult(**defaults)


# ---------------------------------------------------------------------------
# ai.registry registration
# ---------------------------------------------------------------------------


def test_application_discovery_registers_v1():
    version = get_version(CAPABILITY)
    assert version.capability == "application_discovery"
    assert version.version == "v1"
    assert version.schema_name == "application_discovery_result"


# ---------------------------------------------------------------------------
# ApplicationDiscoveryResult domain validators (ai.application_discovery.schema)
# ---------------------------------------------------------------------------


def test_validate_result_valid_completed_has_no_errors():
    assert validate_result(_result(), _package()) == []


def test_validate_result_rejects_completed_without_name():
    result = _result(name="")
    errors = validate_result(result, _package())
    assert any("requires a non-empty name" in e for e in errors)


def test_validate_result_rejects_completed_without_evidence_refs():
    result = _result(evidence_refs=[])
    errors = validate_result(result, _package())
    assert any("requires at least one evidence_refs" in e for e in errors)


def test_validate_result_rejects_unknown_evidence_refs():
    result = _result(evidence_refs=["OBJ-999"])
    errors = validate_result(result, _package())
    assert any("not present in the evidence package" in e for e in errors)


def test_validate_result_insufficient_context_allows_empty_fields():
    result = ApplicationDiscoveryResult(
        status=ApplicationDiscoveryStatus.INSUFFICIENT_CONTEXT, confidence=0.1, evidence_refs=[]
    )
    assert validate_result(result, _package()) == []


def test_validate_result_insufficient_context_must_not_assert_name():
    result = ApplicationDiscoveryResult(
        status=ApplicationDiscoveryStatus.INSUFFICIENT_CONTEXT, name="Order Management", confidence=0.1
    )
    errors = validate_result(result, _package())
    assert any("must not assert name/description/domain" in e for e in errors)
