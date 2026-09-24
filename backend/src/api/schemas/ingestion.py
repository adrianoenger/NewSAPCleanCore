"""Pydantic schemas for source ingestion endpoints."""

from datetime import datetime

from pydantic import BaseModel


class ScanCreate(BaseModel):
    source_path: str


class ScanRead(BaseModel):
    id: int
    assessment_id: int
    source_path: str
    status: str
    total_files: int
    scanned_files: int
    error: str | None
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class CategoryCount(BaseModel):
    category: str
    count: int


class ScanDetailRead(ScanRead):
    category_counts: list[CategoryCount]


class SourceFileRead(BaseModel):
    id: int
    scan_id: int
    assessment_id: int
    rel_path: str
    size_bytes: int
    mtime: float
    sha256: str
    category: str

    model_config = {"from_attributes": True}


class ScanConfigRead(BaseModel):
    scan_root: str
    demo_path: str
