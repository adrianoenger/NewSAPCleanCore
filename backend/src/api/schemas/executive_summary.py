"""Pydantic schemas for the Executive Summary endpoints (SPRINT-18 CAP-005)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ExecutiveSummaryEvidenceRef(BaseModel):
    ref_id: str
    source_type: str
    entity_id: int | None = None


class ExecutiveSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: int
    status: Literal["COMPLETED", "INSUFFICIENT_CONTEXT", "FAILED"]
    markdown: str
    evidence_refs: list[ExecutiveSummaryEvidenceRef]
    provider: str | None
    model_id: str | None
    prompt_version: str | None
    error: str | None
    stage_run_id: int | None
    generated_at: datetime
