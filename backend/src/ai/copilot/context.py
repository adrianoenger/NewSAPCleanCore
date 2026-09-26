"""Copilot context assembly (ADR-010, Baseline core rule 17: "Chat may route to SQL, semantic
search, source retrieval, supplemental evidence retrieval and MCP as appropriate").

Builds one bounded, citable `CopilotContext` per question by combining:
- a structured summary (reuses `pipeline.dashboard_summary`, the same aggregation Dashboard
  Geral shows — the "structured query" channel);
- the current UI selection's own detail, reusing already-persisted, already evidence-bound AI
  outputs (`ObjectUnderstanding`/`BusinessRule`/`CleanCoreAssessment`) rather than rebuilding a
  parallel evidence package — their `evidence_refs` are surfaced directly so the model can cite
  the same source/ATC/supplemental-evidence items those capabilities already validated;
- semantic search hits for the question text across the assessment's embeddings (the "semantic
  retrieval" channel);
- already-retrieved `SapKnowledgeReference` rows for the selection (the "MCP" channel) — read-only
  reuse via `ai.knowledge_service.list_guidance`; a chat question never itself triggers a new MCP
  query (ADR-007 restricts that to an explicit finding/application detail view).

Every item carries a `ref_id` the model must cite in `evidence_refs`/`navigation_ref`
(`ai.copilot.schema.validate_result` rejects anything not present here) and, where the item
corresponds to a navigable entity, a `navigation` target reusing the same three kinds as
`resultNav.ts::ResultFocus` (sap_object/business_rule/application).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.embedding_provider import EmbeddingProvider, EmbeddingProviderError
from ai.embeddings.search import semantic_search
from ai.knowledge_service import list_guidance
from persistence.models import (
    Application,
    BusinessRule,
    ObjectUnderstanding,
    ObjectUnderstandingStatus,
    SAPObject,
    SapKnowledgeTargetType,
)
from pipeline.dashboard_summary import compute_dashboard_summary

_MAX_CONTEXT_ITEMS = 40
_SEMANTIC_HIT_LIMIT = 5

_SEMANTIC_ENTITY_TO_FOCUS_KIND = {
    "SAP_OBJECT": "sap_object",
    "APPLICATION": "application",
    "BUSINESS_RULE": "business_rule",
}


@dataclass(frozen=True)
class CopilotSelection:
    kind: str  # "sap_object" | "business_rule" | "application"
    id: int


@dataclass(frozen=True)
class CopilotContextItem:
    ref_id: str
    source_type: str
    entity_id: int | None
    summary: str
    navigation: CopilotSelection | None = None


@dataclass(frozen=True)
class CopilotContext:
    assessment_id: int
    view: str
    selection: CopilotSelection | None
    items: list[CopilotContextItem] = field(default_factory=list)


def build_context(
    session: Session,
    assessment_id: int,
    view: str,
    selection: CopilotSelection | None,
    question: str,
    embedding_provider: EmbeddingProvider,
) -> CopilotContext:
    items: list[CopilotContextItem] = [_summary_item(session, assessment_id)]

    if selection is not None:
        items.extend(_selection_items(session, assessment_id, selection))

    if question.strip():
        items.extend(_semantic_items(session, assessment_id, question, embedding_provider))

    return CopilotContext(
        assessment_id=assessment_id, view=view, selection=selection, items=items[:_MAX_CONTEXT_ITEMS]
    )


def _summary_item(session: Session, assessment_id: int) -> CopilotContextItem:
    summary = compute_dashboard_summary(session, assessment_id)
    return CopilotContextItem(
        ref_id="SUMMARY-1",
        source_type="STRUCTURED_SUMMARY",
        entity_id=None,
        summary=(
            f"{summary.objects_analyzed} objects analyzed, {summary.customizations_identified} custom "
            f"applications identified, {summary.critical_findings} critical ATC findings, "
            f"{summary.high_impact_objects} high-impact objects, {summary.business_rules_identified} "
            f"candidate business rules. Results stale (needs reprocessing): {summary.is_stale}."
        ),
    )


def _resolved_evidence_items(evidence_refs: list[dict]) -> list[CopilotContextItem]:
    items: list[CopilotContextItem] = []
    for ref in evidence_refs:
        ref_id = ref.get("ref_id")
        if not ref_id:
            continue
        source_type = ref.get("source_type", "UNKNOWN")
        items.append(
            CopilotContextItem(
                ref_id=ref_id,
                source_type=source_type,
                entity_id=ref.get("entity_id"),
                summary=f"Evidence already cited by prior AI analysis ({source_type}).",
            )
        )
    return items


def _knowledge_items(session: Session, assessment_id: int, target_type: str, target_id: int) -> list[CopilotContextItem]:
    rows = list_guidance(session, assessment_id, target_type, target_id)
    return [
        CopilotContextItem(
            ref_id=f"SAPK-{r.id}",
            source_type="SAP_KNOWLEDGE",
            entity_id=r.id,
            summary=f"{r.title}: {r.summary[:200]}".strip(": "),
        )
        for r in rows
    ]


def _selection_items(session: Session, assessment_id: int, selection: CopilotSelection) -> list[CopilotContextItem]:
    if selection.kind == "sap_object":
        return _sap_object_selection_items(session, assessment_id, selection.id)
    if selection.kind == "business_rule":
        return _business_rule_selection_items(session, assessment_id, selection.id)
    if selection.kind == "application":
        return _application_selection_items(session, assessment_id, selection.id)
    return []


def _sap_object_selection_items(session: Session, assessment_id: int, object_id: int) -> list[CopilotContextItem]:
    obj = session.get(SAPObject, object_id)
    if obj is None or obj.assessment_id != assessment_id:
        return []

    items = [
        CopilotContextItem(
            ref_id="SEL-1",
            source_type="SAP_OBJECT",
            entity_id=obj.id,
            summary=f"{obj.object_type} {obj.object_name}: {obj.description or '(no description)'}",
            navigation=CopilotSelection(kind="sap_object", id=obj.id),
        )
    ]

    understanding = session.scalars(
        select(ObjectUnderstanding).where(ObjectUnderstanding.sap_object_id == obj.id)
    ).first()
    if understanding is not None and understanding.status == ObjectUnderstandingStatus.COMPLETED.value:
        items.append(
            CopilotContextItem(
                ref_id="SEL-1-UNDERSTANDING",
                source_type="OBJECT_UNDERSTANDING",
                entity_id=obj.id,
                summary=f"Functional purpose: {understanding.functional_purpose} Technical purpose: {understanding.technical_purpose}",
            )
        )
        items.extend(_resolved_evidence_items(understanding.evidence_refs))

    return items


def _business_rule_selection_items(session: Session, assessment_id: int, rule_id: int) -> list[CopilotContextItem]:
    rule = session.get(BusinessRule, rule_id)
    if rule is None or rule.assessment_id != assessment_id:
        return []

    items = [
        CopilotContextItem(
            ref_id="SEL-1",
            source_type="BUSINESS_RULE",
            entity_id=rule.id,
            summary=f"{rule.rule_type} rule: IF {rule.condition} THEN {rule.action} (confidence {rule.confidence:.2f}).",
            navigation=CopilotSelection(kind="business_rule", id=rule.id),
        )
    ]
    items.extend(_resolved_evidence_items(rule.evidence_refs))
    items.extend(_knowledge_items(session, assessment_id, SapKnowledgeTargetType.BUSINESS_RULE.value, rule.id))
    return items


def _application_selection_items(session: Session, assessment_id: int, application_id: int) -> list[CopilotContextItem]:
    app = session.get(Application, application_id)
    if app is None or app.assessment_id != assessment_id:
        return []

    items = [
        CopilotContextItem(
            ref_id="SEL-1",
            source_type="APPLICATION",
            entity_id=app.id,
            summary=f"Application '{app.name}': {app.description or '(no description)'}",
            navigation=CopilotSelection(kind="application", id=app.id),
        )
    ]
    items.extend(_resolved_evidence_items(app.evidence_refs))

    cc = app.clean_core_assessment
    if cc is not None and cc.status == "COMPLETED":
        items.append(
            CopilotContextItem(
                ref_id="SEL-1-CLEANCORE",
                source_type="CLEAN_CORE_ASSESSMENT",
                entity_id=cc.id,
                summary=(
                    f"Technical risk: {cc.technical_risk or 'n/a'}. Business importance: "
                    f"{cc.business_importance or 'n/a'}. Recommendation: {cc.recommendation} — "
                    f"{cc.recommendation_rationale}"
                ),
            )
        )
        for refs in (cc.technical_risk_evidence_refs, cc.business_importance_evidence_refs, cc.recommendation_evidence_refs):
            items.extend(_resolved_evidence_items(refs))

    items.extend(_knowledge_items(session, assessment_id, SapKnowledgeTargetType.APPLICATION.value, app.id))
    return items


def _semantic_items(
    session: Session, assessment_id: int, question: str, embedding_provider: EmbeddingProvider
) -> list[CopilotContextItem]:
    try:
        hits = semantic_search(session, assessment_id, question, embedding_provider, limit=_SEMANTIC_HIT_LIMIT)
    except EmbeddingProviderError:
        # Semantic retrieval is enrichment, never a hard dependency of answering (mirrors
        # ai.knowledge_service.fetch_guidance's own "a provider error is skipped, not fatal").
        return []

    items: list[CopilotContextItem] = []
    for i, hit in enumerate(hits, start=1):
        kind = _SEMANTIC_ENTITY_TO_FOCUS_KIND.get(hit.entity_type)
        items.append(
            CopilotContextItem(
                ref_id=f"SEM-{i}",
                source_type=hit.entity_type,
                entity_id=hit.entity_id,
                summary=hit.content_text[:300],
                navigation=CopilotSelection(kind=kind, id=hit.entity_id) if kind else None,
            )
        )
    return items


def render_prompt(context: CopilotContext, question: str, history: list[tuple[str, str]]) -> str:
    """Render `context` + prior turns + the new question into the user-turn text handed to the
    provider. `history` is `[(role, content), ...]`, oldest first, already capped by the caller."""
    lines = [f"Current view: {context.view}"]
    if context.selection is not None:
        lines.append(f"Current selection: {context.selection.kind} #{context.selection.id}")
    lines.append("")
    lines.append(
        "Context available for citation. Each line starts with its ref_id — the ONLY value you "
        "may put in evidence_refs or navigation_ref (never the [source_type] tag, never the "
        "'navigable' note, never anything you compose yourself):"
    )
    for item in context.items:
        nav = f" (navigable — cite this exact ref_id in navigation_ref if relevant)" if item.navigation else ""
        lines.append(f"- ref_id={item.ref_id} [{item.source_type}]: {item.summary}{nav}")

    if history:
        lines.append("")
        lines.append("Conversation so far:")
        for role, content in history:
            lines.append(f"{role}: {content}")

    lines.append("")
    lines.append(f"Question: {question}")
    return "\n".join(lines)
