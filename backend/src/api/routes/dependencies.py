"""API routes for SAP object dependencies."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.sprint05 import DependenciesResponse, DependencyRecord
from parsing.dependency_detector import DetectedDependency, detect_dependencies
from persistence.database import get_session
from persistence.models import Assessment, SAPObject, SAPObjectDependency, SourceFile, SourceScan

router = APIRouter(prefix="/assessments/{assessment_id}", tags=["dependencies"])


def _get_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


@router.get("/objects/{object_id}/dependencies", response_model=DependenciesResponse)
def list_object_dependencies(
    assessment_id: int = Path(...),
    object_id: int = Path(...),
    session: Session = Depends(get_session),
) -> DependenciesResponse:
    """Return all detected dependencies for a SAP object."""
    _get_assessment(assessment_id, session)
    sap_obj = session.get(SAPObject, object_id)
    if sap_obj is None or sap_obj.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="SAP object not found")

    deps = list(
        session.scalars(
            select(SAPObjectDependency)
            .where(SAPObjectDependency.source_object_id == object_id)
            .order_by(SAPObjectDependency.dep_type, SAPObjectDependency.target_name)
        )
    )
    return DependenciesResponse(
        assessment_id=assessment_id,
        object_id=object_id,
        dependencies=[DependencyRecord.model_validate(d) for d in deps],
        total=len(deps),
    )


@router.post("/objects/{object_id}/detect-dependencies", status_code=200)
def detect_and_persist_dependencies(
    assessment_id: int = Path(...),
    object_id: int = Path(...),
    session: Session = Depends(get_session),
) -> dict:
    """Detect and persist dependencies for a single SAP object by re-reading its source file."""
    _get_assessment(assessment_id, session)
    sap_obj = session.get(SAPObject, object_id)
    if sap_obj is None or sap_obj.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="SAP object not found")

    source_file: SourceFile | None = session.get(SourceFile, sap_obj.source_file_id)
    if source_file is None:
        raise HTTPException(status_code=404, detail="Source file not found")
    scan: SourceScan | None = session.get(SourceScan, source_file.scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Source scan not found")

    import os
    abs_path = os.path.join(scan.source_path, source_file.rel_path)
    try:
        with open(abs_path, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        raise HTTPException(status_code=422, detail="Cannot read source file")

    detected: list[DetectedDependency] = detect_dependencies(
        content, sap_obj.object_type, sap_obj.attributes or {}
    )

    # Delete existing deps for this object before re-inserting
    from sqlalchemy import delete
    session.execute(
        delete(SAPObjectDependency).where(SAPObjectDependency.source_object_id == object_id)
    )

    persisted = 0
    for dep in detected:
        session.add(
            SAPObjectDependency(
                assessment_id=assessment_id,
                source_object_id=object_id,
                target_name=dep.target_name,
                target_type=dep.target_type,
                dep_type=dep.dep_type,
                source_line=dep.source_line,
                confidence=dep.confidence,
            )
        )
        persisted += 1

    session.commit()
    return {"detected": persisted, "object_id": object_id}


@router.post("/detect-dependencies", status_code=200)
def detect_all_dependencies(
    assessment_id: int = Path(...),
    session: Session = Depends(get_session),
) -> dict:
    """Detect and persist dependencies for all SAP objects in an assessment."""
    _get_assessment(assessment_id, session)

    objects = list(
        session.scalars(
            select(SAPObject).where(SAPObject.assessment_id == assessment_id)
        )
    )

    import os
    from sqlalchemy import delete

    # Clear existing
    session.execute(
        delete(SAPObjectDependency).where(SAPObjectDependency.assessment_id == assessment_id)
    )

    total_detected = 0
    for sap_obj in objects:
        source_file: SourceFile | None = session.get(SourceFile, sap_obj.source_file_id)
        if source_file is None:
            continue
        scan_row: SourceScan | None = session.get(SourceScan, source_file.scan_id)
        if scan_row is None:
            continue
        abs_path = os.path.join(scan_row.source_path, source_file.rel_path)
        try:
            with open(abs_path, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError:
            continue

        detected = detect_dependencies(content, sap_obj.object_type, sap_obj.attributes or {})
        for dep in detected:
            session.add(
                SAPObjectDependency(
                    assessment_id=assessment_id,
                    source_object_id=sap_obj.id,
                    target_name=dep.target_name,
                    target_type=dep.target_type,
                    dep_type=dep.dep_type,
                    source_line=dep.source_line,
                    confidence=dep.confidence,
                )
            )
            total_detected += 1

    session.commit()
    return {"assessment_id": assessment_id, "objects_processed": len(objects), "dependencies_detected": total_detected}
