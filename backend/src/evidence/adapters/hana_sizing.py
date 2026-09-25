"""HANA Sizing Report adapter (ADR-017 amendment — SPRINT-08 post-completion extension).

Parses the plain-text output of SAP's standard sizing report (`/SDF/HDB_SIZING`, transaction
`/SDF/HANA_SIZING` or the equivalent Quick Sizer/Readiness Check export) — a real, stable SAP
format (unlike Panaya/Signavio's original profiles, no invented guessing here). The report is a sequence of
ASCII boxes (`-` top/bottom rules, `|`-bordered content, an inner `|---|` header separator)
plus loose `label<spaces>value` metadata lines outside any box.

Recognition is structural, not per-box-title: any box whose data rows have a first column
matching a plausible SAP object name (`^[A-Z0-9_/]{2,30}$`) is treated as a table-level
volume/metric record (`USAGE_SIGNAL`, correlatable to a `SAPObject` by name); every other box's
rows become dataset-level sizing metrics (no object correlation). This avoids hard-coding the
report's ~15 box titles, which vary by SAP release/customer configuration.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from evidence.adapters.base import ImportBatchOutcome, ImportBatchPlan, InspectionResult
from persistence.models import EvidenceDataset, EvidenceRecord

DATASET_TYPE = "HANA_SIZING_REPORT"
IMPORTER_VERSION = "1.0"

_RULE_RE = re.compile(r"^-{10,}$")
_OBJECT_NAME_RE = re.compile(r"^[A-Z0-9_/]{2,30}$")
_SIGNATURE_RE = re.compile(r"SIZING RESULTS IN GiB|HDB_SIZING|HANA_SIZING", re.IGNORECASE)


def detect(filename: str, file_path: Path) -> bool:
    lower = filename.lower()
    if not lower.endswith(".txt"):
        return False
    if "hana_sizing" in lower or "hdb_sizing" in lower or "sizing" in lower:
        return True
    try:
        head = file_path.read_text(encoding="utf-8", errors="replace")[:8192]
    except OSError:
        return False
    return bool(_SIGNATURE_RE.search(head))


def _split_columns(row: str) -> list[str]:
    return [c.strip() for c in re.split(r"\s{2,}", row.strip()) if c.strip()]


def _extract_boxes(text: str) -> list[tuple[str, list[list[str]]]]:
    """Return [(section_header, [[col, ...], ...])] — one entry per ASCII box."""
    boxes: list[tuple[str, list[list[str]]]] = []
    current: list[str] | None = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if _RULE_RE.fullmatch(stripped):
            if current is None:
                current = []
            else:
                boxes.append(_parse_box(current))
                current = None
        elif current is not None and stripped.startswith("|") and stripped.endswith("|"):
            current.append(stripped[1:-1])

    return boxes


def _parse_box(inner_lines: list[str]) -> tuple[str, list[list[str]]]:
    separator_idx = next(
        (i for i, line in enumerate(inner_lines) if _RULE_RE.fullmatch(line.strip())), None
    )
    if separator_idx is None:
        return " ".join(l.strip() for l in inner_lines if l.strip()), []

    header = " ".join(re.sub(r"\s+", " ", l).strip() for l in inner_lines[:separator_idx] if l.strip())
    rows = [
        _split_columns(l)
        for l in inner_lines[separator_idx + 1 :]
        if l.strip() and not _RULE_RE.fullmatch(l.strip())
    ]
    return header, [r for r in rows if r]


def _extract_metadata(text: str) -> dict[str, str]:
    """Loose `label<spaces>value` lines outside any box — bounded, best-effort preview."""
    metadata: dict[str, str] = {}
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("|") or _RULE_RE.fullmatch(stripped):
            continue
        cols = _split_columns(stripped)
        if len(cols) == 2 and len(metadata) < 50:
            metadata[cols[0].rstrip(":")] = cols[1]
    return metadata


def _parsed_number(value: str) -> float | None:
    """SAP sizing reports use European formatting: '.' thousands, ',' decimal."""
    try:
        return float(value.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def inspect(file_path: Path) -> InspectionResult:
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return InspectionResult(dataset_type=DATASET_TYPE, display_name=file_path.name, warnings=[f"Cannot read file: {exc}"])

    boxes = _extract_boxes(text)
    metadata = _extract_metadata(text)

    table_metric_rows = 0
    metric_rows = 0
    for _header, rows in boxes:
        for row in rows:
            if len(row) >= 2 and _OBJECT_NAME_RE.match(row[0]):
                table_metric_rows += 1
            elif len(row) >= 2:
                metric_rows += 1

    warnings: list[str] = []
    if not boxes:
        warnings.append("No recognized sizing-report boxes found in this file")

    return InspectionResult(
        dataset_type=DATASET_TYPE,
        display_name=file_path.name,
        capabilities=["USAGE_SIGNAL"] if (table_metric_rows or metric_rows) else [],
        manifest={
            "metadata": metadata,
            "box_count": len(boxes),
            "table_metric_rows": table_metric_rows,
            "metric_rows": metric_rows,
        },
        source_system_hint=metadata.get("SID"),
        warnings=warnings,
    )


def plan_batches(file_path: Path, inspection: InspectionResult) -> list[ImportBatchPlan]:
    if inspection.manifest.get("box_count", 0) == 0:
        return []
    return [ImportBatchPlan(batch_key="full", payload={})]


def import_batch(
    file_path: Path, dataset: EvidenceDataset, batch: ImportBatchPlan, session: Session
) -> ImportBatchOutcome:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    boxes = _extract_boxes(text)
    imported = 0

    for box_index, (header, rows) in enumerate(boxes):
        for row_index, row in enumerate(rows):
            if len(row) < 2:
                continue
            is_object_row = _OBJECT_NAME_RE.match(row[0]) is not None
            source_key = f"box-{box_index}:row-{row_index}"
            fingerprint = hashlib.sha256(source_key.encode()).hexdigest()[:32]
            already = session.execute(
                select(EvidenceRecord.id).where(
                    EvidenceRecord.dataset_id == dataset.id, EvidenceRecord.record_fingerprint == fingerprint
                )
            ).first()
            if already is not None:
                continue

            values = [{"raw": v, "parsed": _parsed_number(v)} for v in row[1:]]
            session.add(
                EvidenceRecord(
                    dataset_id=dataset.id,
                    record_type="hana_sizing_table_metric" if is_object_row else "hana_sizing_metric",
                    capability="USAGE_SIGNAL",
                    source_key=source_key,
                    record_fingerprint=fingerprint,
                    object_name=row[0] if is_object_row else None,
                    normalized_payload={"label": row[0], "values": values},
                    source_locator={"section": header, "box_index": box_index, "row_index": row_index},
                )
            )
            imported += 1

    session.flush()
    return ImportBatchOutcome(records_imported=imported)
