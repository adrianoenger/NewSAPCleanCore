"""Pydantic schemas for Client, SAPSystem and Assessment endpoints."""

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
# SAPSystem
# ---------------------------------------------------------------------------


class SAPSystemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sid: str | None = Field(default=None, max_length=10)
    description: str | None = None


class SAPSystemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    name: str
    sid: str | None
    description: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


class AssessmentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sap_system_id: int
    name: str
    description: str | None
    status: str
    created_at: datetime
