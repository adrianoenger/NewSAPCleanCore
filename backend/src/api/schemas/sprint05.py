"""API schemas for SPRINT-05: dependencies, ATC runs/findings, technical findings."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class DependencyRecord(BaseModel):
    id: int
    source_object_id: int
    target_name: str
    target_type: str | None
    dep_type: str
    source_line: int | None
    confidence: str

    model_config = {"from_attributes": True}


class DependenciesResponse(BaseModel):
    assessment_id: int
    object_id: int
    dependencies: list[DependencyRecord]
    total: int


# ---------------------------------------------------------------------------
# ATC diagnostics (before committing import)
# ---------------------------------------------------------------------------


class ATCDiagnosticsResponse(BaseModel):
    worksheet: str
    total_rows: int
    recognized_columns: list[str]
    missing_known_columns: list[str]
    unknown_columns: list[str]
    original_headers: list[str]
    validation_status: str
    warnings: list[str]


# ---------------------------------------------------------------------------
# ATC Run
# ---------------------------------------------------------------------------


class ATCRunRecord(BaseModel):
    id: int
    assessment_id: int
    source_filename: str
    selected_worksheet: str | None
    original_headers: list[Any]
    canonical_mapping: dict[str, Any]
    unknown_headers: list[Any]
    missing_known_headers: list[Any]
    importer_version: str
    imported_row_count: int
    warning_count: int
    validation_status: str
    warnings_summary: list[Any]
    imported_at: datetime

    model_config = {"from_attributes": True}


class ATCRunListResponse(BaseModel):
    assessment_id: int
    runs: list[ATCRunRecord]
    total: int


# ---------------------------------------------------------------------------
# ATC Finding
# ---------------------------------------------------------------------------


class ATCFindingRecord(BaseModel):
    id: int
    atc_run_id: int
    assessment_id: int
    source_row_number: int
    priority: int | None
    check_title: str | None
    check_message: str | None
    object_name_raw: str | None
    object_type_raw: str | None
    exemption_state: str | None
    package_name_raw: str | None
    first_found_on: date | None
    sap_note_number: str | None
    correlation_status: str | None
    correlated_object_id: int | None
    mapping_warnings: list[Any]

    model_config = {"from_attributes": True}


class ATCFindingsResponse(BaseModel):
    assessment_id: int
    atc_run_id: int
    findings: list[ATCFindingRecord]
    total: int
    correlation_summary: dict[str, int]


# ---------------------------------------------------------------------------
# Technical findings
# ---------------------------------------------------------------------------


class TechnicalFindingRecord(BaseModel):
    id: int
    assessment_id: int
    sap_object_id: int | None
    atc_finding_id: int | None
    source: str
    finding_type: str
    severity: str
    title: str
    details: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class TechnicalFindingsResponse(BaseModel):
    assessment_id: int
    findings: list[TechnicalFindingRecord]
    total: int
