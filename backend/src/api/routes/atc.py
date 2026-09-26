"""API routes for ATC XLSX import."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas.sprint05 import (
    ATCDiagnosticsResponse,
    ATCFindingRecord,
    ATCFindingsResponse,
    ATCRunListResponse,
    ATCRunRecord,
)
from atc.importer import inspect_workbook
from atc.persistence import ATCImportRejected, persist_atc_import
from persistence.database import get_session
from persistence.models import Assessment, ATCFinding, ATCRun

router = APIRouter(prefix="/assessments/{assessment_id}", tags=["atc"])


def _require_assessment(assessment_id: int, session: Session) -> Assessment:
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return a


# ---------------------------------------------------------------------------
# Inspect (preview diagnostics without persisting)
# ---------------------------------------------------------------------------


@router.post("/atc/inspect", response_model=ATCDiagnosticsResponse)
async def inspect_atc_file(
    assessment_id: int = Path(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ATCDiagnosticsResponse:
    """Return diagnostics for an ATC XLSX file without persisting anything."""
    _require_assessment(assessment_id, session)
    content = await file.read()
    diag = inspect_workbook(content, file.filename or "upload.xlsx")
    return ATCDiagnosticsResponse(
        worksheet=diag.worksheet,
        total_rows=diag.total_rows,
        recognized_columns=diag.recognized_columns,
        missing_known_columns=diag.missing_known_columns,
        unknown_columns=diag.unknown_columns,
        original_headers=diag.original_headers,
        validation_status=diag.validation_status,
        warnings=diag.warnings,
    )


# ---------------------------------------------------------------------------
# Import (persist findings)
# ---------------------------------------------------------------------------


@router.post("/atc/import", response_model=ATCRunRecord)
async def import_atc_file(
    assessment_id: int = Path(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ATCRunRecord:
    """Import an ATC XLSX file, persist findings, correlate with SAP objects."""
    _require_assessment(assessment_id, session)

    content = await file.read()
    filename = file.filename or "upload.xlsx"
    try:
        atc_run = persist_atc_import(session, assessment_id, filename, content)
    except ATCImportRejected as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": "ATC file rejected", "warnings": exc.warnings},
        ) from exc

    session.commit()
    session.refresh(atc_run)
    return ATCRunRecord.model_validate(atc_run)


# ---------------------------------------------------------------------------
# List runs + findings
# ---------------------------------------------------------------------------


@router.get("/atc/runs", response_model=ATCRunListResponse)
def list_atc_runs(
    assessment_id: int = Path(...),
    session: Session = Depends(get_session),
) -> ATCRunListResponse:
    _require_assessment(assessment_id, session)
    runs = list(session.scalars(
        select(ATCRun)
        .where(ATCRun.assessment_id == assessment_id)
        .order_by(ATCRun.imported_at.desc())
    ))
    return ATCRunListResponse(
        assessment_id=assessment_id,
        runs=[ATCRunRecord.model_validate(r) for r in runs],
        total=len(runs),
    )


@router.get("/atc/runs/{run_id}/findings", response_model=ATCFindingsResponse)
def list_atc_findings(
    assessment_id: int = Path(...),
    run_id: int = Path(...),
    limit: int = 200,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> ATCFindingsResponse:
    _require_assessment(assessment_id, session)
    run = session.get(ATCRun, run_id)
    if run is None or run.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="ATC run not found")

    findings = list(session.scalars(
        select(ATCFinding)
        .where(ATCFinding.atc_run_id == run_id)
        .order_by(ATCFinding.source_row_number)
        .offset(offset)
        .limit(limit)
    ))

    # Correlation summary
    from collections import Counter
    all_statuses = list(session.execute(
        select(ATCFinding.correlation_status).where(ATCFinding.atc_run_id == run_id)
    ))
    summary = dict(Counter(s[0] or "UNKNOWN" for s in all_statuses))

    return ATCFindingsResponse(
        assessment_id=assessment_id,
        atc_run_id=run_id,
        findings=[ATCFindingRecord.model_validate(f) for f in findings],
        total=run.imported_row_count,
        correlation_summary=summary,
    )
