"""Pydantic schema for the results-summary aggregation endpoint (Dashboard Geral / SPRINT-15)."""
from datetime import date

from pydantic import BaseModel


class DashboardSummaryRead(BaseModel):
    assessment_id: int
    objects_analyzed: int
    customizations_identified: int
    critical_findings: int
    high_impact_objects: int
    business_rules_identified: int
    is_stale: bool


class DashboardOverviewRead(BaseModel):
    """Reference-dashboard panels (SPRINT-18 CAP-003): inventory, ATC by priority, Clean Core
    distribution by objects (inherited from the owning Application, ADR-018) and by applications.
    Recommendation keys include `UNCLASSIFIED` for objects/applications without a classification."""

    summary: DashboardSummaryRead
    objects_total: int
    objects_custom: int
    objects_by_type: dict[str, int]
    atc_run_id: int | None
    atc_total: int
    atc_by_priority: dict[str, int]
    objects_classified: int
    clean_core_objects: dict[str, int]
    clean_core_applications: dict[str, int]
    usage_signal_by_level: dict[str, int]
    unused_custom_objects: int


class ObjectListItem(BaseModel):
    id: int
    object_type: str
    object_name: str
    description: str
    is_custom: bool
    application_id: int | None
    application_name: str | None
    recommendation: str | None
    technical_risk: str | None
    atc_findings: int
    usage_level: str | None


class ObjectListResponse(BaseModel):
    items: list[ObjectListItem]
    total: int


class ATCFindingListItem(BaseModel):
    id: int
    priority: int | None
    check_title: str | None
    check_message: str | None
    object_name_raw: str | None
    object_type_raw: str | None
    package_name_raw: str | None
    correlated_object_id: int | None

    model_config = {"from_attributes": True}


class ATCFindingListResponse(BaseModel):
    atc_run_id: int | None
    items: list[ATCFindingListItem]
    total: int


class ATCFindingDetailRead(ATCFindingListItem):
    atc_run_id: int
    source_row_number: int
    exemption_state: str | None
    contact_person: str | None
    first_found_on: date | None
    object_responsible: str | None
    last_changed_by: str | None
    sap_note_number: str | None
    sap_note_short_text: str | None
    referenced_application_component: str | None
    referenced_object_type: str | None
    referenced_object_name: str | None
    additional_info: str | None
    simplification_item_category: str | None
    change_category: str | None
    change_category_description: str | None
    remarks: str | None
    correlation_status: str | None
