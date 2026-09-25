"""ATC XLSX importer.

Pipeline:
  XLSX file → workbook/sheet discovery → header discovery + mapping
  → raw row preservation → canonical normalization
  → object correlation → technical interpretation

Contract: docs/data/atc-import-contract.md / ADR-016.
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

IMPORTER_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Known canonical column aliases — case-insensitive, whitespace-normalized
# ---------------------------------------------------------------------------

_CANONICAL_ALIASES: dict[str, str] = {
    "priority": "priority",
    "check title": "check_title",
    "check message": "check_message",
    "object name": "object_name_raw",
    "object type": "object_type_raw",
    "exemption state": "exemption_state",
    "contact person": "contact_person",
    "package": "package_name_raw",
    "first found on": "first_found_on",
    "object responsible": "object_responsible",
    "last changed by": "last_changed_by",
    "sap note number": "sap_note_number",
    "short text": "sap_note_short_text",
    "referenced application component": "referenced_application_component",
    "referenced object type": "referenced_object_type",
    "referenced object": "referenced_object_name",
    "additional info": "additional_info",
    "simplification item category": "simplification_item_category",
    "change category of piecelist items": "change_category",
    "description of change category": "change_category_description",
    "remarks": "remarks",
}

_ALL_KNOWN_FIELDS = set(_CANONICAL_ALIASES.values())

# Minimum fields needed for ACCEPTED_FULL
_FULL_REQUIRED = {"object_name_raw"}


def _normalize_header(h: str) -> str:
    return re.sub(r"\s+", " ", str(h).strip()).lower()


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RawRow:
    row_number: int
    raw_payload: dict[str, Any]
    normalized: dict[str, Any]
    canonical: dict[str, Any]
    fingerprint: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImportDiagnostics:
    worksheet: str
    total_rows: int
    recognized_columns: list[str]
    missing_known_columns: list[str]
    unknown_columns: list[str]
    original_headers: list[str]
    canonical_mapping: dict[str, str]
    validation_status: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    diagnostics: ImportDiagnostics
    rows: list[RawRow] = field(default_factory=list)
    file_fingerprint: str = ""


# ---------------------------------------------------------------------------
# Workbook / sheet discovery
# ---------------------------------------------------------------------------


def _find_best_sheet(wb: openpyxl.Workbook) -> tuple[str, openpyxl.worksheet.worksheet.Worksheet] | None:
    """Prefer 'Data' sheet; otherwise pick first non-empty sheet with a header row."""
    candidates = []
    for name in wb.sheetnames:
        ws = wb[name]
        rows = list(ws.iter_rows(min_row=1, max_row=2, values_only=True))
        if not rows or all(v is None for v in rows[0]):
            continue
        candidates.append((name, ws))

    if not candidates:
        return None

    preferred = next((c for c in candidates if c[0].strip().lower() == "data"), None)
    return preferred or candidates[0]


# ---------------------------------------------------------------------------
# Header mapping
# ---------------------------------------------------------------------------


def _map_headers(raw_headers: list[Any]) -> tuple[dict[int, str], list[str], list[str], list[str]]:
    """Map column positions to canonical field names.

    Returns:
        col_map: {col_index → canonical_field_name or ''}
        recognized: list of recognized canonical names
        unknown: list of unrecognized headers
        missing: list of known canonical fields not present in headers
    """
    col_map: dict[int, str] = {}
    recognized: list[str] = []
    unknown_headers: list[str] = []

    for idx, h in enumerate(raw_headers):
        if h is None:
            col_map[idx] = ""
            continue
        norm = _normalize_header(h)
        canonical = _CANONICAL_ALIASES.get(norm, "")
        col_map[idx] = canonical
        if canonical:
            recognized.append(canonical)
        else:
            unknown_headers.append(str(h))

    present = set(recognized)
    missing = [f for f in _ALL_KNOWN_FIELDS if f not in present]
    return col_map, recognized, unknown_headers, missing


# ---------------------------------------------------------------------------
# Type normalization helpers
# ---------------------------------------------------------------------------

_EXCEL_EPOCH = date(1899, 12, 30)


def _normalize_date(value: Any) -> date | None:
    """Normalize Excel date serial, Python date/datetime, or string to date."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        try:
            from datetime import timedelta
            return _EXCEL_EPOCH + timedelta(days=int(value))
        except (OverflowError, ValueError):
            return None
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def _normalize_priority(value: Any) -> tuple[int | None, str | None]:
    """Return (int_priority, warning) where warning is set for non-integer values."""
    if value is None:
        return None, None
    try:
        return int(value), None
    except (ValueError, TypeError):
        return None, f"Non-integer priority value: {value!r}"


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _fingerprint(payload: dict) -> str:
    h = hashlib.sha256()
    h.update(repr(sorted(payload.items())).encode())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Row normalization
