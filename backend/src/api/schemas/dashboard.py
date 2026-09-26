"""Pydantic schema for the results-summary aggregation endpoint (Dashboard Geral / SPRINT-15)."""
from pydantic import BaseModel


class DashboardSummaryRead(BaseModel):
    assessment_id: int
    objects_analyzed: int
    customizations_identified: int
    critical_findings: int
    high_impact_objects: int
    business_rules_identified: int
    is_stale: bool
