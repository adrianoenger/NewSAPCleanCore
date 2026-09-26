"""Pydantic schemas for application discovery endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from api.schemas.business_rules import BusinessRuleRead


class ApplicationMemberRead(BaseModel):
    id: int
    object_type: str
    object_name: str

    model_config = {"from_attributes": True}


class ApplicationFindingRead(BaseModel):
    id: int
    object_id: int
    object_name: str
    check_title: str | None
    check_message: str | None


class ApplicationRead(BaseModel):
    id: int
    assessment_id: int
    name: str
    description: str
    domain: str
    confidence: float | None
    rationale: str
    evidence_refs: list[dict[str, Any]]
    clustering_signals: list[dict[str, Any]]
    status: str
    consolidated_into_id: int | None
    provider: str | None
    model_id: str | None
    prompt_capability: str | None
    prompt_version: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    member_count: int
    members: list[ApplicationMemberRead]

    model_config = {"from_attributes": True}


class ApplicationListResponse(BaseModel):
    assessment_id: int
    applications: list[ApplicationRead]
    total: int


class ApplicationDetailRead(ApplicationRead):
    business_rules: list[BusinessRuleRead]
    findings: list[ApplicationFindingRead]


class ApplicationRenameRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ApplicationMoveObjectRequest(BaseModel):
    object_id: int
    target_application_id: int | None = None


class ApplicationMoveObjectResponse(BaseModel):
    object_id: int
    application: ApplicationRead | None


class ApplicationMergeRequest(BaseModel):
    source_application_id: int
    target_application_id: int
