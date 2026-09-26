"""Pydantic schemas for SAP knowledge (MCP) guidance endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SapKnowledgeReferenceRead(BaseModel):
    id: int
    target_type: str
    target_id: int
    provider: str
    query: str
    title: str
    reference: str
    summary: str
    retrieved_at: datetime
    reused: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_row(cls, row) -> "SapKnowledgeReferenceRead":
        return cls(
            id=row.id,
            target_type=row.target_type,
            target_id=row.target_id,
            provider=row.provider,
            query=row.query,
            title=row.title,
            reference=row.reference,
            summary=row.summary,
            retrieved_at=row.retrieved_at,
            reused=row.reused_from_id is not None,
        )


class SapKnowledgeGuidanceResponse(BaseModel):
    assessment_id: int
    target_type: str
    target_id: int
    references: list[SapKnowledgeReferenceRead]
