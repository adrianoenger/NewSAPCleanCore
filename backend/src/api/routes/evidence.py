"""API routes for supplemental evidence datasets (SPRINT-08 / ADR-017).

Import lifecycle: inspect (preview, no persistence) -> create (persist +
fingerprint + store by reference + start a durable evidence_import
PipelineRun) -> list/detail (dataset KPIs, correlation summary, import
progress) -> object-scoped correlation lookup (drill-down from a SAPObject).
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Path as PathParam, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.evidence import (
    EvidenceCorrelationRecord,
    EvidenceDatasetListResponse,
    EvidenceDatasetRecord,
    EvidenceInspectResponse,
    ObjectEvidenceCorrelationsResponse,
)
from evidence.adapters import detect_adapter
from persistence.database import get_session
from persistence.models import (
    Assessment,
    EvidenceArtifact,
    EvidenceArtifactRole,
    EvidenceCorrelation,
    EvidenceDataset,
    EvidenceDatasetStatus,
    EvidenceRecord,
    PipelineRun,
)
from pipeline.engine import create_pipeline_run, run_pipeline
from settings import get_settings

router = APIRouter(prefix="/assessments/{assessment_id}", tags=["evidence"])

_TARGET_SAP_OBJECT = "SAP_OBJECT"


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


def _require_dataset(assessment_id: int, dataset_id: int, session: Session) -> EvidenceDataset:
    ds = session.get(EvidenceDataset, dataset_id)
    if ds is None or ds.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Evidence dataset not found")
    return ds


def _safe_basename(name: str) -> str:
    """Reduce an untrusted upload filename to a bare, safe basename.

    Rejects directory components, traversal (`..`), absolute paths and dotfiles
    before it ever reaches `Path` construction — an uploaded filename like
    `../../etc/passwd` or `C:\\Windows\\...` must never influence where we write.
    """
    base = PurePosixPath(name).name or PureWindowsPath(name).name
    if not base or base in (".", "..") or "/" in base or "\\" in base or base.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return base


def _resolve_under(root: Path, *parts: str) -> Path:
    """Join `parts` under `root` and verify the result did not escape it."""
    resolved_root = root.resolve()
    dest = (resolved_root / Path(*parts)).resolve()
    if os.path.commonpath([str(dest), str(resolved_root)]) != str(resolved_root):
        raise HTTPException(status_code=400, detail="Invalid filename")
    return dest


async def _stream_to_disk(file: UploadFile, dest: Path) -> tuple[str, int]:
    """Copy the upload to disk in chunks (never fully buffered) and return (sha256, size)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1 << 20):
            h.update(chunk)
            size += len(chunk)
            out.write(chunk)
    return h.hexdigest(), size


def _to_record(dataset: EvidenceDataset, session: Session) -> EvidenceDatasetRecord:
    records_count = session.scalar(
        select(func.count()).select_from(EvidenceRecord).where(EvidenceRecord.dataset_id == dataset.id)
    ) or 0

    correlation_summary: dict[str, int] = {}
    rows = session.execute(
        select(EvidenceCorrelation.status, func.count())
        .join(EvidenceRecord, EvidenceCorrelation.evidence_record_id == EvidenceRecord.id)
        .where(EvidenceRecord.dataset_id == dataset.id)
        .group_by(EvidenceCorrelation.status)
    ).all()
    for status, count in rows:
        correlation_summary[status] = count

    latest_run = session.scalars(
        select(PipelineRun)
        .where(PipelineRun.evidence_dataset_id == dataset.id)
        .order_by(PipelineRun.created_at.desc())
    ).first()

    return EvidenceDatasetRecord(
        id=dataset.id,
        assessment_id=dataset.assessment_id,
        dataset_type=dataset.dataset_type,
        display_name=dataset.display_name,
        source_filename=dataset.source_filename,
        source_sha256=dataset.source_sha256,
        source_size_bytes=dataset.source_size_bytes,
        importer_name=dataset.importer_name,
        importer_version=dataset.importer_version,
        status=dataset.status,
        source_system_hint=dataset.source_system_hint,
        source_client_hint=dataset.source_client_hint,
        extracted_at=dataset.extracted_at,
        capabilities=dataset.capabilities or [],
        manifest=dataset.manifest or {},
        warning_summary=dataset.warning_summary or [],
        error=dataset.error,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
        records_count=records_count,
        correlation_summary=correlation_summary,
        pipeline_run_id=latest_run.id if latest_run else None,
        pipeline_run_status=latest_run.status if latest_run else None,
    )


