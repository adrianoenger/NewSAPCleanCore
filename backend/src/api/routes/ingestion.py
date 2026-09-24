"""Source ingestion routes — directory scan lifecycle and file inventory."""

from collections import Counter
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.ingestion import (
    CategoryCount,
    ScanConfigRead,
    ScanCreate,
    ScanDetailRead,
    ScanRead,
    SourceFileRead,
)
from ingestion.scanner import run_scan
from persistence.database import get_session
from persistence.models import Assessment, ScanStatus, SourceFile, SourceScan
from settings import get_settings

assessments_router = APIRouter(prefix="/assessments", tags=["ingestion"])
config_router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    assessment = session.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


def _validate_scan_path(source_path: str, scan_root: str) -> Path:
    """Resolve both paths and enforce that source_path is inside scan_root (no symlink escape)."""
    try:
        root_real = Path(scan_root).resolve(strict=True)
        target_real = Path(source_path).resolve(strict=True)
    except (OSError, RuntimeError):
        raise HTTPException(status_code=400, detail="Invalid source path")
    if not target_real.is_dir():
        raise HTTPException(status_code=400, detail="source_path must be a directory")
    try:
        target_real.relative_to(root_real)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"source_path must be within scan_root ({scan_root})",
        )
    return target_real


@config_router.get("/config", response_model=ScanConfigRead)
def get_scan_config() -> ScanConfigRead:
    s = get_settings()
    return ScanConfigRead(scan_root=s.scan_root, demo_path=s.demo_source_path)


@assessments_router.post(
    "/{assessment_id}/scans",
    response_model=ScanRead,
    status_code=status.HTTP_201_CREATED,
)
def start_scan(
    assessment_id: int,
    body: ScanCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> SourceScan:
    _require_assessment(assessment_id, session)
    settings = get_settings()
    validated = _validate_scan_path(body.source_path, settings.scan_root)
    validated_str = str(validated)

    # Resume an interrupted scan for the same path instead of creating a duplicate
    existing = session.scalars(
        select(SourceScan).where(
            SourceScan.assessment_id == assessment_id,
            SourceScan.source_path == validated_str,
            SourceScan.status.in_([ScanStatus.PENDING.value, ScanStatus.SCANNING.value]),
        )
    ).first()

    if existing is not None:
        scan = existing
        scan.status = ScanStatus.PENDING.value
        scan.error = None
        session.commit()
        session.refresh(scan)
    else:
        scan = SourceScan(
            assessment_id=assessment_id,
            source_path=validated_str,
            status=ScanStatus.PENDING.value,
        )
        session.add(scan)
        session.commit()
        session.refresh(scan)

    background_tasks.add_task(
        run_scan, scan.id, validated_str, assessment_id, settings.database_url
    )
    return scan


@assessments_router.get("/{assessment_id}/scans", response_model=list[ScanRead])
def list_scans(
    assessment_id: int,
    session: Session = Depends(get_session),
) -> list[SourceScan]:
    _require_assessment(assessment_id, session)
    return list(
        session.scalars(
            select(SourceScan)
            .where(SourceScan.assessment_id == assessment_id)
            .order_by(SourceScan.started_at.desc())
        )
    )


@assessments_router.get("/{assessment_id}/scans/{scan_id}", response_model=ScanDetailRead)
def get_scan(
    assessment_id: int,
    scan_id: int,
    session: Session = Depends(get_session),
) -> ScanDetailRead:
    _require_assessment(assessment_id, session)
    scan = session.get(SourceScan, scan_id)
    if scan is None or scan.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Scan not found")
    counts = Counter(
        session.scalars(select(SourceFile.category).where(SourceFile.scan_id == scan_id))
    )
    return ScanDetailRead(
        **ScanRead.model_validate(scan).model_dump(),
        category_counts=[
            CategoryCount(category=cat, count=n) for cat, n in sorted(counts.items())
        ],
    )


@assessments_router.get("/{assessment_id}/source-files", response_model=list[SourceFileRead])
def list_source_files(
    assessment_id: int,
    scan_id: int | None = None,
    limit: int = 200,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[SourceFile]:
    _require_assessment(assessment_id, session)
    q = select(SourceFile).where(SourceFile.assessment_id == assessment_id)
    if scan_id is not None:
        q = q.where(SourceFile.scan_id == scan_id)
    return list(session.scalars(q.order_by(SourceFile.rel_path).offset(offset).limit(limit)))
