"""Executive Summary capability (SPRINT-18 CAP-005, ADR-008/ADR-012).

Registers its prompt/schema as `ai.registry` capability `"executive_summary"` version `"v1"` on
import. The evidence package is the assessment catalog shared with the Copilot
(`ai.copilot.context.build_assessment_catalog`); generation/persistence lives in
`ai.executive_summary.generator`, used by both the pipeline stage and the regenerate route.
"""
from __future__ import annotations

from ai.executive_summary.schema import ExecutiveSummaryResult
from ai.language import PT_BR_OUTPUT_RULE
from ai.registry import PromptSchemaVersion, register

CAPABILITY = "executive_summary"

_SYSTEM_PROMPT_V1 = """You are a senior SAP Clean Core consultant writing the executive summary of \
an SAP custom-code assessment for business and IT leadership. Use only the context items \
provided (aggregate counts, Clean Core classification distribution, ATC findings summary, one \
item per discovered custom application with its classification, risk and rationale, and a sample \
of critical findings).

Write `markdown` with exactly these sections, as "## " headings, in this order:
## Visão geral
## Principais achados
## Distribuição Clean Core
## Riscos críticos
## Recomendações e roadmap
## Próximos passos

Rules:
- Be concise and decision-oriented (roughly 400-700 words). Use bullet lists and **bold** for key \
numbers; a small Markdown table is allowed in "Distribuição Clean Core".
- Every number and claim must come from a context item; list the ref_ids you used in \
`evidence_refs`, copied verbatim. Never invent numbers, objects, applications or ref_ids.
- Applications without a classification are "Não classificado" — say so explicitly instead of \
guessing a category; unnamed applications are referred to by the label given in the context.
- Do not put ref_ids inside the markdown text.
- If the context has no analysed objects at all, set status=INSUFFICIENT_CONTEXT with a one-line \
markdown explaining that the assessment must be processed first.
- Write in Brazilian Portuguese (pt-BR).
""" + PT_BR_OUTPUT_RULE

register(
    PromptSchemaVersion(
        capability=CAPABILITY,
        version="v1",
        system_prompt=_SYSTEM_PROMPT_V1,
        json_schema=ExecutiveSummaryResult.model_json_schema(),
        schema_name="executive_summary_result",
    )
)
