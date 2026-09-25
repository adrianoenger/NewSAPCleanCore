"""SAP Readiness Check for SAP S/4HANA Conversion adapter (ADR-017 amendment —
SPRINT-08 post-completion extension).

Parses the official SAP-generated Word report (a real, stable SAP template — unlike
Panaya/Signavio's original profiles, no invented guessing here). The document's ~40 embedded tables vary in
count/order across customers, so tables are classified by their **header row text**, not by
index — the same structural-recognition approach as the Panaya adapter's XML tag matching.
Recognized table kinds:

- System metadata (`SID`, product/DB/OS versions) → dataset manifest / source_system_hint.
- Simplification Items (`Title`/`Effort Ranking`/`SAP Note`/...) → `S4_CONVERSION_SIGNAL`.
- Custom code checks (`Check Type`/`Number Issues Found`) → `S4_CONVERSION_SIGNAL`.
- Table volume/sizing (`Table`/`...Size in GiB`) → `USAGE_SIGNAL`, correlatable by table name —
  the same signal `evidence.adapters.hana_sizing` extracts from the standalone sizing report.

Any table whose header doesn't match a recognized kind is counted in
`manifest.unrecognized_tables`, never dropped silently or guessed at.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

import docx
from sqlalchemy import select
from sqlalchemy.orm import Session

from evidence.adapters.base import ImportBatchOutcome, ImportBatchPlan, InspectionResult
from persistence.models import EvidenceDataset, EvidenceRecord

DATASET_TYPE = "SAP_READINESS_CHECK"
IMPORTER_VERSION = "1.0"

_OBJECT_NAME_RE = re.compile(r"^[A-Z0-9_/]{2,30}$")


def detect(filename: str, file_path: Path) -> bool:
    lower = filename.lower()
    if not lower.endswith(".docx"):
        return False
    if "readiness" in lower:
        return True
    try:
        with zipfile.ZipFile(file_path) as zf:
            if "word/document.xml" not in zf.namelist():
                return False
            with zf.open("word/document.xml") as fh:
                head = fh.read(32768).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, KeyError):
        return False
    return "Readiness Check" in head


def _header_texts(table) -> list[str]:
    if not table.rows:
        return []
    return [c.text.strip() for c in table.rows[0].cells]


def _classify(headers: list[str]) -> str | None:
    joined = " | ".join(headers)
    if "Check Type" in joined and "Number Issues Found" in joined:
        return "custom_code_check"
    if ("Simplification item title" in joined or "Title" in headers) and (
        "Effort Ranking" in joined or "Compatibility Scope ID" in joined
    ):
        return "simplification_item"
    if "Table" in headers and ("Size in GiB" in joined or "Size On Disk" in joined or "GiB" in joined):
        return "table_volume"
    if "SID" in headers and len(headers) <= 6:
        return "system_metadata"
    return None


def _row_dict(headers: list[str], row) -> dict[str, str]:
    cells = [c.text.strip() for c in row.cells]
    return {headers[i] if i < len(headers) else f"col_{i}": v for i, v in enumerate(cells)}


def _classified_tables(doc) -> list[tuple[int, str, list[str]]]:
    result = []
    for idx, table in enumerate(doc.tables):
        headers = _header_texts(table)
        kind = _classify(headers)
        if kind:
            result.append((idx, kind, headers))
    return result


def inspect(file_path: Path) -> InspectionResult:
    try:
        doc = docx.Document(file_path)
    except Exception as exc:  # noqa: BLE001 — python-docx raises assorted exceptions for bad files
        return InspectionResult(
            dataset_type=DATASET_TYPE, display_name=file_path.name, warnings=[f"Cannot read .docx file: {exc}"]
        )

    classified = _classified_tables(doc)
    kind_counts: dict[str, int] = {}
    for _idx, kind, _headers in classified:
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    unrecognized = len(doc.tables) - len(classified)

    source_system_hint = None
    for idx, kind, headers in classified:
        if kind == "system_metadata" and len(doc.tables[idx].rows) >= 2:
            row = _row_dict(headers, doc.tables[idx].rows[1])
            source_system_hint = row.get("SID") or source_system_hint

    _CAPABILITY_BY_KIND = {
        "simplification_item": "S4_CONVERSION_SIGNAL",
        "custom_code_check": "S4_CONVERSION_SIGNAL",
        "table_volume": "USAGE_SIGNAL",
    }
    capabilities = sorted({_CAPABILITY_BY_KIND[k] for k in kind_counts if k in _CAPABILITY_BY_KIND})

    warnings: list[str] = []
    if not classified:
        warnings.append("No recognized Readiness Check tables found in this document")

    return InspectionResult(
        dataset_type=DATASET_TYPE,
        display_name=file_path.name,
        capabilities=capabilities,
        manifest={
            "table_count": len(doc.tables),
            "recognized_table_counts": kind_counts,
            "unrecognized_tables": unrecognized,
        },
        source_system_hint=source_system_hint,
        warnings=warnings,
    )


def plan_batches(file_path: Path, inspection: InspectionResult) -> list[ImportBatchPlan]:
    doc = docx.Document(file_path)
    return [
        ImportBatchPlan(batch_key=f"table-{idx}", payload={"table_index": idx, "kind": kind})
        for idx, kind, _headers in _classified_tables(doc)
    ]


def import_batch(
    file_path: Path, dataset: EvidenceDataset, batch: ImportBatchPlan, session: Session
) -> ImportBatchOutcome:
    table_index = batch.payload["table_index"]
    kind = batch.payload["kind"]
    doc = docx.Document(file_path)
    table = doc.tables[table_index]
    headers = _header_texts(table)
    imported = 0

    if kind == "system_metadata":
        return ImportBatchOutcome(records_imported=0)  # captured in inspect()'s manifest only

    capability = "USAGE_SIGNAL" if kind == "table_volume" else "S4_CONVERSION_SIGNAL"
    record_type = f"readiness_check_{kind}"

    for row_index, row in enumerate(table.rows[1:]):
        payload = _row_dict(headers, row)
        if not any(payload.values()):
            continue
        source_key = f"table-{table_index}:row-{row_index}"
        fingerprint = hashlib.sha256(source_key.encode()).hexdigest()[:32]
        already = session.execute(
            select(EvidenceRecord.id).where(
                EvidenceRecord.dataset_id == dataset.id, EvidenceRecord.record_fingerprint == fingerprint
            )
        ).first()
        if already is not None:
            continue

        object_name: str | None = None
        if kind == "table_volume":
            candidate = payload.get(headers[0], "") if headers else ""
            if _OBJECT_NAME_RE.match(candidate):
                object_name = candidate

        session.add(
            EvidenceRecord(
                dataset_id=dataset.id,
                record_type=record_type,
                capability=capability,
                source_key=source_key,
                record_fingerprint=fingerprint,
                object_name=object_name,
                normalized_payload=payload,
                source_locator={"table_index": table_index, "row_index": row_index, "kind": kind},
            )
        )
        imported += 1

    session.flush()
    return ImportBatchOutcome(records_imported=imported)
