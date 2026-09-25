"""Pydantic schemas for durable pipeline execution endpoints (SPRINT-06 / ADR-005)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PipelineRunCreate(BaseModel):
    source_path: str


class StageRunRecord(BaseModel):
    id: int
    stage_key: str
    sequence: int
    depends_on: list[str]
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None

    model_config = {"from_attributes": True}


class PipelineRunRecord(BaseModel):
    id: int
    assessment_id: int
    source_path: str
    source_scan_id: int | None
    status: str
    pause_requested: bool
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    stages: list[StageRunRecord]


class PipelineRunListResponse(BaseModel):
    assessment_id: int
    runs: list[PipelineRunRecord]
    total: int


class WorkItemRecord(BaseModel):
    id: int
    stage_run_id: int
    item_key: str
    status: str
    attempts: int
    max_attempts: int
    last_error: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class WorkItemsResponse(BaseModel):
    items: list[WorkItemRecord]
    total: int
