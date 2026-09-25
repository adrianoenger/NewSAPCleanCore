"""Deterministic EvidenceRecord -> canonical-entity correlation (ADR-017).

Generalizes the same exact/heuristic/ambiguous matching semantics used for ATC
findings (`api.routes.atc._correlate_findings`) to any EvidenceRecord that carries
a normalized object_name (optionally with object_type). AI may assist with
interpretation later, but this deterministic pass is what may ever mark a
correlation MATCHED_EXACT/MATCHED_HEURISTIC — never a guess.
"""
from __future__ import annotations

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from persistence.models import EvidenceCorrelation, EvidenceCorrelationStatus, EvidenceRecord, SAPObject

_TARGET_SAP_OBJECT = "SAP_OBJECT"

# Records are processed in id-ordered pages rather than loaded all at once — confirmed
# necessary against a real Signavio import: 4M+ records for one dataset pushed the backend
# container to ~20GB RSS and 100% CPU for many minutes before this fix (every record loaded
# as an ORM object simultaneously, plus a same-sized batch of pending EvidenceCorrelation
# objects held in the session's identity map). A page's correlations are inserted via Core
# `insert()` executemany (bounded per-row params, not one giant multi-row statement), then
# the page's ORM objects are expunged before the next page is fetched.
_PAGE_SIZE = 5000


def correlate_dataset_records(dataset_id: int, assessment_id: int, session: Session) -> dict[str, int]:
    """(Re-)correlate every EvidenceRecord of `dataset_id` against this Assessment's
    SAPObjects. Idempotent: prior correlations for these records are replaced.

    Returns a {status: count} summary.
    """
    objects = list(session.scalars(select(SAPObject).where(SAPObject.assessment_id == assessment_id)))
    by_name_type: dict[tuple[str, str], list[int]] = {}
    by_name: dict[str, list[int]] = {}
    for obj in objects:
        by_name_type.setdefault((obj.object_name.upper(), obj.object_type.upper()), []).append(obj.id)
        by_name.setdefault(obj.object_name.upper(), []).append(obj.id)

    # A subquery, not an `IN (...)` list of Python ids — a dataset can carry well over
    # PostgreSQL's 65535-bind-parameter limit (confirmed: a real Panaya import produced
    # ~180k records in one dataset), which an id-list `IN` clause would blow past outright.
    session.execute(
        delete(EvidenceCorrelation).where(
            EvidenceCorrelation.evidence_record_id.in_(
                select(EvidenceRecord.id).where(EvidenceRecord.dataset_id == dataset_id)
            )
        )
    )
    session.flush()

    summary = {s.value: 0 for s in EvidenceCorrelationStatus}
    last_id = 0
    while True:
        page = list(
            session.scalars(
                select(EvidenceRecord)
                .where(EvidenceRecord.dataset_id == dataset_id, EvidenceRecord.id > last_id)
                .order_by(EvidenceRecord.id)
                .limit(_PAGE_SIZE)
            )
        )
        if not page:
            break
        last_id = page[-1].id

        rows = []
        for rec in page:
            name = (rec.object_name or "").strip().upper()
            if not name:
                status = EvidenceCorrelationStatus.NOT_APPLICABLE.value
                target_id, method = None, "no_object_identity"
            else:
                otype = (rec.object_type or "").strip().upper()
                exact_matches = by_name_type.get((name, otype), []) if otype else []
                if len(exact_matches) == 1:
                    status, target_id, method = (
                        EvidenceCorrelationStatus.MATCHED_EXACT.value, exact_matches[0], "object_name_type_exact",
                    )
                elif len(exact_matches) > 1:
                    status, target_id, method = (
                        EvidenceCorrelationStatus.AMBIGUOUS.value, None, "object_name_type_exact",
                    )
                else:
                    name_matches = by_name.get(name, [])
                    if len(name_matches) == 1:
                        status, target_id, method = (
                            EvidenceCorrelationStatus.MATCHED_HEURISTIC.value, name_matches[0], "object_name_only",
                        )
                    elif len(name_matches) > 1:
                        status, target_id, method = EvidenceCorrelationStatus.AMBIGUOUS.value, None, "object_name_only"
                    else:
                        status, target_id, method = EvidenceCorrelationStatus.UNMATCHED.value, None, "object_name_only"

            rows.append({
                "evidence_record_id": rec.id,
                "target_type": _TARGET_SAP_OBJECT,
                "target_id": target_id,
                "status": status,
                "method": method,
                "rationale": {"object_name": rec.object_name, "object_type": rec.object_type},
            })
            summary[status] += 1

        session.execute(insert(EvidenceCorrelation.__table__), rows)
        session.flush()
        # Expunge only this page's EvidenceRecord objects, never `session.expunge_all()` —
        # the caller (`_evidence_import_finalize`) holds its own `dataset`/`run`/`stage`
        # objects in the same session across this call and must not have them silently
        # detached (a detached object's later attribute changes are never flushed/committed).
        for rec in page:
            session.expunge(rec)

    return summary
