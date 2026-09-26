"""Pydantic schemas for SAP object parsing endpoints."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SAPObjectRead(BaseModel):
    id: int
    assessment_id: int
    source_file_id: int
    object_type: str
    object_name: str
    description: str
    line_start: int
    line_end: int | None
    application_id: int | None
    parsed_at: datetime

    model_config = {"from_attributes": True}


class ObjectUnderstandingRead(BaseModel):
    status: str
    functional_purpose: str
    technical_purpose: str
    concepts: list[str]
    confidence: float | None
    rationale: str
    evidence_refs: list[dict[str, Any]]
    provider: str
    model_id: str
    prompt_capability: str
    prompt_version: str
    error: str | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SAPObjectDetailRead(SAPObjectRead):
    attributes: dict[str, Any]
    understanding: ObjectUnderstandingRead | None = None


class SourceSnippetRead(BaseModel):
    """Bounded raw source text for Monaco (CAP-002, SPRINT-17). Read-only, never the full file
    when it exceeds the size cap — large files are truncated rather than loaded wholesale
    (Baseline core rule 10)."""

    object_id: int
    rel_path: str
    language: str
    content: str
    line_start: int
    line_end: int | None
    truncated: bool
    size_bytes: int
