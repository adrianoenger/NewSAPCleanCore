"""Pydantic schemas for business rule discovery endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class BusinessRuleRead(BaseModel):
    id: int
    assessment_id: int
    sap_object_id: int
    rule_type: str
    condition: str
    action: str
    confidence: float
    rationale: str
    evidence_refs: list[dict[str, Any]]
    status: str
    consolidated_into_id: int | None
    user_validated: bool
    user_validated_at: datetime | None
    user_notes: str | None
    provider: str
    model_id: str
    prompt_capability: str
    prompt_version: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BusinessRuleListResponse(BaseModel):
    assessment_id: int
    rules: list[BusinessRuleRead]
    total: int


class BusinessRuleValidateRequest(BaseModel):
    user_validated: bool
    user_notes: str | None = None
