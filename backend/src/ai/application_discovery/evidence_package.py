"""Application Discovery evidence package builder (ADR-008/ADR-012 + Baseline "AI Processing").

Assembles a provider-agnostic, citable evidence package for one candidate cluster
(`ai.application_discovery.clustering.CandidateCluster`): each member object's deterministic
identity, the dependency edges that linked members together, and every member's correlated ATC
findings / supplemental evidence — the same ground-truth artifacts `ai.object_understanding`
cites for a single object, aggregated across the cluster.

Each member's persisted `ObjectUnderstanding` and `BusinessRule`s are AI-derived interpretation
from earlier pipeline stages — per ADR-008 they are never citable evidence themselves, so they
are rendered as prompt *context* only (mirroring `ai.business_rule_discovery.evidence_package`'s
treatment of `ObjectUnderstanding`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.application_discovery.clustering import CandidateCluster, ClusterSignal
from persistence.models import (
    ATCFinding,
    BusinessRule,
    BusinessRuleStatus,
    EvidenceCorrelation,
    EvidenceCorrelationStatus,
    EvidenceDataset,
    EvidenceRecord,
    ObjectUnderstanding,
    ObjectUnderstandingStatus,
    SAPObject,
)

_TARGET_SAP_OBJECT = "SAP_OBJECT"
_MATCHED_STATUSES = (EvidenceCorrelationStatus.MATCHED_EXACT.value, EvidenceCorrelationStatus.MATCHED_HEURISTIC.value)


@dataclass(frozen=True)
class EvidenceItem:
    """One citable piece of evidence; `ref_id` is what the model must echo back in
    `ApplicationDiscoveryResult.evidence_refs` to prove a claim is evidence-bound."""

    ref_id: str
    source_type: str  # "SAP_OBJECT" | "DEPENDENCY" | "ATC_FINDING" | "SUPPLEMENTAL_EVIDENCE"
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
class ApplicationEvidencePackage:
    object_items: list[EvidenceItem]
    dependency_items: list[EvidenceItem]
    atc_items: list[EvidenceItem]
    supplemental_items: list[EvidenceItem]
    members: list[MemberContext] = field(default_factory=list)
    clustering_signals: list[ClusterSignal] = field(default_factory=list)

    def all_items(self) -> list[EvidenceItem]:
        return [*self.object_items, *self.dependency_items, *self.atc_items, *self.supplemental_items]


def build_application_evidence_package(session: Session, cluster: CandidateCluster) -> ApplicationEvidencePackage:
    objects = list(session.scalars(select(SAPObject).where(SAPObject.id.in_(cluster.object_ids))))
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
    seen_dep_ids: set[int] = set()
    for signal in cluster.signals:
        if signal.signal_type != "dependency" or signal.dependency_id is None:
            continue
        if signal.dependency_id in seen_dep_ids:
            continue
        seen_dep_ids.add(signal.dependency_id)
        dependency_items.append(
            EvidenceItem(
                ref_id=f"DEP-{signal.dependency_id}",
                source_type="DEPENDENCY",
                entity_id=signal.dependency_id,
                summary=signal.description,
            )
        )

    atc_findings = list(
        session.scalars(select(ATCFinding).where(ATCFinding.correlated_object_id.in_(cluster.object_ids)))
    )
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

    rows = list(
        session.execute(
            select(EvidenceCorrelation, EvidenceRecord, EvidenceDataset)
            .join(EvidenceRecord, EvidenceCorrelation.evidence_record_id == EvidenceRecord.id)
            .join(EvidenceDataset, EvidenceRecord.dataset_id == EvidenceDataset.id)
            .where(
                EvidenceCorrelation.target_type == _TARGET_SAP_OBJECT,
                EvidenceCorrelation.target_id.in_(cluster.object_ids),
                EvidenceCorrelation.status.in_(_MATCHED_STATUSES),
            )
        )
    )
    supplemental_items = [
        EvidenceItem(
            ref_id=f"EVD-{rec.id}",
            source_type="SUPPLEMENTAL_EVIDENCE",
            entity_id=rec.id,
            summary=(
                f"{dataset.dataset_type} / {rec.record_type} ({rec.capability}) on "
                f"{objects_by_id[corr.target_id].object_name}: {_short_payload(rec.normalized_payload)}"
            ),
        )
        for corr, rec, dataset in rows
    ]

    understandings = {
        u.sap_object_id: u
        for u in session.scalars(
            select(ObjectUnderstanding).where(
                ObjectUnderstanding.sap_object_id.in_(cluster.object_ids),
                ObjectUnderstanding.status == ObjectUnderstandingStatus.COMPLETED.value,
            )
        )
    }
    rules_by_object: dict[int, list[BusinessRule]] = {}
    for rule in session.scalars(
        select(BusinessRule).where(
            BusinessRule.sap_object_id.in_(cluster.object_ids),
            BusinessRule.status == BusinessRuleStatus.CANDIDATE.value,
        )
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

    return ApplicationEvidencePackage(
        object_items=object_items,
        dependency_items=dependency_items,
        atc_items=atc_items,
        supplemental_items=supplemental_items,
        members=members,
        clustering_signals=cluster.signals,
    )


def _short_payload(payload: dict) -> str:
    parts = [f"{k}={v}" for k, v in list(payload.items())[:5]]
    return ", ".join(parts)[:200]


def render_prompt(package: ApplicationEvidencePackage) -> str:
    """Render `package` into the user-turn text handed to the provider."""
    lines = ["Candidate cluster of SAP objects (deterministic clustering, not yet named):", ""]
    for member in package.members:
        lines.append(f"- {member.object_type} {member.object_name} (ref OBJ-{member.object_id})")
        if member.understanding is not None:
            u = member.understanding
            purpose = u.functional_purpose or u.technical_purpose
            lines.append(f"  Persisted understanding (interpretation, not evidence — ADR-008): {purpose}")
            if u.concepts:
                lines.append(f"  Concepts: {', '.join(u.concepts)}")
        for rule in member.business_rules:
            lines.append(
                f"  Discovered rule (interpretation, not evidence — ADR-008): {rule.condition} -> {rule.action}"
            )

    lines.append("")
    lines.append("Deterministic clustering signals that grouped these objects together:")
    if not package.clustering_signals:
        lines.append("(none — this is a single-object candidate with no grouping evidence)")
    for signal in package.clustering_signals:
        lines.append(f"- [{signal.signal_type}] {signal.description}")

    lines.append("")
    lines.append("Evidence available for citation (use these ref_id values in evidence_refs):")
    if not package.all_items():
        lines.append("(none — no object identity, dependency, ATC or supplemental evidence found)")
    for item in package.all_items():
        lines.append(f"- {item.ref_id} [{item.source_type}]: {item.summary}")

    return "\n".join(lines)