# ---------------------------------------------------------------------------


def _normalize_row(
    row_num: int,
    raw_values: tuple,
    col_map: dict[int, str],
    raw_headers: list[Any],
) -> RawRow:
    raw_payload: dict[str, Any] = {}
    canonical: dict[str, Any] = {}
    warnings: list[str] = []

    for idx, val in enumerate(raw_values):
        header = str(raw_headers[idx]) if idx < len(raw_headers) else f"col_{idx}"
        raw_payload[header] = val
        field_name = col_map.get(idx, "")
        if not field_name:
            continue

        if field_name == "priority":
            prio, w = _normalize_priority(val)
            canonical["priority"] = prio
            if w:
                warnings.append(f"row {row_num}: {w}")
        elif field_name == "first_found_on":
            canonical["first_found_on"] = _normalize_date(val)
        else:
            canonical[field_name] = _str_or_none(val)

    fp = _fingerprint(raw_payload)
    return RawRow(
        row_number=row_num,
        raw_payload=raw_payload,
        normalized={},
        canonical=canonical,
        fingerprint=fp,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Public import API
# ---------------------------------------------------------------------------


def inspect_workbook(content: bytes, filename: str = "upload.xlsx") -> ImportDiagnostics:
    """Parse the workbook and return diagnostics without persisting anything."""
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except (InvalidFileException, Exception) as exc:
        return ImportDiagnostics(
            worksheet="",
            total_rows=0,
            recognized_columns=[],
            missing_known_columns=list(_ALL_KNOWN_FIELDS),
            unknown_columns=[],
            original_headers=[],
            canonical_mapping={},
            validation_status="REJECTED",
            warnings=[f"Cannot open workbook: {exc}"],
        )

    sheet_result = _find_best_sheet(wb)
    if sheet_result is None:
        return ImportDiagnostics(
            worksheet="",
            total_rows=0,
            recognized_columns=[],
            missing_known_columns=list(_ALL_KNOWN_FIELDS),
            unknown_columns=[],
            original_headers=[],
            canonical_mapping={},
            validation_status="REJECTED",
            warnings=["No usable worksheet found"],
        )

    sheet_name, ws = sheet_result
    rows_iter = ws.iter_rows(values_only=True)
    try:
        raw_headers = list(next(rows_iter))
    except StopIteration:
        return ImportDiagnostics(
            worksheet=sheet_name,
            total_rows=0,
            recognized_columns=[],
            missing_known_columns=list(_ALL_KNOWN_FIELDS),
            unknown_columns=[],
            original_headers=[],
            canonical_mapping={},
            validation_status="REJECTED",
            warnings=["No header row found"],
        )

    col_map, recognized, unknown, missing = _map_headers(raw_headers)
    data_rows = sum(1 for row in rows_iter if any(v is not None for v in row))

    if data_rows == 0:
        return ImportDiagnostics(
            worksheet=sheet_name,
            total_rows=0,
            recognized_columns=recognized,
            missing_known_columns=missing,
            unknown_columns=unknown,
            original_headers=[str(h) if h is not None else "" for h in raw_headers],
            canonical_mapping={v: k for k, v in col_map.items() if v},
            validation_status="REJECTED",
            warnings=["No data rows found"],
        )

    status = _determine_status(recognized, missing)
    warnings: list[str] = []
    if missing:
        warnings.append(f"Missing known columns: {missing}")

    return ImportDiagnostics(
        worksheet=sheet_name,
        total_rows=data_rows,
        recognized_columns=recognized,
        missing_known_columns=missing,
        unknown_columns=unknown,
        original_headers=[str(h) if h is not None else "" for h in raw_headers],
        canonical_mapping={v: col_map[k] for k, v in enumerate(col_map.values()) if v},
        validation_status=status,
        warnings=warnings,
    )


def _determine_status(recognized: list[str], missing: list[str]) -> str:
    """Determine ACCEPTED_FULL, ACCEPTED_PARTIAL, or REJECTED from recognized fields."""
    recognized_set = set(recognized)
    if not _FULL_REQUIRED.issubset(recognized_set):
        # Missing the single required field → partial but still import
        return "ACCEPTED_PARTIAL"
    # If any optional-but-useful fields are missing, still FULL
    return "ACCEPTED_FULL"


def import_workbook(content: bytes, filename: str = "upload.xlsx") -> ImportResult:
    """Full import: return ImportResult with diagnostics + all rows."""
    fp_hash = hashlib.sha256(content).hexdigest()

    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        diag = ImportDiagnostics(
            worksheet="",
            total_rows=0,
            recognized_columns=[],
            missing_known_columns=list(_ALL_KNOWN_FIELDS),
            unknown_columns=[],
            original_headers=[],
            canonical_mapping={},
            validation_status="REJECTED",
            warnings=[f"Cannot open workbook: {exc}"],
        )
        return ImportResult(diagnostics=diag, file_fingerprint=fp_hash)

    sheet_result = _find_best_sheet(wb)
    if sheet_result is None:
        diag = ImportDiagnostics(
            worksheet="",
            total_rows=0,
            recognized_columns=[],
            missing_known_columns=list(_ALL_KNOWN_FIELDS),
            unknown_columns=[],
            original_headers=[],
            canonical_mapping={},
            validation_status="REJECTED",
            warnings=["No usable worksheet"],
        )
        return ImportResult(diagnostics=diag, file_fingerprint=fp_hash)

    sheet_name, ws = sheet_result
    rows_iter = ws.iter_rows(values_only=True)

    try:
        raw_headers = list(next(rows_iter))
    except StopIteration:
        diag = ImportDiagnostics(
            worksheet=sheet_name,
            total_rows=0,
            recognized_columns=[],
            missing_known_columns=list(_ALL_KNOWN_FIELDS),
            unknown_columns=[],
            original_headers=[],
            canonical_mapping={},
            validation_status="REJECTED",
            warnings=["No header row"],
        )
        return ImportResult(diagnostics=diag, file_fingerprint=fp_hash)

    col_map, recognized, unknown, missing = _map_headers(raw_headers)

    rows: list[RawRow] = []
    global_warnings: list[str] = []
    if missing:
        global_warnings.append(f"Missing known columns: {missing}")

    for row_num, row_values in enumerate(rows_iter, start=2):
        if all(v is None for v in row_values):
            continue
        raw_row = _normalize_row(row_num, row_values, col_map, raw_headers)
        rows.append(raw_row)
        global_warnings.extend(raw_row.warnings)

    status = "REJECTED" if not rows else _determine_status(recognized, missing)

    str_headers = [str(h) if h is not None else "" for h in raw_headers]

    diag = ImportDiagnostics(
        worksheet=sheet_name,
        total_rows=len(rows),
        recognized_columns=recognized,
        missing_known_columns=missing,
        unknown_columns=unknown,
        original_headers=str_headers,
        canonical_mapping={v: k for k, v in col_map.items() if v},
        validation_status=status,
        warnings=global_warnings,
    )
    return ImportResult(diagnostics=diag, rows=rows, file_fingerprint=fp_hash)
