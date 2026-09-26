"""SAP object parsing routes — browse objects parsed by the durable pipeline (Step 3), object detail.

Parsing itself is triggered only by the durable pipeline (SPRINT-07 consolidation) —
there is no standalone manual parse endpoint anymore.
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.parsing import SAPObjectDetailRead, SAPObjectRead, SourceSnippetRead
from persistence.database import get_session
from persistence.models import ArtifactCategory, Assessment, SAPObject, SourceFile, SourceScan
from pipeline.status import get_current_scan

router = APIRouter(prefix="/assessments", tags=["parsing"])

# Bounded read (Baseline core rule 10) — Monaco shows a truncation notice past this size
# rather than the source viewer ever loading a large real-world file wholesale into memory.
_MAX_SOURCE_BYTES = 512_000

_CATEGORY_TO_LANGUAGE: dict[str, str] = {
    ArtifactCategory.ABAP_SOURCE.value: "abap",
    ArtifactCategory.XML_METADATA.value: "xml",
    ArtifactCategory.CDS.value: "abap",
    ArtifactCategory.DDIC.value: "plaintext",
    ArtifactCategory.CONFIGURATION.value: "yaml",
    ArtifactCategory.DOCUMENTATION.value: "markdown",
    ArtifactCategory.OTHER.value: "plaintext",
}


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


@router.get("/{assessment_id}/objects", response_model=list[SAPObjectRead])
def list_objects(
    assessment_id: int,
    object_type: str | None = None,
    limit: int = 200,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> list[SAPObject]:
    """Objects parsed from the *current* ingestion only — an older, superseded scan's
    objects are not returned, so a new ingestion invalidates stale results (SPRINT-07)."""
    _require_assessment(assessment_id, session)
    current_scan = get_current_scan(session, assessment_id)
    if current_scan is None:
        return []

    q = (
        select(SAPObject)
        .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
        .where(SourceFile.scan_id == current_scan.id)
    )
    if object_type:
        q = q.where(SAPObject.object_type == object_type)
    return list(
        session.scalars(q.order_by(SAPObject.object_name).offset(offset).limit(limit))
    )


@router.get("/{assessment_id}/objects/{object_id}", response_model=SAPObjectDetailRead)
def get_object(
    assessment_id: int,
    object_id: int,
    session: Session = Depends(get_session),
) -> SAPObject:
    _require_assessment(assessment_id, session)
    obj = session.get(SAPObject, object_id)
    if obj is None or obj.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="SAP object not found")
    return obj


@router.get("/{assessment_id}/objects/{object_id}/source", response_model=SourceSnippetRead)
def get_object_source(
    assessment_id: int,
    object_id: int,
    session: Session = Depends(get_session),
) -> SourceSnippetRead:
    """Raw source text for Monaco (CAP-002, SPRINT-17) — read from the scan's source directory
    on disk (nothing is persisted in the database), the same lookup path pipeline stages already
    use for dependency detection/AI evidence packages."""
    _require_assessment(assessment_id, session)
    obj = session.get(SAPObject, object_id)
    if obj is None or obj.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="SAP object not found")

    source_file = session.get(SourceFile, obj.source_file_id)
    if source_file is None:
        raise HTTPException(status_code=404, detail="Source file not found")
    scan = session.get(SourceScan, source_file.scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Source scan not found")

    # This endpoint returns raw file bytes over HTTP (unlike the internal-only read paths in
    # pipeline/stages.py and dependencies.py), so a poisoned/legacy `rel_path` must not be able to
    # escape the scan's source directory via `..` segments, an absolute path, or a symlink.
    if os.path.isabs(source_file.rel_path):
        raise HTTPException(status_code=422, detail="Invalid source path")
    base = os.path.realpath(scan.source_path)
    abs_path = os.path.realpath(os.path.join(base, source_file.rel_path))
    if os.path.commonpath([abs_path, base]) != base:
        raise HTTPException(status_code=422, detail="Invalid source path")

    try:
        size_bytes = os.path.getsize(abs_path)
        with open(abs_path, "rb") as fh:
            raw = fh.read(_MAX_SOURCE_BYTES)
    except OSError:
        raise HTTPException(status_code=422, detail="Cannot read source file")

    content = raw.decode("utf-8", errors="replace")
    truncated = size_bytes > _MAX_SOURCE_BYTES

    return SourceSnippetRead(
        object_id=object_id,
        rel_path=source_file.rel_path,
        language=_CATEGORY_TO_LANGUAGE.get(source_file.category, "plaintext"),
        content=content,
        line_start=obj.line_start,
        line_end=obj.line_end,
        truncated=truncated,
        size_bytes=size_bytes,
    )
