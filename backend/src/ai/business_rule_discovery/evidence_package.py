"""Business Rule Discovery evidence package builder (ADR-008/ADR-012 + Baseline "AI Processing").

Reuses `ai.object_understanding`'s evidence package (source excerpt, correlated ATC findings,
correlated supplemental evidence) unchanged — the citable evidence set for a business rule is the
same underlying evidence a rule about that object could ever be grounded in. The persisted
`ObjectUnderstanding` for the object is added as prompt *context* only: per ADR-008, AI
interpretation is not itself authoritative evidence, so it is never a citable `ref_id` and
`evidence_refs` are still validated only against the underlying evidence package.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ai.object_understanding.evidence_package import (
    ObjectEvidencePackage,
    build_evidence_package,
)
from ai.object_understanding.evidence_package import render_prompt as render_object_evidence_prompt
from persistence.models import ObjectUnderstanding, SAPObject


@dataclass(frozen=True)
class BusinessRuleEvidencePackage:
    object_package: ObjectEvidencePackage
    understanding: ObjectUnderstanding

    def all_items(self):
        return self.object_package.all_items()


def build_business_rule_evidence_package(
    session: Session, obj: SAPObject, understanding: ObjectUnderstanding
) -> BusinessRuleEvidencePackage:
    return BusinessRuleEvidencePackage(
        object_package=build_evidence_package(session, obj),
        understanding=understanding,
    )


def render_prompt(package: BusinessRuleEvidencePackage) -> str:
    u = package.understanding
    lines = [
        "Persisted object understanding (interpretation, not evidence by itself — ADR-008):",
        f"- Functional purpose: {u.functional_purpose or '(none)'}",
        f"- Technical purpose: {u.technical_purpose or '(none)'}",
        f"- Concepts: {', '.join(u.concepts or [])}",
        f"- Rationale: {u.rationale or '(none)'}",
        "",
        render_object_evidence_prompt(package.object_package),
    ]
    return "\n".join(lines)
