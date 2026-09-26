"""Deterministic application clustering (Baseline "AI Processing" — application discovery).

Groups a scan's `SAPObject`s into candidate application clusters using only deterministic
signals — no AI call here. Naming/description/domain/confidence assignment is a separate step
(the `application_discovery` pipeline stage, consuming `ai.application_discovery`) that treats
each `CandidateCluster` and its `signals` as citable, evidence-bound context.

Signals used:
- ``dependency``: `SAPObjectDependency.target_name`/`target_type` resolved to a `SAPObject` in
  the same scan via `canonical_key` (there is no FK to the target on `SAPObjectDependency` —
  resolution happens here, scoped to this scan's objects only). Primary signal.
- ``shared_package``: two objects each have a `MATCHED_*` correlation to the same non-null
  package name, via `ATCFinding.package_name_raw` or `EvidenceRecord.package_name`.
- ``shared_concept``: two objects' persisted `ObjectUnderstanding.concepts` share a tag that is
  not so common across this scan's understood objects that it stops being distinguishing
  (`_MAX_CONCEPT_SHARE`).

Baseline also allows clustering on "transactions" and "reliable process/usage correlations when
available" — the current `EvidenceRecord`/`EvidenceCorrelation` schema has no generic
cross-object join key for either beyond `package_name` (already covered by ``shared_package``);
inventing one would mean guessing a provider-specific payload shape, which ADR-017 forbids for
supplemental evidence. Left unexercised (see SPRINT-11 progress notes / BACKLOG).

An object with no signal connecting it to any other object still yields its own
single-member candidate cluster — grouping is never forced without evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import (
    ATCFinding,
    EvidenceCorrelation,
    EvidenceCorrelationStatus,
    EvidenceRecord,
    ObjectUnderstanding,
    SAPObject,
    SAPObjectDependency,
    SourceFile,
)

_TARGET_SAP_OBJECT = "SAP_OBJECT"
_MATCHED_STATUSES = (EvidenceCorrelationStatus.MATCHED_EXACT.value, EvidenceCorrelationStatus.MATCHED_HEURISTIC.value)

# A concept tag shared by more than this fraction of the scan's understood objects is too
# generic (e.g. "sap", "abap") to be a distinguishing clustering signal.
_MAX_CONCEPT_SHARE = 0.5


@dataclass(frozen=True)
class ClusterSignal:
    signal_type: str  # "dependency" | "shared_package" | "shared_concept"
    description: str
    dependency_id: int | None = None


@dataclass(frozen=True)
class CandidateCluster:
    object_ids: list[int]
    signals: list[ClusterSignal] = field(default_factory=list)


class _UnionFind:
    def __init__(self, ids: list[int]) -> None:
        self._parent = {i: i for i in ids}

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def build_candidate_clusters(session: Session, assessment_id: int, scan_id: int) -> list[CandidateCluster]:
    objects = list(
        session.scalars(
            select(SAPObject)
            .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
            .where(SourceFile.scan_id == scan_id)
        )
    )
    if not objects:
        return []

    by_id = {obj.id: obj for obj in objects}
    by_canonical_key = {obj.canonical_key: obj for obj in objects}
    object_ids = list(by_id)
    uf = _UnionFind(object_ids)
    pair_signals: dict[tuple[int, int], list[ClusterSignal]] = {}

    def link(a: int, b: int, signal: ClusterSignal) -> None:
        if a == b:
            return
        key = (a, b) if a < b else (b, a)
        pair_signals.setdefault(key, []).append(signal)
        uf.union(a, b)

    _link_dependencies(session, by_id, by_canonical_key, link)
    _link_shared_packages(session, object_ids, link)
    _link_shared_concepts(session, object_ids, link)

    groups: dict[int, list[int]] = {}
    for oid in object_ids:
        groups.setdefault(uf.find(oid), []).append(oid)

    clusters: list[CandidateCluster] = []
    for member_ids in groups.values():
        member_set = set(member_ids)
        signals = [
            signal
            for pair, pair_sigs in pair_signals.items()
            if pair[0] in member_set and pair[1] in member_set
            for signal in pair_sigs
        ]
        clusters.append(CandidateCluster(object_ids=sorted(member_ids), signals=signals))

    return clusters


def _link_dependencies(session, by_id, by_canonical_key, link) -> None:
    deps = list(
        session.scalars(select(SAPObjectDependency).where(SAPObjectDependency.source_object_id.in_(by_id)))
    )
    for dep in deps:
        target = None
        if dep.target_type:
            target = by_canonical_key.get(f"{dep.target_type.upper()}::{dep.target_name.upper()}")
        if target is None:
            for obj in by_id.values():
                if obj.object_name.upper() == dep.target_name.upper():
                    target = obj
                    break
        if target is None or target.id == dep.source_object_id:
            continue
        link(
            dep.source_object_id,
            target.id,
            ClusterSignal(
                signal_type="dependency",
                description=f"{by_id[dep.source_object_id].object_name} -> {target.object_name} ({dep.dep_type})",
                dependency_id=dep.id,
            ),
        )


def _link_shared_packages(session, object_ids, link) -> None:
    package_by_object: dict[int, set[str]] = {oid: set() for oid in object_ids}

    atc_rows = list(
        session.scalars(
            select(ATCFinding).where(
                ATCFinding.correlated_object_id.in_(object_ids), ATCFinding.package_name_raw.is_not(None)
            )
        )
    )
    for finding in atc_rows:
        package_by_object[finding.correlated_object_id].add(finding.package_name_raw)

    evd_rows = list(
        session.execute(
            select(EvidenceCorrelation.target_id, EvidenceRecord.package_name)
            .join(EvidenceRecord, EvidenceCorrelation.evidence_record_id == EvidenceRecord.id)
            .where(
                EvidenceCorrelation.target_type == _TARGET_SAP_OBJECT,
                EvidenceCorrelation.target_id.in_(object_ids),
                EvidenceCorrelation.status.in_(_MATCHED_STATUSES),
                EvidenceRecord.package_name.is_not(None),
            )
        )
    )
    for target_id, package_name in evd_rows:
        package_by_object[target_id].add(package_name)

    packages_to_objects: dict[str, list[int]] = {}
    for oid, packages in package_by_object.items():
        for pkg in packages:
            packages_to_objects.setdefault(pkg, []).append(oid)

    for pkg, oids in packages_to_objects.items():
        if len(oids) < 2:
            continue
        anchor = oids[0]
        for other in oids[1:]:
            link(anchor, other, ClusterSignal(signal_type="shared_package", description=f"package {pkg}"))


def _link_shared_concepts(session, object_ids, link) -> None:
    understandings = list(
        session.scalars(select(ObjectUnderstanding).where(ObjectUnderstanding.sap_object_id.in_(object_ids)))
    )
    concept_by_object = {u.sap_object_id: set(u.concepts or []) for u in understandings}
    concept_to_objects: dict[str, list[int]] = {}
    for oid, concepts in concept_by_object.items():
        for concept in concepts:
            concept_to_objects.setdefault(concept, []).append(oid)

    considered_objects = len(concept_by_object) or 1
    for concept, oids in concept_to_objects.items():
        if len(oids) < 2 or (len(oids) / considered_objects) > _MAX_CONCEPT_SHARE:
            continue
        anchor = oids[0]
        for other in oids[1:]:
            link(anchor, other, ClusterSignal(signal_type="shared_concept", description=f"concept '{concept}'"))
