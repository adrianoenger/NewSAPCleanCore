"""Clean Core Analysis evidence package builder (ADR-008/ADR-012/ADR-017 + Baseline core rule
8/11 + Baseline "AI Processing").

Assembles a provider-agnostic, citable evidence package for one `Application` (reusing the same
member-cluster shape `ai.application_discovery.evidence_package` already builds), split into two
pools so Technical Risk and Business Importance can never share evidence by construction:

- ``technical_items``: object identity, dependency edges, correlated ATC findings, deterministic
  `TechnicalFinding` severities, and technical supplemental signals (`TECHNICAL_OBJECT_METADATA`,
  `SOURCE_CODE`, `DEPENDENCY_SIGNAL`, `S4_CONVERSION_SIGNAL`).
- ``business_items``: object identity plus process/usage/user/role supplemental signals
  (`USAGE_SIGNAL`, `PROCESS_KPI`, `BUSINESS_PROCESS_SIGNAL`, `USER_SIGNAL`, `ROLE_SIGNAL`,
  `AUTHORIZATION_SIGNAL`) — tagged `PROCESS_USAGE_EVIDENCE` rather than the generic
  `SUPPLEMENTAL_EVIDENCE` label so callers can tell whether a business_importance conclusion
  actually rested on one (Baseline core rule 11 transparency). Only `MATCHED_EXACT`/
  `MATCHED_HEURISTIC` correlations are ever included in either supplemental pool — an
  `UNMATCHED`/`AMBIGUOUS` correlation is never citable evidence (ADR-017 quality gate).

SAP guidance already retrieved for this Application (`SapKnowledgeReference`, ADR-007) is
external authoritative context, not customer evidence — it is offered as a third pool available
to both dimensions and the recommendation.

Each member's persisted `ObjectUnderstanding`/`BusinessRule` and the Application's own AI-derived
name/description/rationale are prior interpretation, not evidence (ADR-008) — rendered as prompt
context only, exactly like `ai.application_discovery.evidence_package` treats them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import (
    Application,
    ATCFinding,
    BusinessRule,
    BusinessRuleStatus,
    EvidenceCorrelation,
    EvidenceCorrelationStatus,
    EvidenceDataset,
    EvidenceRecord,
    ObjectUnderstanding,
    ObjectUnderstandingStatus,
    SapKnowledgeReference,
    SapKnowledgeTargetType,
    SAPObject,
    SAPObjectDependency,
    TechnicalFinding,
)

_TARGET_SAP_OBJECT = "SAP_OBJECT"
_MATCHED_STATUSES = (EvidenceCorrelationStatus.MATCHED_EXACT.value, EvidenceCorrelationStatus.MATCHED_HEURISTIC.value)

_BUSINESS_CAPABILITIES = {
    "USAGE_SIGNAL",
    "PROCESS_KPI",
    "BUSINESS_PROCESS_SIGNAL",
    "USER_SIGNAL",
    "ROLE_SIGNAL",
    "AUTHORIZATION_SIGNAL",
}
_TECHNICAL_CAPABILITIES = {
    "TECHNICAL_OBJECT_METADATA",
    "SOURCE_CODE",
    "DEPENDENCY_SIGNAL",
    "S4_CONVERSION_SIGNAL",
}


@dataclass(frozen=True)
class EvidenceItem:
    """One citable piece of evidence; `ref_id` is what the model must echo back in
    `CleanCoreAnalysisResult` evidence_refs fields to prove a claim is evidence-bound."""

    ref_id: str
    source_type: str  # "SAP_OBJECT" | "DEPENDENCY" | "ATC_FINDING" | "TECHNICAL_FINDING"
    # | "SUPPLEMENTAL_EVIDENCE" | "PROCESS_USAGE_EVIDENCE" | "SAP_KNOWLEDGE"
    entity_id: int
    summary: str


@dataclass(frozen=True)
class MemberContext:
    object_id: int
    object_type: str
    object_name: str
    understanding: ObjectUnderstanding | None
    business_rules: list[BusinessRule]


@dataclass(frozen=True)
class CleanCoreEvidencePackage:
    application: Application
    members: list[MemberContext]
    technical_items: list[EvidenceItem]
    business_items: list[EvidenceItem]
    guidance_items: list[EvidenceItem]

    def all_items(self) -> list[EvidenceItem]:
        return [*self.technical_items, *self.business_items, *self.guidance_items]


def build_clean_core_evidence_package(
    session: Session, application: Application, member_ids: list[int]
) -> CleanCoreEvidencePackage:
    objects = list(session.scalars(select(SAPObject).where(SAPObject.id.in_(member_ids))))
    objects_by_id = {obj.id: obj for obj in objects}

    object_items = [
        EvidenceItem(
            ref_id=f"OBJ-{obj.id}",
            source_type="SAP_OBJECT",
            entity_id=obj.id,
            summary=f"{obj.object_type} {obj.object_name}"
            + (f": {obj.description[:200]}" if obj.description else ""),
        )
        for obj in objects
    ]

    dependency_items: list[EvidenceItem] = []
    for dep in session.scalars(select(SAPObjectDependency).where(SAPObjectDependency.source_object_id.in_(member_ids))):
        source = objects_by_id.get(dep.source_object_id)
        if source is None:
            continue
        dependency_items.append(
            EvidenceItem(
                ref_id=f"DEP-{dep.id}",
                source_type="DEPENDENCY",
                entity_id=dep.id,
                summary=f"{source.object_name} -> {dep.target_name} ({dep.dep_type})",
            )
        )

    atc_findings = list(session.scalars(select(ATCFinding).where(ATCFinding.correlated_object_id.in_(member_ids))))
    atc_items = [
        EvidenceItem(
            ref_id=f"ATC-{f.id}",
            source_type="ATC_FINDING",
            entity_id=f.id,
            summary=(
                f"{f.check_title or 'ATC finding'} on {objects_by_id[f.correlated_object_id].object_name}: "
                f"{(f.check_message or '').strip()[:200]}"
            ),
        )
        for f in atc_findings
    ]

    finding_rows = list(session.scalars(select(TechnicalFinding).where(TechnicalFinding.sap_object_id.in_(member_ids))))
    finding_items = [
        EvidenceItem(
            ref_id=f"TF-{tf.id}",
            source_type="TECHNICAL_FINDING",
            entity_id=tf.id,
            summary=(
                f"[{tf.severity}] {tf.title} on "
                f"{objects_by_id[tf.sap_object_id].object_name if tf.sap_object_id else 'assessment'}"
            ),
        )
        for tf in finding_rows
    ]

    evd_rows = list(
        session.execute(
            select(EvidenceCorrelation, EvidenceRecord, EvidenceDataset)
            .join(EvidenceRecord, EvidenceCorrelation.evidence_record_id == EvidenceRecord.id)
            .join(EvidenceDataset, EvidenceRecord.dataset_id == EvidenceDataset.id)
            .where(
                EvidenceCorrelation.target_type == _TARGET_SAP_OBJECT,
                EvidenceCorrelation.target_id.in_(member_ids),
                EvidenceCorrelation.status.in_(_MATCHED_STATUSES),
            )
        )
    )
    technical_signal_items: list[EvidenceItem] = []
    business_signal_items: list[EvidenceItem] = []
    for corr, rec, dataset in evd_rows:
        summary = (
            f"{dataset.dataset_type} / {rec.record_type} ({rec.capability}) on "
            f"{objects_by_id[corr.target_id].object_name}: {_short_payload(rec.normalized_payload)}"
        )
        if rec.capability in _BUSINESS_CAPABILITIES:
            business_signal_items.append(
                EvidenceItem(ref_id=f"EVD-{rec.id}", source_type="PROCESS_USAGE_EVIDENCE", entity_id=rec.id, summary=summary)
            )
        elif rec.capability in _TECHNICAL_CAPABILITIES:
            technical_signal_items.append(
                EvidenceItem(ref_id=f"EVD-{rec.id}", source_type="SUPPLEMENTAL_EVIDENCE", entity_id=rec.id, summary=summary)
            )
        # An unrecognized capability is neither pool's evidence — never guessed either way.

    guidance_rows = list(
        session.scalars(
            select(SapKnowledgeReference).where(
                SapKnowledgeReference.target_type == SapKnowledgeTargetType.APPLICATION.value,
                SapKnowledgeReference.target_id == application.id,
            )
        )
    )
    guidance_items = [
        EvidenceItem(
            ref_id=f"SAPDOC-{g.id}",
            source_type="SAP_KNOWLEDGE",
            entity_id=g.id,
            summary=f"{g.title}: {g.summary[:200]}" if g.title else g.summary[:200],
        )
        for g in guidance_rows
    ]

    understandings = {
        u.sap_object_id: u
        for u in session.scalars(
            select(ObjectUnderstanding).where(
                ObjectUnderstanding.sap_object_id.in_(member_ids),
                ObjectUnderstanding.status == ObjectUnderstandingStatus.COMPLETED.value,
            )
        )
    }
    rules_by_object: dict[int, list[BusinessRule]] = {}
    for rule in session.scalars(
        select(BusinessRule).where(BusinessRule.sap_object_id.in_(member_ids), BusinessRule.status == BusinessRuleStatus.CANDIDATE.value)
    ):
        rules_by_object.setdefault(rule.sap_object_id, []).append(rule)

    members = [
        MemberContext(
            object_id=obj.id,
            object_type=obj.object_type,
            object_name=obj.object_name,
            understanding=understandings.get(obj.id),
            business_rules=rules_by_object.get(obj.id, []),
        )
        for obj in objects
    ]

    return CleanCoreEvidencePackage(
        application=application,
        members=members,
        technical_items=[*object_items, *dependency_items, *atc_items, *finding_items, *technical_signal_items],
        business_items=[*object_items, *business_signal_items],
        guidance_items=guidance_items,
    )


def _short_payload(payload: dict) -> str:
    parts = [f"{k}={v}" for k, v in list(payload.items())[:5]]
    return ", ".join(parts)[:200]


def render_prompt(package: CleanCoreEvidencePackage) -> str:
    """Render `package` into the user-turn text handed to the provider."""
    app = package.application
    lines = [
        f"Candidate application: {app.name or '(unnamed candidate)'}",
        f"AI-derived description (interpretation, not evidence — ADR-008): {app.description or '(none)'}",
        f"AI-derived domain (interpretation, not evidence): {app.domain or '(none)'}",
        "",
        "Members:",
    ]
    for member in package.members:
        lines.append(f"- {member.object_type} {member.object_name} (ref OBJ-{member.object_id})")
        if member.understanding is not None:
            u = member.understanding
            purpose = u.functional_purpose or u.technical_purpose
            lines.append(f"  Persisted understanding (interpretation, not evidence — ADR-008): {purpose}")
        for rule in member.business_rules:
            lines.append(
                f"  Discovered rule (interpretation, not evidence — ADR-008): {rule.condition} -> {rule.action}"
            )

    lines.append("")
    lines.append("Technical evidence (use only for technical_risk):")
    if not package.technical_items:
        lines.append("(none)")
    for item in package.technical_items:
        lines.append(f"- {item.ref_id} [{item.source_type}]: {item.summary}")

    lines.append("")
    lines.append(
        "Business evidence (use only for business_importance; PROCESS_USAGE_EVIDENCE items are "
        "correlation-quality-gated process/usage/user/role signals):"
    )
    if not package.business_items:
        lines.append("(none)")
    for item in package.business_items:
        lines.append(f"- {item.ref_id} [{item.source_type}]: {item.summary}")

    lines.append("")
    lines.append("SAP guidance (external authoritative context — may support either dimension or the recommendation):")
    if not package.guidance_items:
        lines.append("(none retrieved for this application)")
    for item in package.guidance_items:
        lines.append(f"- {item.ref_id} [{item.source_type}]: {item.summary}")

    return "\n".join(lines)
