"""Pydantic schemas for the AI Copilot endpoint (SPRINT-16, ADR-010)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CopilotFocusKind = Literal["sap_object", "business_rule", "application"]


class CopilotSelectionRequest(BaseModel):
    kind: CopilotFocusKind
    id: int


class CopilotMessageTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CopilotAskRequest(BaseModel):
    question: str
    view: str
    selection: CopilotSelectionRequest | None = None
    history: list[CopilotMessageTurn] = Field(default_factory=list)


class CopilotReferenceRead(BaseModel):
    ref_id: str
    source_type: str
    entity_id: int | None
    summary: str


class CopilotNavigationRead(BaseModel):
    kind: CopilotFocusKind
    id: int


class CopilotAskResponse(BaseModel):
    status: Literal["ANSWERED", "INSUFFICIENT_CONTEXT", "FAILED"]
    answer: str
    references: list[CopilotReferenceRead]
    navigation: CopilotNavigationRead | None
    error: str | None = None