@router.post("/evidence-datasets/inspect", response_model=EvidenceInspectResponse)
async def inspect_evidence_package(
    assessment_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> EvidenceInspectResponse:
    """Preview a package's detected type/capabilities/manifest without persisting anything."""
    _require_assessment(assessment_id, session)
    filename = _safe_basename(file.filename or "upload.zip")

    settings = get_settings()
    tmp_dir = Path(settings.evidence_storage_path) / "_inspect_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = _resolve_under(tmp_dir, f"inspect_{filename}")
    await _stream_to_disk(file, tmp_path)
    try:
        # Detection sniffs the actual content (ZIP/XML/JSON structure) — the filename
        # alone rarely carries the provider's name in a real export.
        adapter = detect_adapter(filename, tmp_path)
        if adapter is None:
            return EvidenceInspectResponse(
                detected=False, dataset_type=None, display_name=filename, capabilities=[], manifest={},
                warnings=["Unrecognized evidence package format — no adapter matched this file"],
                source_system_hint=None, source_client_hint=None,
            )
        result = adapter.inspect(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return EvidenceInspectResponse(
        detected=True, dataset_type=result.dataset_type, display_name=result.display_name,
        capabilities=result.capabilities, manifest=result.manifest, warnings=result.warnings,
        source_system_hint=result.source_system_hint, source_client_hint=result.source_client_hint,
    )


@router.post("/evidence-datasets", response_model=EvidenceDatasetRecord, status_code=201)
async def create_evidence_dataset(
    assessment_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> EvidenceDatasetRecord:
    _require_assessment(assessment_id, session)
    filename = _safe_basename(file.filename or "upload.zip")
    settings = get_settings()

    dataset = EvidenceDataset(
        assessment_id=assessment_id,
        dataset_type="OTHER",
        display_name=filename,
        source_filename=filename,
        source_sha256="",
        source_size_bytes=0,
        importer_name="unknown",
        status=EvidenceDatasetStatus.INSPECTED.value,
    )
    session.add(dataset)
    session.flush()

    dest = _resolve_under(Path(settings.evidence_storage_path), str(dataset.id), filename)
    digest, size = await _stream_to_disk(file, dest)
    dataset.source_sha256 = digest
    dataset.source_size_bytes = size

    adapter = detect_adapter(filename, dest)
    if adapter is None:
        dataset.status = EvidenceDatasetStatus.FAILED.value
        dataset.error = "Unrecognized evidence package format — no adapter matched this file"
        session.commit()
        return _to_record(dataset, session)

    dataset.dataset_type = adapter.DATASET_TYPE
    dataset.importer_name = adapter.__name__.rsplit(".", 1)[-1]
    dataset.importer_version = getattr(adapter, "IMPORTER_VERSION", "1.0")
    session.add(
        EvidenceArtifact(
            dataset_id=dataset.id,
            member_name=filename,
            artifact_role=EvidenceArtifactRole.PRIMARY.value,
            size_bytes=size,
            sha256=digest,
            storage_path=str(dest),
        )
    )
    session.commit()

    run = create_pipeline_run(
        session, assessment_id, str(dest), kind="evidence_import", evidence_dataset_id=dataset.id,
    )
    background_tasks.add_task(run_pipeline, run.id, settings.database_url)

    return _to_record(dataset, session)


@router.get("/evidence-datasets", response_model=EvidenceDatasetListResponse)
def list_evidence_datasets(
    assessment_id: int,
    session: Session = Depends(get_session),
) -> EvidenceDatasetListResponse:
    _require_assessment(assessment_id, session)
    datasets = list(
        session.scalars(
            select(EvidenceDataset)
            .where(EvidenceDataset.assessment_id == assessment_id)
            .order_by(EvidenceDataset.created_at.desc())
        )
    )
    return EvidenceDatasetListResponse(
        assessment_id=assessment_id,
        datasets=[_to_record(d, session) for d in datasets],
        total=len(datasets),
    )


@router.get("/evidence-datasets/{dataset_id}", response_model=EvidenceDatasetRecord)
def get_evidence_dataset(
    assessment_id: int,
    dataset_id: int = PathParam(...),
    session: Session = Depends(get_session),
) -> EvidenceDatasetRecord:
    _require_assessment(assessment_id, session)
    dataset = _require_dataset(assessment_id, dataset_id, session)
    return _to_record(dataset, session)


@router.delete("/evidence-datasets/{dataset_id}", status_code=204)
def delete_evidence_dataset(
    assessment_id: int,
    dataset_id: int = PathParam(...),
    session: Session = Depends(get_session),
) -> None:
    """Delete a dataset and everything under it (artifacts/records/correlations cascade via
    existing FKs) plus its stored file on disk. Safe even mid-import: the background pipeline
    task's `run_pipeline` already returns quietly if its PipelineRun row has disappeared."""
    _require_assessment(assessment_id, session)
    dataset = _require_dataset(assessment_id, dataset_id, session)

    settings = get_settings()
    storage_dir = Path(settings.evidence_storage_path) / str(dataset.id)

    session.delete(dataset)
    session.commit()

    shutil.rmtree(storage_dir, ignore_errors=True)


@router.get("/objects/{object_id}/evidence-correlations", response_model=ObjectEvidenceCorrelationsResponse)
def get_object_evidence_correlations(
    assessment_id: int,
    object_id: int = PathParam(...),
    session: Session = Depends(get_session),
) -> ObjectEvidenceCorrelationsResponse:
    """Drill-down: supplemental evidence correlated to a specific SAPObject (evidence-model.md)."""
    _require_assessment(assessment_id, session)

    rows = list(
        session.execute(
            select(EvidenceCorrelation, EvidenceRecord, EvidenceDataset)
            .join(EvidenceRecord, EvidenceCorrelation.evidence_record_id == EvidenceRecord.id)
            .join(EvidenceDataset, EvidenceRecord.dataset_id == EvidenceDataset.id)
            .where(
                EvidenceDataset.assessment_id == assessment_id,
                EvidenceCorrelation.target_type == _TARGET_SAP_OBJECT,
                EvidenceCorrelation.target_id == object_id,
            )
            .order_by(EvidenceCorrelation.created_at.desc())
        )
    )

    correlations = [
        EvidenceCorrelationRecord(
            id=corr.id,
            target_type=corr.target_type,
            target_id=corr.target_id,
            status=corr.status,
            method=corr.method,
            score=corr.score,
            rationale=corr.rationale,
            created_at=corr.created_at,
            evidence_record=record,
            dataset_display_name=dataset.display_name,
            dataset_type=dataset.dataset_type,
        )
        for corr, record, dataset in rows
    ]
    return ObjectEvidenceCorrelationsResponse(
        assessment_id=assessment_id, object_id=object_id, correlations=correlations, total=len(correlations),
    )
