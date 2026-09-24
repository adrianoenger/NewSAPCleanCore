"""Pydantic schemas for Client and Assessment endpoints (SPRINT-04: Assessment-centric)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


class AssessmentCreate(BaseModel):
    client_id: int
    name: str = Field(..., min_length=1, max_length=200)
    sap_source_system: str | None = None
    description: str | None = None


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    name: str
    sap_source_system: str | None
    description: str | None
    status: str
    created_at: datetime


class AssessmentListItem(BaseModel):
    """Lightweight assessment row for the home grid — includes client name for display."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    client_name: str
    name: str
    sap_source_system: str | None
    status: str
    created_at: datetime
