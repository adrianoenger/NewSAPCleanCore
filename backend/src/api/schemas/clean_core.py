"""Pydantic schemas for Clean Core Analysis (embedded into application read models)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CleanCoreAssessmentRead(BaseModel):
    id: int
    application_id: int
    status: str
    technical_risk: str | None
    technical_risk_rationale: str
    technical_risk_evidence_refs: list[dict[str, Any]]
    business_importance: str | None
    business_importance_rationale: str
    business_importance_evidence_refs: list[dict[str, Any]]
    business_importance_uses_process_usage_evidence: bool
    recommendation: str
    recommendation_rationale: str
    recommendation_evidence_refs: list[dict[str, Any]]
    confidence: float | None
    provider: str
    model_id: str
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
