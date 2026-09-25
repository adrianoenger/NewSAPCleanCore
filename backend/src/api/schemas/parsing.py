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
    parsed_at: datetime

    model_config = {"from_attributes": True}


class SAPObjectDetailRead(SAPObjectRead):
    attributes: dict[str, Any]
