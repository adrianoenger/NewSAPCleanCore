"""SPRINT-10 — Business Rule Discovery: registry registration and domain-validator unit tests
(ADR-008/ADR-012). Mirrors test_ai_providers.py's own domain-validator test pattern for
object_understanding — no live provider credentials required.
"""
from __future__ import annotations

from ai.business_rule_discovery import CAPABILITY
from ai.business_rule_discovery.evidence_package import BusinessRuleEvidencePackage
from ai.business_rule_discovery.schema import (
    BusinessRuleCandidate,
    BusinessRuleDiscoveryResult,
    BusinessRuleDiscoveryStatus,
    BusinessRuleType,
    validate_result,
)
from ai.object_understanding.evidence_package import EvidenceItem, ObjectEvidencePackage
from ai.registry import get_version


class _FakeUnderstanding:
    functional_purpose = "Validates the customer's credit limit before posting."
    technical_purpose = "Checks a threshold and raises an exception."
    concepts: list[str] = ["credit management"]
    rationale = "Grounded in the source excerpt."


def _package() -> BusinessRuleEvidencePackage:
    object_package = ObjectEvidencePackage(
        object_id=1,
        object_type="report",
        object_name="ZA",
        description="",
        code_excerpt_chunks=["code"],
        code_truncated=False,
        code_item=EvidenceItem(ref_id="SRC-1", source_type="SOURCE_CODE", entity_id=1, summary="s"),
        atc_items=[],
        supplemental_items=[],
    )
    return BusinessRuleEvidencePackage(object_package=object_package, understanding=_FakeUnderstanding())


def _rule(**overrides) -> BusinessRuleCandidate:
    defaults = dict(
        rule_type=BusinessRuleType.VALIDATION,
        condition="order value exceeds customer credit limit",
        action="reject the posting",
        confidence=0.9,
        rationale="r",
        evidence_refs=["SRC-1"],
    )
    defaults.update(overrides)
    return BusinessRuleCandidate(**defaults)


# ---------------------------------------------------------------------------
# ai.registry registration
# ---------------------------------------------------------------------------


def test_business_rule_discovery_registers_v1():
    version = get_version(CAPABILITY)
    assert version.capability == "business_rule_discovery"
    assert version.version == "v1"
    assert version.schema_name == "business_rule_discovery_result"


# ---------------------------------------------------------------------------
# BusinessRuleDiscoveryResult domain validators (ai.business_rule_discovery.schema)
# ---------------------------------------------------------------------------


def test_validate_result_completed_allows_zero_rules():
    """A COMPLETED result with no rules is a valid outcome — 'reviewed, none found' —
    never forced into fabricating a rule (ADR-012)."""
    result = BusinessRuleDiscoveryResult(status=BusinessRuleDiscoveryStatus.COMPLETED, rules=[])
    assert validate_result(result, _package()) == []


def test_validate_result_valid_completed_rule_has_no_errors():
    result = BusinessRuleDiscoveryResult(status=BusinessRuleDiscoveryStatus.COMPLETED, rules=[_rule()])
    assert validate_result(result, _package()) == []


def test_validate_result_rejects_rule_missing_condition_or_action():
    result = BusinessRuleDiscoveryResult(
        status=BusinessRuleDiscoveryStatus.COMPLETED, rules=[_rule(condition="", action="")]
    )
    errors = validate_result(result, _package())
    assert any("requires non-empty condition and action" in e for e in errors)


def test_validate_result_rejects_rule_without_evidence_refs():
    result = BusinessRuleDiscoveryResult(
        status=BusinessRuleDiscoveryStatus.COMPLETED, rules=[_rule(evidence_refs=[])]
    )
    errors = validate_result(result, _package())
    assert any("requires at least one evidence_refs" in e for e in errors)


def test_validate_result_rejects_unknown_evidence_refs_in_rule():
    result = BusinessRuleDiscoveryResult(
        status=BusinessRuleDiscoveryStatus.COMPLETED, rules=[_rule(evidence_refs=["SRC-999"])]
    )
    errors = validate_result(result, _package())
    assert any("not present in the evidence package" in e for e in errors)


def test_validate_result_insufficient_context_must_not_include_rules():
    result = BusinessRuleDiscoveryResult(status=BusinessRuleDiscoveryStatus.INSUFFICIENT_CONTEXT, rules=[_rule()])
    errors = validate_result(result, _package())
    assert any("must not include any rules" in e for e in errors)
