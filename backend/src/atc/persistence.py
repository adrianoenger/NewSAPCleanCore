"""Persist an ATC XLSX import: findings, SAP-object correlation, derived TechnicalFindings.

Extracted out of `api/routes/atc.py::import_atc_file` (SPRINT-17 CAP-005) so the demo seed can
persist a compact, reproducible ATC run the same way a real upload would, instead of duplicating
this logic.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from atc.importer import ImportResult, RawRow, import_workbook
from persistence.models import (
    ATCCheck,
    ATCFinding,
    ATCRun,
    ATCRunStatus,
    SAPObject,
    TechnicalFinding,
    TechnicalFindingSeverity,
    TechnicalFindingSource,
)

_PRIORITY_SEVERITY: dict[int, str] = {
    1: TechnicalFindingSeverity.HIGH.value,
    2: TechnicalFindingSeverity.MEDIUM.value,
    3: TechnicalFindingSeverity.LOW.value,
}


class ATCImportRejected(ValueError):
    """Raised when the workbook structure cannot be read reliably (ADR-016)."""

    def __init__(self, warnings: list[str]):
        super().__init__("ATC file rejected")
        self.warnings = warnings


class _ObjectIndex:
    """Name/type lookup over the assessment's current SAPObjects (ADR-016 correlation rules)."""

    def __init__(self, assessment_id: int, session: Session):
        self.by_name_type: dict[tuple[str, str], list[int]] = {}
        self.by_name: dict[str, list[int]] = {}
        rows = session.execute(
            select(SAPObject.id, SAPObject.object_name, SAPObject.object_type).where(
                SAPObject.assessment_id == assessment_id
            )
        )
        for obj_id, name, otype in rows:
            self.by_name_type.setdefault((name.upper(), otype.upper()), []).append(obj_id)
            self.by_name.setdefault(name.upper(), []).append(obj_id)

    def match(self, name_raw: str | None, type_raw: str | None) -> tuple[str, int | None]:
        name = (name_raw or "").strip().upper()
        otype = (type_raw or "").strip().upper()
        if not name:
            return ("UNMATCHED", None)
        if otype:
            matches = self.by_name_type.get((name, otype), [])
            if len(matches) == 1:
                return ("MATCHED_EXACT", matches[0])
            if len(matches) > 1:
                return ("AMBIGUOUS", None)
        name_matches = self.by_name.get(name, [])
        if len(name_matches) == 1:
            return ("MATCHED_HEURISTIC", name_matches[0])
        if len(name_matches) > 1:
            return ("AMBIGUOUS", None)
        return ("UNMATCHED", None)


def _correlate_findings(
    assessment_id: int, rows: Sequence[RawRow], session: Session
) -> dict[int, tuple[str, int | None]]:
    """Return {row_index: (correlation_status, sap_object_id)} for each row."""
    index = _ObjectIndex(assessment_id, session)
    return {
        idx: index.match(row.canonical.get("object_name_raw"), row.canonical.get("object_type_raw"))
        for idx, row in enumerate(rows)
    }


def recorrelate_atc_findings(assessment_id: int, session: Session) -> int:
    """Re-correlate every persisted ATC finding of the assessment against the current SAPObjects.

    Correlation is computed at import time, so an ATC file imported before the source was parsed
    (or before a reprocess changed the object set) would otherwise stay UNMATCHED / point at
    removed objects forever. Called by `parse_objects` finalize (SPRINT-18). Updates the derived
    TechnicalFinding.sap_object_id too. Returns how many findings changed.
    """
    index = _ObjectIndex(assessment_id, session)
    findings = session.execute(
        select(
            ATCFinding.id,
            ATCFinding.object_name_raw,
            ATCFinding.object_type_raw,
            ATCFinding.correlation_status,
            ATCFinding.correlated_object_id,
        ).where(ATCFinding.assessment_id == assessment_id)
    ).all()
    changed: list[dict] = []
    for fid, name, otype, status, obj_id in findings:
        new_status, new_obj = index.match(name, otype)
        if (new_status, new_obj) != (status, obj_id):
            changed.append({"id": fid, "correlation_status": new_status, "correlated_object_id": new_obj})
    if not changed:
        return 0
    session.execute(update(ATCFinding), changed)
    new_obj_by_finding = {c["id"]: c["correlated_object_id"] for c in changed}
    derived = session.execute(
        select(TechnicalFinding.id, TechnicalFinding.atc_finding_id).where(
            TechnicalFinding.assessment_id == assessment_id,
            TechnicalFinding.atc_finding_id.is_not(None),
        )
    ).all()
    tf_updates = [
        {"id": tf_id, "sap_object_id": new_obj_by_finding[af_id]}
        for tf_id, af_id in derived
        if af_id in new_obj_by_finding
    ]
    if tf_updates:
        session.execute(update(TechnicalFinding), tf_updates)
    session.flush()
    return len(changed)


def _upsert_atc_check(check_title: str, session: Session) -> int:
    existing = session.scalars(select(ATCCheck).where(ATCCheck.check_title == check_title)).first()
    if existing:
        return existing.id
    new_check = ATCCheck(check_title=check_title)
    session.add(new_check)
    session.flush()
    return new_check.id


def _derive_technical_findings(assessment_id: int, atc_run_id: int, session: Session) -> int:
    """Derive TechnicalFinding records from the just-persisted ATCFinding rows."""
    atc_findings = list(
        session.scalars(
            select(ATCFinding).where(ATCFinding.atc_run_id == atc_run_id).order_by(ATCFinding.source_row_number)
        )
    )

    count = 0
    for af in atc_findings:
        severity = _PRIORITY_SEVERITY.get(af.priority or 0, TechnicalFindingSeverity.INFO.value)
        title = af.check_title or "Finding ATC"
        if af.object_name_raw:
            title = f"{title}: {af.object_name_raw}"

        session.add(
            TechnicalFinding(
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
        )
        count += 1
    return count


def persist_atc_import(session: Session, assessment_id: int, filename: str, content: bytes) -> ATCRun:
    """Import an ATC XLSX and persist its run/findings/correlations/derived findings.

    Raises `ATCImportRejected` when the workbook structure cannot be read reliably — callers
    (the API route, the demo seed) decide how to surface that.
    """
    result: ImportResult = import_workbook(content, filename)
    diag = result.diagnostics

    if diag.validation_status == ATCRunStatus.REJECTED.value:
        raise ATCImportRejected(diag.warnings)

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
        warnings_summary=diag.warnings[:100],
    )
    session.add(atc_run)
    session.flush()

    for idx, row in enumerate(result.rows):
        corr_status, corr_obj_id = correlations.get(idx, ("UNMATCHED", None))
        can = row.canonical
        check_title = can.get("check_title")
        atc_check_id = _upsert_atc_check(check_title, session) if check_title else None

        session.add(
            ATCFinding(
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
        )

    session.flush()
    _derive_technical_findings(assessment_id, atc_run.id, session)
    return atc_run
