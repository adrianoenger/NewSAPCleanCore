"""Generate and persist the Executive Summary of one assessment (SPRINT-18 CAP-005).

Shared by the `executive_summary` pipeline stage and `POST .../executive-summary/regenerate`.
ADR-012: schema, evidence-reference and domain rules are validated before persistence; a
provider/validation failure is persisted as FAILED (keeping the error), never a false summary.
"""
from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.copilot.context import CopilotContextItem, build_assessment_catalog
from ai.executive_summary import CAPABILITY
from ai.executive_summary.schema import ExecutiveSummaryResult, validate_result
from ai.provider import AIProvider, AIProviderError, StructuredCompletionRequest
from ai.registry import get_version
from persistence.models import ExecutiveSummary, ExecutiveSummaryStatus


def render_prompt(assessment_label: str, items: list[CopilotContextItem]) -> str:
    lines = [
        f"Assessment: {assessment_label}",
        "",
        "Context available for citation. Each line starts with its ref_id — the ONLY value you may put "
        "in evidence_refs:",
    ]
    lines.extend(f"- ref_id={item.ref_id} [{item.source_type}]: {item.summary}" for item in items)
    lines.append("")
    lines.append("Write the executive summary.")
    return "\n".join(lines)


def generate_executive_summary(
    session: Session,
    assessment_id: int,
    assessment_label: str,
    provider: AIProvider,
    stage_run_id: int | None = None,
) -> ExecutiveSummary:
    items = build_assessment_catalog(session, assessment_id)
    items_by_ref = {item.ref_id: item for item in items}
    prompt_version = get_version(CAPABILITY)

    row = session.scalars(select(ExecutiveSummary).where(ExecutiveSummary.assessment_id == assessment_id)).first()
    if row is None:
        row = ExecutiveSummary(assessment_id=assessment_id)
        session.add(row)
    row.prompt_capability = CAPABILITY
    row.prompt_version = prompt_version.version
    row.stage_run_id = stage_run_id
    row.generated_at = func.now()

    try:
        completion = provider.complete_structured(
            StructuredCompletionRequest(
                system_prompt=prompt_version.system_prompt,
                user_prompt=render_prompt(assessment_label, items),
                json_schema=prompt_version.json_schema,
                schema_name=prompt_version.schema_name,
            )
        )
        result = ExecutiveSummaryResult.model_validate(completion.output)
        errors = validate_result(result, set(items_by_ref))
        if errors:
            raise AIProviderError(f"Domain validation failed: {'; '.join(errors)}")
    except (AIProviderError, ValidationError) as exc:
        # Keep the previous markdown (if any) visible — only the status/error say it is stale.
        row.status = ExecutiveSummaryStatus.FAILED.value
        row.markdown = row.markdown or ""
        row.evidence_refs = row.evidence_refs or []
        row.provider = provider.name
        row.model_id = provider.model_id
        row.error = str(exc)[:2000]
        session.flush()
        return row

    row.status = result.status.value
    row.markdown = result.markdown
    row.evidence_refs = [
        {
            "ref_id": ref,
            "source_type": items_by_ref[ref].source_type,
            "entity_id": items_by_ref[ref].entity_id,
        }
        for ref in dict.fromkeys(result.evidence_refs)
    ]
    row.provider = completion.provider
    row.model_id = completion.model_id
    row.error = None
    session.flush()
    return row
