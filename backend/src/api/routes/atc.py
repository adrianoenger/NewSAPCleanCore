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
from atc.importer import ImportResult, import_workbook, inspect_workbook
from persistence.database import get_session
from persistence.models import (
    Assessment,
    ATCCheck,
    ATCFinding,
    ATCRun,
    ATCRunStatus,
    SAPObject,
    TechnicalFinding,
    TechnicalFindingSource,
    TechnicalFindingSeverity,
)

router = APIRouter(prefix="/assessments/{assessment_id}", tags=["atc"])

_PRIORITY_SEVERITY: dict[int, str] = {
    1: TechnicalFindingSeverity.HIGH.value,
    2: TechnicalFindingSeverity.MEDIUM.value,
    3: TechnicalFindingSeverity.LOW.value,
}


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


def _correlate_findings(assessment_id: int, rows: list, session: Session) -> dict[int, tuple[str, int | None]]:
    """Return {row_index: (correlation_status, sap_object_id)} for each row."""
    # Load all SAP objects for this assessment indexed by name and type
    objects = list(session.scalars(
        select(SAPObject).where(SAPObject.assessment_id == assessment_id)
    ))
    by_name_type: dict[tuple[str, str], list[int]] = {}
    by_name: dict[str, list[int]] = {}
    for obj in objects:
        key = (obj.object_name.upper(), obj.object_type.upper())
        by_name_type.setdefault(key, []).append(obj.id)
        by_name.setdefault(obj.object_name.upper(), []).append(obj.id)

    result: dict[int, tuple[str, int | None]] = {}
    for idx, row in enumerate(rows):
        name = (row.canonical.get("object_name_raw") or "").strip().upper()
        otype = (row.canonical.get("object_type_raw") or "").strip().upper()
        if not name:
            result[idx] = ("UNMATCHED", None)
            continue

        if otype:
            matches = by_name_type.get((name, otype), [])
            if len(matches) == 1:
                result[idx] = ("MATCHED_EXACT", matches[0])
                continue
            if len(matches) > 1:
                result[idx] = ("AMBIGUOUS", None)
                continue
        # Fallback: name-only
        name_matches = by_name.get(name, [])
        if len(name_matches) == 1:
            result[idx] = ("MATCHED_HEURISTIC", name_matches[0])
        elif len(name_matches) > 1:
            result[idx] = ("AMBIGUOUS", None)
        else:
            result[idx] = ("UNMATCHED", None)
    return result


def _upsert_atc_check(check_title: str, session: Session) -> int:
    existing = session.scalars(
        select(ATCCheck).where(ATCCheck.check_title == check_title)
    ).first()
    if existing:
        return existing.id
    new_check = ATCCheck(check_title=check_title)
    session.add(new_check)
    session.flush()
    return new_check.id


def _derive_technical_findings(
    assessment_id: int,
    atc_run_id: int,
    rows,
    correlations: dict[int, tuple[str, int | None]],
    session: Session,
) -> int:
    """Derive TechnicalFinding records from ATC findings."""
    # Look up ATCFinding ids by row index
    atc_findings = list(session.scalars(
        select(ATCFinding)
        .where(ATCFinding.atc_run_id == atc_run_id)
        .order_by(ATCFinding.source_row_number)
    ))

    count = 0
    for af in atc_findings:
        severity = _PRIORITY_SEVERITY.get(af.priority or 0, TechnicalFindingSeverity.INFO.value)
        title = af.check_title or "ATC Finding"
        if af.object_name_raw:
            title = f"{title}: {af.object_name_raw}"

        tf = TechnicalFinding(
            assessment_id=assessment_id,
            sap_object_id=af.correlated_object_id,
            atc_finding_id=af.id,
            source=TechnicalFindingSource.ATC.value,
            finding_type=af.check_title or "UNKNOWN_CHECK",
            severity=severity,
            title=title,
            details={
                "priority": af.priority,
                "object_type": af.object_type_raw,
                "package": af.package_name_raw,
                "sap_note": af.sap_note_number,
                "correlation": af.correlation_status,
            },
        )
        session.add(tf)
        count += 1
    return count


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
    result: ImportResult = import_workbook(content, filename)
    diag = result.diagnostics

    if diag.validation_status == ATCRunStatus.REJECTED.value:
        raise HTTPException(
            status_code=422,
            detail={"message": "ATC file rejected", "warnings": diag.warnings},
        )

    correlations = _correlate_findings(assessment_id, result.rows, session)

    atc_run = ATCRun(
        assessment_id=assessment_id,
        source_filename=filename,
        file_fingerprint=result.file_fingerprint,
        selected_worksheet=diag.worksheet,
        original_headers=diag.original_headers,
        canonical_mapping=diag.canonical_mapping,
        unknown_headers=diag.unknown_columns,
        missing_known_headers=diag.missing_known_columns,
        importer_version="1.0",
        imported_row_count=len(result.rows),
        warning_count=len(diag.warnings),
        validation_status=diag.validation_status,
        warnings_summary=diag.warnings[:100],  # cap at 100 for DB storage
    )
    session.add(atc_run)
    session.flush()

    for idx, row in enumerate(result.rows):
        corr_status, corr_obj_id = correlations.get(idx, ("UNMATCHED", None))
        can = row.canonical
        check_title = can.get("check_title")
        atc_check_id = _upsert_atc_check(check_title, session) if check_title else None

        finding = ATCFinding(
            atc_run_id=atc_run.id,
            assessment_id=assessment_id,
            source_row_number=row.row_number,
            row_fingerprint=row.fingerprint,
            raw_payload=row.raw_payload,
            normalized_payload=None,
            mapping_warnings=row.warnings,
            priority=can.get("priority"),
            check_title=check_title,
            check_message=can.get("check_message"),
            object_name_raw=can.get("object_name_raw"),
            object_type_raw=can.get("object_type_raw"),
            exemption_state=can.get("exemption_state"),
            contact_person=can.get("contact_person"),
            package_name_raw=can.get("package_name_raw"),
            first_found_on=can.get("first_found_on"),
            object_responsible=can.get("object_responsible"),
            last_changed_by=can.get("last_changed_by"),
            sap_note_number=can.get("sap_note_number"),
            sap_note_short_text=can.get("sap_note_short_text"),
            referenced_application_component=can.get("referenced_application_component"),
            referenced_object_type=can.get("referenced_object_type"),
            referenced_object_name=can.get("referenced_object_name"),
            additional_info=can.get("additional_info"),
            simplification_item_category=can.get("simplification_item_category"),
            change_category=can.get("change_category"),
            change_category_description=can.get("change_category_description"),
            remarks=can.get("remarks"),
            correlation_status=corr_status,
            correlated_object_id=corr_obj_id,
            atc_check_id=atc_check_id,
        )
        session.add(finding)

    session.flush()

    # Derive technical findings from ATC
    _derive_technical_findings(assessment_id, atc_run.id, result.rows, correlations, session)

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
