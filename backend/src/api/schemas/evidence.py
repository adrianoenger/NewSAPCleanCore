"""API schemas for SPRINT-08: supplemental evidence datasets (ADR-017)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EvidenceInspectResponse(BaseModel):
    detected: bool
    dataset_type: str | None
    display_name: str
    capabilities: list[str]
    manifest: dict[str, Any]
    warnings: list[str]
    source_system_hint: str | None
    source_client_hint: str | None


class EvidenceDatasetRecord(BaseModel):
    id: int
    assessment_id: int
    dataset_type: str
    display_name: str
    source_filename: str
    source_sha256: str
    source_size_bytes: int
    importer_name: str
    importer_version: str
    status: str
    source_system_hint: str | None
    source_client_hint: str | None
    extracted_at: datetime | None
    capabilities: list[str]
    manifest: dict[str, Any]
    warning_summary: list[str]
    error: str | None
    created_at: datetime
    updated_at: datetime
    records_count: int
    correlation_summary: dict[str, int]
    pipeline_run_id: int | None
    pipeline_run_status: str | None

    model_config = {"from_attributes": True}


class EvidenceDatasetListResponse(BaseModel):
    assessment_id: int
    datasets: list[EvidenceDatasetRecord]
    total: int


class EvidenceRecordSummary(BaseModel):
    id: int
    dataset_id: int
    record_type: str
    capability: str
    object_name: str | None
    object_type: str | None
    package_name: str | None
    normalized_payload: dict[str, Any]
    source_locator: dict[str, Any]

    model_config = {"from_attributes": True}


class EvidenceCorrelationRecord(BaseModel):
    id: int
    target_type: str
    target_id: int | None
    status: str
    method: str
    score: float | None
    rationale: dict[str, Any] | None
    created_at: datetime
    evidence_record: EvidenceRecordSummary
    dataset_display_name: str
    dataset_type: str

    model_config = {"from_attributes": True}


class ObjectEvidenceCorrelationsResponse(BaseModel):
    assessment_id: int
    object_id: int
    correlations: list[EvidenceCorrelationRecord]
    total: int
