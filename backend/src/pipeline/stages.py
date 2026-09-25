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

from ingestion.classifier import classify
from parsing.dependency_detector import detect_dependencies
from parsing.dispatcher import parse_file
from persistence.models import (
    PipelineRun,
    SAPObject,
    SAPObjectDependency,
    ScanStatus,
    SourceFile,
    SourceScan,
    StageRun,
    WorkItem,
)


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


def _scan_prepare(stage: StageRun, run: PipelineRun, session: Session) -> None:
    scan = session.get(SourceScan, run.source_scan_id) if run.source_scan_id else None
    if scan is None:
        scan = SourceScan(
            assessment_id=run.assessment_id,
            source_path=run.source_path,
            status=ScanStatus.PENDING.value,
        )
        session.add(scan)
        session.flush()
        run.source_scan_id = scan.id

    root = Path(run.source_path).resolve(strict=True)
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


def _parse_process_item(item: WorkItem, stage: StageRun, run: PipelineRun, session: Session) -> None:
    sf = session.get(SourceFile, item.payload["source_file_id"])
    scan = session.get(SourceScan, sf.scan_id)
    abs_path = os.path.join(scan.source_path, sf.rel_path)

    with open(abs_path, encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    for obj in list(session.scalars(select(SAPObject).where(SAPObject.source_file_id == sf.id))):
        session.delete(obj)
    session.flush()

    parsed = parse_file(content, sf.rel_path, sf.category)
    for p in parsed:
        session.add(
            SAPObject(
                assessment_id=run.assessment_id,
                source_file_id=sf.id,
                object_type=p.object_type,
                object_name=p.object_name,
                description=p.description,
                line_start=p.line_start,
                line_end=p.line_end,
                attributes=p.attributes,
            )
        )


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


STAGE_DEFINITIONS: list[StageDefinition] = [
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
    ),
    StageDefinition(
        key="detect_dependencies",
        depends_on=("parse",),
        prepare=_dependencies_prepare,
        process_item=_dependencies_process_item,
    ),
]
