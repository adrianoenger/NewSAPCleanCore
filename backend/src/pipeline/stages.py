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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from evidence.adapters import get_adapter
from evidence.adapters.base import ImportBatchPlan
from evidence.correlation import correlate_dataset_records
from ingestion.classifier import classify
from parsing.dependency_detector import detect_dependencies
from parsing.dispatcher import parse_file
from persistence.models import (
    EvidenceDataset,
    EvidenceDatasetStatus,
    EvidenceRecord,
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
