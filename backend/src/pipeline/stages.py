"""Stage definitions for the durable processing pipeline.

Each stage wraps an already-available deterministic capability (directory scan,
SAP object parsing, dependency detection) as a sequence of persisted WorkItems.
The wrapped modules (`ingestion.classifier`, `parsing.dispatcher`,
`parsing.dependency_detector`) are called as-is — their function signatures and
persisted domain models are not altered by this orchestration layer.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.business_rule_discovery import CAPABILITY as BUSINESS_RULE_DISCOVERY_CAPABILITY
from ai.business_rule_discovery.evidence_package import (
    build_business_rule_evidence_package,
)
from ai.business_rule_discovery.evidence_package import render_prompt as render_business_rule_prompt
from ai.business_rule_discovery.schema import BusinessRuleDiscoveryResult
from ai.business_rule_discovery.schema import validate_result as validate_business_rule_result
from ai.object_understanding import CAPABILITY as OBJECT_UNDERSTANDING_CAPABILITY
from ai.object_understanding.evidence_package import ObjectEvidencePackage, build_evidence_package, render_prompt
from ai.object_understanding.schema import ObjectUnderstandingResult, validate_result
from ai.provider import AIProviderError, StructuredCompletionRequest
from ai.providers import get_provider
from ai.registry import get_version
from evidence.adapters import get_adapter
from evidence.adapters.base import ImportBatchPlan
from evidence.correlation import correlate_dataset_records
from ingestion.classifier import classify
from parsing.dependency_detector import detect_dependencies
from parsing.dispatcher import parse_file
from persistence.models import (
    BusinessRule,
    BusinessRuleStatus,
    EvidenceDataset,
    EvidenceDatasetStatus,
    EvidenceRecord,
    ObjectUnderstanding,
    ObjectUnderstandingStatus,
    PipelineRun,
    SAPObject,
    SAPObjectDependency,
    ScanStatus,
    SourceFile,
    SourceScan,
    StageRun,
    WorkItem,
)
from pipeline.status import get_current_scan
from settings import get_settings


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class StageDefinition:
    key: str
    depends_on: tuple[str, ...]
    prepare: Callable[[StageRun, PipelineRun, Session], None]
    process_item: Callable[[WorkItem, StageRun, PipelineRun, Session], None]
    finalize: Callable[[StageRun, PipelineRun, Session], None] | None = None


# ---------------------------------------------------------------------------
# scan — wraps ingestion.classifier; produces SourceScan/SourceFile rows
# ---------------------------------------------------------------------------


def _same_directory(candidate_path: str, root: Path) -> bool:
    """True if `candidate_path` still exists on disk and resolves to `root`.

    A candidate scan whose directory has since been deleted or moved (e.g. an
    older, unrelated ingestion) can never be the one currently being scanned.
    """
    candidate = Path(candidate_path)
    try:
        return candidate.exists() and candidate.resolve(strict=True) == root
    except OSError:
        return False


def _scan_prepare(stage: StageRun, run: PipelineRun, session: Session) -> None:
    scan = session.get(SourceScan, run.source_scan_id) if run.source_scan_id else None
    root = Path(run.source_path).resolve(strict=True)

    if scan is None:
        # Reuse Step 1's already-completed ingestion for this directory instead of
        # re-walking the filesystem — SOURCE_SCAN stays the first canonical stage
        # (docs/architecture/pipeline-architecture.md), but its work is skipped when
        # already satisfied (ADR-005 "idempotency and incremental invalidation").
        reusable = get_current_scan(session, run.assessment_id)
        if reusable is not None and _same_directory(reusable.source_path, root):
            run.source_scan_id = reusable.id
            stage.total_items = reusable.scanned_files
            stage.completed_items = reusable.scanned_files
            session.commit()
            return

        scan = SourceScan(
            assessment_id=run.assessment_id,
            source_path=run.source_path,
            status=ScanStatus.PENDING.value,
        )
        session.add(scan)
        session.flush()
        run.source_scan_id = scan.id

    existing_keys = set(
        session.scalars(select(WorkItem.item_key).where(WorkItem.stage_run_id == stage.id))
    )

    created = 0
    for abs_path in sorted(root.rglob("*")):
        if not abs_path.is_file():
            continue
        try:
            rel = str(abs_path.resolve(strict=True).relative_to(root)).replace(os.sep, "/")
        except (OSError, ValueError):
            continue
        if rel in existing_keys:
            continue
        session.add(WorkItem(stage_run_id=stage.id, item_key=rel, payload={"rel_path": rel}))
        existing_keys.add(rel)
        created += 1

    stage.total_items = created + (stage.total_items or 0)
    scan.total_files = stage.total_items
    scan.status = ScanStatus.SCANNING.value
    session.commit()


def _scan_process_item(item: WorkItem, stage: StageRun, run: PipelineRun, session: Session) -> None:
    scan = session.get(SourceScan, run.source_scan_id)
    root = Path(run.source_path)
    rel = item.payload["rel_path"]
    abs_path = root / rel

    existing = session.scalars(
        select(SourceFile).where(SourceFile.scan_id == scan.id, SourceFile.rel_path == rel)
    ).first()
    if existing is None:
        stat = abs_path.stat()
        session.add(
            SourceFile(
                scan_id=scan.id,
                assessment_id=run.assessment_id,
                rel_path=rel,
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
                sha256=_sha256(abs_path),
                category=classify(rel),
            )
        )
    scan.scanned_files = session.scalar(
        select(func.count()).select_from(SourceFile).where(SourceFile.scan_id == scan.id)
    )


def _scan_finalize(stage: StageRun, run: PipelineRun, session: Session) -> None:
    scan = session.get(SourceScan, run.source_scan_id)
    if scan is None:
        return
    if stage.status == "completed":
        scan.status = ScanStatus.COMPLETED.value
        if scan.completed_at is None:
            scan.completed_at = datetime.now(timezone.utc)
    elif stage.status == "failed":
        scan.status = ScanStatus.FAILED.value
        scan.error = stage.error


# ---------------------------------------------------------------------------
# parse — wraps parsing.dispatcher.parse_file; produces SAPObject rows
# ---------------------------------------------------------------------------


def _parse_prepare(stage: StageRun, run: PipelineRun, session: Session) -> None:
    existing_keys = set(
        session.scalars(select(WorkItem.item_key).where(WorkItem.stage_run_id == stage.id))
    )
    files = list(
        session.scalars(
            select(SourceFile).where(
                SourceFile.scan_id == run.source_scan_id,
                SourceFile.category.in_(["abap_source", "ddic"]),
            )
        )
    )
    created = 0
    for sf in files:
        key = str(sf.id)
        if key in existing_keys:
            continue
        session.add(WorkItem(stage_run_id=stage.id, item_key=key, payload={"source_file_id": sf.id}))
        created += 1

    stage.total_items = created + (stage.total_items or 0)
    session.commit()


def canonical_object_key(object_type: str, object_name: str) -> str:
    """Deterministic Assessment-scoped identity for a SAP object (ADR-017).

    Stable across reprocessing so `SAPObject.id` — and everything correlated to it
    (ATC findings, supplemental evidence) — survives re-parsing the same object.
    """
    return f"{object_type.strip().upper()}::{object_name.strip().upper()}"


def _parse_process_item(item: WorkItem, stage: StageRun, run: PipelineRun, session: Session) -> None:
    sf = session.get(SourceFile, item.payload["source_file_id"])
    scan = session.get(SourceScan, sf.scan_id)
    abs_path = os.path.join(scan.source_path, sf.rel_path)

    with open(abs_path, encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    parsed = parse_file(content, sf.rel_path, sf.category)
    for p in parsed:
        key = canonical_object_key(p.object_type, p.object_name)
        existing = session.scalars(
            select(SAPObject).where(
                SAPObject.assessment_id == run.assessment_id, SAPObject.canonical_key == key
            )
        ).first()
        if existing is not None:
            existing.source_file_id = sf.id
            existing.object_type = p.object_type
            existing.object_name = p.object_name
            existing.description = p.description
            existing.line_start = p.line_start
            existing.line_end = p.line_end
            existing.attributes = p.attributes
            existing.last_seen_stage_run_id = stage.id
            existing.parsed_at = datetime.now(timezone.utc)
        else:
            session.add(
                SAPObject(
                    assessment_id=run.assessment_id,
                    source_file_id=sf.id,
                    object_type=p.object_type,
                    object_name=p.object_name,
                    canonical_key=key,
                    description=p.description,
                    line_start=p.line_start,
                    line_end=p.line_end,
                    attributes=p.attributes,
                    last_seen_stage_run_id=stage.id,
                )
            )
    session.flush()


def _parse_finalize(stage: StageRun, run: PipelineRun, session: Session) -> None:
    """Remove objects no longer produced by any file in this scan (ADR-017 reconciliation),
    then re-correlate every supplemental evidence dataset of this assessment against the
    now-current SAPObject set (ADR-017 amendment — SPRINT-08 post-completion).

    Runs once every file's WorkItem has completed, so an object that moved between two
    files in the same scan was already re-upserted (and stamped with this stage's id)
    before this check — only genuinely absent objects are removed.

    Re-correlation is required here, not optional: `EvidenceCorrelation.target_id` has no
    DB-level FK (it is a polymorphic column, pointing at SAPObject today and possibly other
    entity types later), so a SAPObject removed above would otherwise leave a silently
    dangling reference; a SAPObject added/renamed would otherwise never be retroactively
    matched against evidence imported before this reprocess.
    """
    if stage.status != "completed":
        return
    stale = list(
        session.scalars(
            select(SAPObject)
            .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
            .where(
                SourceFile.scan_id == run.source_scan_id,
                SAPObject.last_seen_stage_run_id.is_distinct_from(stage.id),
            )
        )
    )
    for obj in stale:
        session.delete(obj)
    session.flush()

    datasets = list(
        session.scalars(select(EvidenceDataset).where(EvidenceDataset.assessment_id == run.assessment_id))
    )
    for dataset in datasets:
        try:
            correlate_dataset_records(dataset.id, run.assessment_id, session)
        except Exception as exc:  # noqa: BLE001
            # Mirrors `_evidence_import_finalize`'s own safety net: `_run_stage` has no
            # try/except around its call to `finalize`, so an uncaught exception here would
            # propagate out of the background task silently, losing even the stale-object
            # reconciliation above (never committed) — the exact "stuck forever" failure mode
            # already fixed elsewhere in this sprint for the same underlying reason.
            dataset.status = EvidenceDatasetStatus.FAILED.value
            dataset.error = f"Re-correlation after source reprocessing failed: {exc}"[:2000]
    session.commit()


# ---------------------------------------------------------------------------
# detect_dependencies — wraps parsing.dependency_detector.detect_dependencies
# ---------------------------------------------------------------------------


def _dependencies_prepare(stage: StageRun, run: PipelineRun, session: Session) -> None:
    existing_keys = set(
        session.scalars(select(WorkItem.item_key).where(WorkItem.stage_run_id == stage.id))
    )
    # Scoped to objects parsed from *this* run's scan — not every object ever
    # parsed for the assessment — so an unrelated prior scan's deleted/moved
    # source files cannot fail this run's dependency-detection stage.
    objects = list(
        session.scalars(
            select(SAPObject)
            .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
            .where(SourceFile.scan_id == run.source_scan_id)
        )
    )
    created = 0
    for obj in objects:
        key = str(obj.id)
        if key in existing_keys:
            continue
        session.add(WorkItem(stage_run_id=stage.id, item_key=key, payload={"object_id": obj.id}))
        created += 1

    stage.total_items = created + (stage.total_items or 0)
    session.commit()


def _dependencies_process_item(
    item: WorkItem, stage: StageRun, run: PipelineRun, session: Session
) -> None:
    obj = session.get(SAPObject, item.payload["object_id"])
    source_file = session.get(SourceFile, obj.source_file_id)
    scan = session.get(SourceScan, source_file.scan_id)
    abs_path = os.path.join(scan.source_path, source_file.rel_path)

    with open(abs_path, encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    detected = detect_dependencies(content, obj.object_type, obj.attributes or {})

    for dep in list(
        session.scalars(select(SAPObjectDependency).where(SAPObjectDependency.source_object_id == obj.id))
    ):
        session.delete(dep)
    session.flush()

    for dep in detected:
        session.add(
            SAPObjectDependency(
                assessment_id=run.assessment_id,
                source_object_id=obj.id,
                target_name=dep.target_name,
                target_type=dep.target_type,
                dep_type=dep.dep_type,
                source_line=dep.source_line,
                confidence=dep.confidence,
            )
        )


# ---------------------------------------------------------------------------
# object_understanding — wraps ai.object_understanding; produces ObjectUnderstanding rows
# (ADR-006/ADR-012, BL-003: a 4th stage of the same source_processing PipelineRun, not a
# separate mechanism)
# ---------------------------------------------------------------------------


def _object_understanding_prepare(stage: StageRun, run: PipelineRun, session: Session) -> None:
    existing_keys = set(
        session.scalars(select(WorkItem.item_key).where(WorkItem.stage_run_id == stage.id))
    )
    # Scoped to this run's scan, mirroring detect_dependencies — an unrelated prior scan's
    # objects never enter this stage's WorkItem set.
    objects = list(
        session.scalars(
            select(SAPObject)
            .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
            .where(SourceFile.scan_id == run.source_scan_id)
        )
    )
    created = 0
    for obj in objects:
        key = str(obj.id)
        if key in existing_keys:
            continue
        session.add(WorkItem(stage_run_id=stage.id, item_key=key, payload={"object_id": obj.id}))
        created += 1

    stage.total_items = created + (stage.total_items or 0)
    session.commit()


def _resolve_evidence_refs(ref_ids: list[str], package: ObjectEvidencePackage) -> list[dict]:
    """Resolve the model's cited `ref_id` strings back to `{ref_id, source_type, entity_id}`
    so the API/UI can link straight to the cited source/ATC/evidence entity without
    reparsing ref_ids. Unknown ref_ids were already rejected by `validate_result`."""
    by_ref = {item.ref_id: item for item in package.all_items()}
    return [
        {"ref_id": item.ref_id, "source_type": item.source_type, "entity_id": item.entity_id}
        for ref_id in ref_ids
        if (item := by_ref.get(ref_id)) is not None
    ]


def _upsert_understanding(
    session: Session,
    existing: ObjectUnderstanding | None,
    *,
    assessment_id: int,
    sap_object_id: int,
    stage_run_id: int,
    status: str,
    functional_purpose: str,
    technical_purpose: str,
    concepts: list[str],
    confidence: float | None,
    rationale: str,
    evidence_refs: list[dict],
    provider: str,
    model_id: str,
    prompt_capability: str,
    prompt_version: str,
    error: str | None,
) -> None:
    row = existing or ObjectUnderstanding(assessment_id=assessment_id, sap_object_id=sap_object_id)
    row.status = status
    row.functional_purpose = functional_purpose
    row.technical_purpose = technical_purpose
    row.concepts = concepts
    row.confidence = confidence
    row.rationale = rationale
    row.evidence_refs = evidence_refs
    row.provider = provider
    row.model_id = model_id
    row.prompt_capability = prompt_capability
    row.prompt_version = prompt_version
    row.error = error
    row.stage_run_id = stage_run_id
    if existing is None:
        session.add(row)
    session.flush()


def _object_understanding_process_item(
    item: WorkItem, stage: StageRun, run: PipelineRun, session: Session
) -> None:
    obj = session.get(SAPObject, item.payload["object_id"])
    package = build_evidence_package(session, obj)
    prompt_version = get_version(OBJECT_UNDERSTANDING_CAPABILITY)
    provider = get_provider(get_settings())

    existing = session.scalars(
        select(ObjectUnderstanding).where(ObjectUnderstanding.sap_object_id == obj.id)
    ).first()

    # ADR-012: schema, evidence-reference and domain rules are validated before persistence.
    # A provider/validation failure is a legitimate terminal outcome for one object, not a
    # pipeline processing error — it is recorded as ObjectUnderstandingStatus.FAILED and the
    # WorkItem completes normally, rather than being retried against the same non-recoverable
    # response.
    try:
        completion = provider.complete_structured(
            StructuredCompletionRequest(
                system_prompt=prompt_version.system_prompt,
                user_prompt=render_prompt(package),
                json_schema=prompt_version.json_schema,
                schema_name=prompt_version.schema_name,
            )
        )
        result = ObjectUnderstandingResult.model_validate(completion.output)
        domain_errors = validate_result(result, package)
        if domain_errors:
            raise AIProviderError(f"Domain validation failed: {'; '.join(domain_errors)}")
    except (AIProviderError, ValidationError) as exc:
        _upsert_understanding(
            session,
            existing,
            assessment_id=run.assessment_id,
            sap_object_id=obj.id,
            stage_run_id=stage.id,
            status=ObjectUnderstandingStatus.FAILED.value,
            functional_purpose="",
            technical_purpose="",
            concepts=[],
            confidence=None,
            rationale="",
            evidence_refs=[],
            provider=provider.name,
            model_id=provider.model_id,
            prompt_capability=OBJECT_UNDERSTANDING_CAPABILITY,
            prompt_version=prompt_version.version,
            error=str(exc)[:2000],
        )
        return

    _upsert_understanding(
        session,
        existing,
        assessment_id=run.assessment_id,
        sap_object_id=obj.id,
        stage_run_id=stage.id,
        status=result.status.value,
        functional_purpose=result.functional_purpose,
        technical_purpose=result.technical_purpose,
        concepts=result.concepts,
        confidence=result.confidence,
        rationale=result.rationale,
        evidence_refs=_resolve_evidence_refs(result.evidence_refs, package),
        provider=completion.provider,
        model_id=completion.model_id,
        prompt_capability=OBJECT_UNDERSTANDING_CAPABILITY,
        prompt_version=prompt_version.version,
        error=None,
    )


# ---------------------------------------------------------------------------
# business_rule_discovery — wraps ai.business_rule_discovery; produces BusinessRule rows
# (ADR-008/ADR-012, Baseline "Business Rules are derived from persisted structured object
# understanding") — a 5th source_processing stage, mirroring object_understanding's pattern.
# ---------------------------------------------------------------------------


def _business_rule_discovery_prepare(stage: StageRun, run: PipelineRun, session: Session) -> None:
    existing_keys = set(
        session.scalars(select(WorkItem.item_key).where(WorkItem.stage_run_id == stage.id))
    )
    # Eligible objects are those with a COMPLETED understanding for this run's scan — an
    # INSUFFICIENT_CONTEXT/FAILED understanding gives business-rule discovery nothing more
    # to reason from than object_understanding already had, so it is not re-attempted here.
    objects = list(
        session.scalars(
            select(SAPObject)
            .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
            .join(ObjectUnderstanding, ObjectUnderstanding.sap_object_id == SAPObject.id)
            .where(
                SourceFile.scan_id == run.source_scan_id,
                ObjectUnderstanding.status == ObjectUnderstandingStatus.COMPLETED.value,
            )
        )
    )
    created = 0
    for obj in objects:
        key = str(obj.id)
        if key in existing_keys:
            continue
        session.add(WorkItem(stage_run_id=stage.id, item_key=key, payload={"object_id": obj.id}))
        created += 1

    stage.total_items = created + (stage.total_items or 0)
    session.commit()


def _business_rule_discovery_process_item(
    item: WorkItem, stage: StageRun, run: PipelineRun, session: Session
) -> None:
    obj = session.get(SAPObject, item.payload["object_id"])
    understanding = session.scalars(
        select(ObjectUnderstanding).where(ObjectUnderstanding.sap_object_id == obj.id)
    ).first()
    if understanding is None or understanding.status != ObjectUnderstandingStatus.COMPLETED.value:
        # Eligibility may have changed since `prepare` scoped this WorkItem (e.g. a concurrent
        # reprocess invalidated the understanding) — nothing to discover from here.
        return

    package = build_business_rule_evidence_package(session, obj, understanding)
    prompt_version = get_version(BUSINESS_RULE_DISCOVERY_CAPABILITY)
    provider = get_provider(get_settings())

    # ADR-012: schema, evidence-reference and domain rules are validated before persistence.
    # Unlike object_understanding's single upserted row, there is no natural per-object "failed"
    # row to write for a list of candidate rules — a provider/validation failure is recorded
    # durably on the WorkItem itself (the same field the engine would set on an uncaught
    # exception) and this run's already-persisted non-validated candidates for the object are
    # left untouched, rather than failing the whole stage for every other object or wiping a
    # prior successful result because of one transient failure.
    try:
        completion = provider.complete_structured(
            StructuredCompletionRequest(
                system_prompt=prompt_version.system_prompt,
                user_prompt=render_business_rule_prompt(package),
                json_schema=prompt_version.json_schema,
                schema_name=prompt_version.schema_name,
            )
        )
        result = BusinessRuleDiscoveryResult.model_validate(completion.output)
        domain_errors = validate_business_rule_result(result, package)
        if domain_errors:
            raise AIProviderError(f"Domain validation failed: {'; '.join(domain_errors)}")
    except (AIProviderError, ValidationError) as exc:
        item.last_error = str(exc)[:2000]
        return

    existing = list(
        session.scalars(
            select(BusinessRule).where(
                BusinessRule.sap_object_id == obj.id, BusinessRule.user_validated.is_(False)
            )
        )
    )
    for row in existing:
        session.delete(row)
    session.flush()

    for rule in result.rules:
        session.add(
            BusinessRule(
                assessment_id=run.assessment_id,
                sap_object_id=obj.id,
                rule_type=rule.rule_type.value,
                condition=rule.condition,
                action=rule.action,
                confidence=rule.confidence,
                rationale=rule.rationale,
                evidence_refs=_resolve_evidence_refs(rule.evidence_refs, package.object_package),
                status=BusinessRuleStatus.CANDIDATE.value,
                provider=completion.provider,
                model_id=completion.model_id,
                prompt_capability=BUSINESS_RULE_DISCOVERY_CAPABILITY,
                prompt_version=prompt_version.version,
                stage_run_id=stage.id,
            )
        )
    session.flush()


def _normalize_rule_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _evidence_ref_key(ref: dict) -> tuple:
    # `ref_id` (e.g. "SRC-1") is only unique within one object's own evidence package, not
    # across objects — keying on the full tuple avoids treating two different objects'
    # same-named ref_id as the same evidence when merging.
    return (ref.get("ref_id"), ref.get("source_type"), ref.get("entity_id"))


def _business_rule_discovery_finalize(stage: StageRun, run: PipelineRun, session: Session) -> None:
    """Basic consolidation/merge: candidate rules for this assessment that share the same
    rule_type and normalized condition+action are duplicates of one another. One survivor is
    kept CANDIDATE (preferring a user-validated row, so validated content is never relabeled);
    every other row in the group is marked MERGED with `consolidated_into_id` pointing at the
    survivor, and its evidence_refs are folded into the survivor's rather than lost. Recomputed
    from scratch on every run, since `process_item` above already regenerated each reprocessed
    object's own non-validated candidates.
    """
    if stage.status != "completed":
        return

    rows = list(
        session.scalars(
            select(BusinessRule)
            .where(
                BusinessRule.assessment_id == run.assessment_id,
                BusinessRule.status == BusinessRuleStatus.CANDIDATE.value,
            )
            .order_by(BusinessRule.id)
        )
    )
    groups: dict[tuple[str, str, str], list[BusinessRule]] = {}
    for row in rows:
        key = (row.rule_type, _normalize_rule_text(row.condition), _normalize_rule_text(row.action))
        groups.setdefault(key, []).append(row)

    for group in groups.values():
        if len(group) < 2:
            continue
        survivor = next((r for r in group if r.user_validated), group[0])
        seen_refs = {_evidence_ref_key(ref) for ref in survivor.evidence_refs}
        for row in group:
            if row is survivor:
                continue
            for ref in row.evidence_refs:
                if _evidence_ref_key(ref) not in seen_refs:
                    survivor.evidence_refs = [*survivor.evidence_refs, ref]
                    seen_refs.add(_evidence_ref_key(ref))
            if not row.user_validated:
                row.status = BusinessRuleStatus.MERGED.value
                row.consolidated_into_id = survivor.id

    session.commit()


SOURCE_PROCESSING_STAGES: list[StageDefinition] = [
    StageDefinition(
        key="scan",
        depends_on=(),
        prepare=_scan_prepare,
        process_item=_scan_process_item,
        finalize=_scan_finalize,
    ),
    StageDefinition(
        key="parse",
        depends_on=("scan",),
        prepare=_parse_prepare,
        process_item=_parse_process_item,
        finalize=_parse_finalize,
    ),
    StageDefinition(
        key="detect_dependencies",
        depends_on=("parse",),
        prepare=_dependencies_prepare,
        process_item=_dependencies_process_item,
    ),
    StageDefinition(
        key="object_understanding",
        depends_on=("detect_dependencies",),
        prepare=_object_understanding_prepare,
        process_item=_object_understanding_process_item,
    ),
    StageDefinition(
        key="business_rule_discovery",
        depends_on=("object_understanding",),
        prepare=_business_rule_discovery_prepare,
        process_item=_business_rule_discovery_process_item,
        finalize=_business_rule_discovery_finalize,
    ),
]


# ---------------------------------------------------------------------------
# import_evidence — wraps evidence.adapters.*; produces EvidenceRecord/EvidenceArtifact
# rows plus EvidenceCorrelation rows for a single EvidenceDataset (ADR-017/SPRINT-08)
# ---------------------------------------------------------------------------


def _require_dataset(run: PipelineRun, session) -> EvidenceDataset:
    dataset = session.get(EvidenceDataset, run.evidence_dataset_id)
    if dataset is None:
        raise ValueError(f"PipelineRun {run.id} has no EvidenceDataset {run.evidence_dataset_id}")
    return dataset


def _evidence_import_prepare(stage: StageRun, run: PipelineRun, session: Session) -> None:
    dataset = _require_dataset(run, session)
    # `_run_stage` returns immediately (skipping `finalize`) when `prepare` raises, so this
    # try/except is the only place that ever gets to mark the dataset FAILED for a
    # prepare-time error (unrecognized dataset_type, an unreadable/encrypted file, ...) —
    # without it, `dataset.status` stays stuck at INSPECTED/IMPORTING forever even though
    # the pipeline run correctly shows "failed". Everything from adapter lookup onward is
    # covered — an unregistered adapter is exactly as much a prepare-time failure as an
    # adapter-internal one.
    try:
        adapter = get_adapter(dataset.dataset_type)
        if adapter is None:
            raise ValueError(f"No adapter registered for dataset_type={dataset.dataset_type!r}")

        file_path = Path(run.source_path)
        inspection = adapter.inspect(file_path)
        batches = adapter.plan_batches(file_path, inspection)
    except Exception as exc:
        dataset.status = EvidenceDatasetStatus.FAILED.value
        dataset.error = str(exc)[:2000]
        session.commit()
        raise

    dataset.capabilities = inspection.capabilities
    dataset.manifest = inspection.manifest
    dataset.warning_summary = inspection.warnings
    dataset.source_system_hint = inspection.source_system_hint
    dataset.source_client_hint = inspection.source_client_hint
    dataset.status = EvidenceDatasetStatus.IMPORTING.value

    existing_keys = set(
        session.scalars(select(WorkItem.item_key).where(WorkItem.stage_run_id == stage.id))
    )
    created = 0
    for batch in batches:
        if batch.batch_key in existing_keys:
            continue
        session.add(WorkItem(stage_run_id=stage.id, item_key=batch.batch_key, payload=batch.payload))
        existing_keys.add(batch.batch_key)
        created += 1

    stage.total_items = created + (stage.total_items or 0)
    session.commit()


def _evidence_import_process_item(
    item: WorkItem, stage: StageRun, run: PipelineRun, session: Session
) -> None:
    dataset = _require_dataset(run, session)
    adapter = get_adapter(dataset.dataset_type)
    file_path = Path(run.source_path)
    batch = ImportBatchPlan(batch_key=item.item_key, payload=item.payload)

    outcome = adapter.import_batch(file_path, dataset, batch, session)
    if outcome.warnings:
        dataset.warning_summary = [*(dataset.warning_summary or []), *outcome.warnings]


def _evidence_import_finalize(stage: StageRun, run: PipelineRun, session: Session) -> None:
    dataset = _require_dataset(run, session)
    records_imported = session.scalar(
        select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.dataset_id == dataset.id)
    ) or 0

    if stage.status == "failed":
        dataset.status = EvidenceDatasetStatus.FAILED.value
        dataset.error = stage.error
    elif dataset.capabilities and records_imported > 0 and not dataset.warning_summary:
        dataset.status = EvidenceDatasetStatus.IMPORTED_FULL.value
    else:
        dataset.status = EvidenceDatasetStatus.IMPORTED_PARTIAL.value
        # `inspect()`'s capabilities are a *prediction* of what the adapter expects to find —
        # if zero batches actually produced a record despite that prediction, the adapter's
        # assumed structure most likely doesn't match this file (confirmed real case: a real
        # Signavio export nests keyFigureId/header/rows one level deeper — under `dataSet` —
        # than the invented profile assumed, so every chunk parsed as "no rows" silently).
        # IMPORTED_FULL must never claim success when nothing was actually extracted.
        if dataset.capabilities and records_imported == 0:
            dataset.warning_summary = [
                *(dataset.warning_summary or []),
                "No evidence records were extracted despite detected capabilities — the file's "
                "structure likely does not match what this adapter expects.",
            ]

    if dataset.extracted_at is None:
        dataset.extracted_at = datetime.now(timezone.utc)

    # `_run_stage` has no try/except around its call to `finalize` — an uncaught exception
    # here propagates all the way out of `run_pipeline` (a FastAPI BackgroundTask, so it is
    # logged and silently swallowed) with the dataset.status change above still uncommitted,
    # reproducing the exact "stuck forever" failure mode CAP-010 already fixed for `prepare`
    # (confirmed live: a real ~180k-record Panaya import crashed here before
    # `correlate_dataset_records` was fixed to avoid a >65535-bind-parameter query).
    try:
        correlate_dataset_records(dataset.id, run.assessment_id, session)
    except Exception as exc:  # noqa: BLE001
        dataset.status = EvidenceDatasetStatus.IMPORTED_PARTIAL.value
        dataset.warning_summary = [*(dataset.warning_summary or []), f"Correlation failed: {exc}"[:2000]]
        session.commit()


EVIDENCE_IMPORT_STAGES: list[StageDefinition] = [
    StageDefinition(
        key="import_evidence",
        depends_on=(),
        prepare=_evidence_import_prepare,
        process_item=_evidence_import_process_item,
        finalize=_evidence_import_finalize,
    ),
]

STAGES_BY_KIND: dict[str, list[StageDefinition]] = {
    "source_processing": SOURCE_PROCESSING_STAGES,
    "evidence_import": EVIDENCE_IMPORT_STAGES,
}
