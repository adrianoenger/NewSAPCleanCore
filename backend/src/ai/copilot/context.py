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
  query (ADR-007 restricts that to an explicit finding/application detail view);
- assessment catalog items (SPRINT-18 CAP-004): the Clean Core distribution, ATC counts, one item
  per application with its classification/rationale/members, and — when `ai.copilot.intent`
  detects the question is about objects or a category — the object list itself. Without these the
  model only had aggregate counts and could not answer "which objects were classified as X?".

Each source has its own budget so the catalog and the selection never crowd each other out.

Every item carries a `ref_id` the model must cite in `evidence_refs`/`navigation_ref`
(`ai.copilot.schema.validate_result` rejects anything not present here) and, where the item
corresponds to a navigable entity, a `navigation` target reusing the same three kinds as
`resultNav.ts::ResultFocus` (sap_object/business_rule/application).
Summaries are pt-BR (the Copilot always answers in pt-BR, SPRINT-18 CAP-001).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.copilot.intent import RECOMMENDATION_LABELS, UNCLASSIFIED_LABEL, CopilotIntent, detect_intent
from ai.embedding_provider import EmbeddingProvider, EmbeddingProviderError
from ai.embeddings.search import semantic_search
from ai.knowledge_service import list_guidance
from persistence.models import (
    Application,
    ApplicationStatus,
    ATCFinding,
    BusinessRule,
    CleanCoreAssessment,
    ObjectUnderstanding,
    ObjectUnderstandingStatus,
    SAPObject,
    SapKnowledgeTargetType,
    SourceFile,
    TechnicalFinding,
    TechnicalFindingSeverity,
)
from pipeline.dashboard_summary import (
    UNCLASSIFIED,
    DashboardOverview,
    compute_dashboard_overview,
)
from pipeline.status import get_current_scan

# Per-source budgets (SPRINT-18 CAP-004) instead of one global cut that let a large selection
# evict the catalog (or vice versa).
_SELECTION_ITEMS_LIMIT = 30
_SEMANTIC_HIT_LIMIT = 5
_CRITICAL_FINDINGS_LIMIT = 5
_APPLICATION_ITEMS_LIMIT = 40
_APPLICATION_MEMBERS_SHOWN = 40
_RATIONALE_CHARS = 600
_OBJECT_CATALOG_FULL_LIMIT = 1500
_OBJECT_CATALOG_GROUPED_NAMES = 15
_TOP_ATC_CHECKS = 10

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
    items = build_assessment_catalog(session, assessment_id, detect_intent(question))

    if selection is not None:
        items.extend(_selection_items(session, assessment_id, selection)[:_SELECTION_ITEMS_LIMIT])

    if question.strip():
        items.extend(_semantic_items(session, assessment_id, question, embedding_provider))

    # The same evidence ref can be inherited from several persisted AI outputs — keep the first.
    unique: dict[str, CopilotContextItem] = {}
    for item in items:
        unique.setdefault(item.ref_id, item)
    return CopilotContext(assessment_id=assessment_id, view=view, selection=selection, items=list(unique.values()))


def build_assessment_catalog(
    session: Session, assessment_id: int, intent: CopilotIntent | None = None
) -> list[CopilotContextItem]:
    """Assessment-wide citable items (summary, catalog, critical findings sample). Also the
    evidence package of `ai.executive_summary` (intent=None: every application, no object list),
    so the Copilot and the Executive Summary cite the very same ref_ids/definitions."""
    intent = intent or CopilotIntent()
    overview = compute_dashboard_overview(session, assessment_id)
    items: list[CopilotContextItem] = [_summary_item(overview)]
    items.extend(_catalog_items(session, assessment_id, overview, intent))
    items.extend(_critical_findings_items(session, assessment_id))
    return items


def _summary_item(overview: DashboardOverview) -> CopilotContextItem:
    summary = overview.summary
    return CopilotContextItem(
        ref_id="SUMMARY-1",
        source_type="STRUCTURED_SUMMARY",
        entity_id=None,
        summary=(
            f"{summary.objects_analyzed} objetos analisados ({overview.objects_custom} customizados Z/Y), "
            f"{summary.customizations_identified} aplicações customizadas identificadas, "
            f"{summary.critical_findings} findings ATC críticos (prioridade 1), "
            f"{summary.high_impact_objects} objetos de alto impacto, {summary.business_rules_identified} "
            f"regras de negócio candidatas. Resultados desatualizados (requer reprocessamento): "
            f"{'sim' if summary.is_stale else 'não'}."
        ),
    )


def _recommendation_label(recommendation: str | None) -> str:
    if not recommendation or recommendation == UNCLASSIFIED:
        return UNCLASSIFIED_LABEL
    return RECOMMENDATION_LABELS.get(recommendation, recommendation)


def _application_label(app: Application) -> str:
    return app.name or f"Aplicação #{app.id} (sem nome)"


def _catalog_items(
    session: Session, assessment_id: int, overview: DashboardOverview, intent: CopilotIntent
) -> list[CopilotContextItem]:
    items = [_distribution_item(overview)]
    if overview.atc_run_id is not None:
        items.append(_atc_catalog_item(session, overview))
    items.extend(_application_catalog_items(session, assessment_id, intent))
    if intent.wants_objects or intent.categories or intent.wants_unclassified:
        item = _object_catalog_item(session, assessment_id, intent)
        if item is not None:
            items.append(item)
    return items


def _distribution_item(overview: DashboardOverview) -> CopilotContextItem:
    def fmt(counts: dict[str, int]) -> str:
        parts = [f"{_recommendation_label(k)}: {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
        return ", ".join(parts) or "nenhum"

    return CopilotContextItem(
        ref_id="CATALOG-CC-DIST",
        source_type="CLEAN_CORE_DISTRIBUTION",
        entity_id=None,
        summary=(
            "Distribuição da classificação Clean Core (cada objeto herda a classificação da sua aplicação). "
            f"Objetos — {fmt(overview.clean_core_objects)}. Aplicações — {fmt(overview.clean_core_applications)}."
        ),
    )


def _atc_catalog_item(session: Session, overview: DashboardOverview) -> CopilotContextItem:
    top_checks = session.execute(
        select(ATCFinding.check_title, func.count(ATCFinding.id))
        .where(ATCFinding.atc_run_id == overview.atc_run_id)
        .group_by(ATCFinding.check_title)
        .order_by(func.count(ATCFinding.id).desc())
        .limit(_TOP_ATC_CHECKS)
    ).all()
    correlated = session.scalar(
        select(func.count(ATCFinding.id)).where(
            ATCFinding.atc_run_id == overview.atc_run_id, ATCFinding.correlated_object_id.is_not(None)
        )
    )
    by_priority = ", ".join(
        f"{'sem prioridade' if p == 'none' else f'P{p}'}: {c}" for p, c in sorted(overview.atc_by_priority.items())
    )
    checks = "; ".join(f"{title or 'Finding ATC'} ({count})" for title, count in top_checks)
    return CopilotContextItem(
        ref_id="CATALOG-ATC",
        source_type="ATC_SUMMARY",
        entity_id=overview.atc_run_id,
        summary=(
            f"Importação ATC atual: {overview.atc_total} findings ({by_priority}); {correlated} correlacionados "
            f"a objetos do código-fonte analisado. Checks mais frequentes: {checks}."
        ),
    )


def _application_catalog_items(session: Session, assessment_id: int, intent: CopilotIntent) -> list[CopilotContextItem]:
    rows = session.execute(
        select(Application, CleanCoreAssessment)
        .outerjoin(CleanCoreAssessment, CleanCoreAssessment.application_id == Application.id)
        .where(Application.assessment_id == assessment_id, Application.status != ApplicationStatus.MERGED.value)
        .order_by(Application.id)
    ).all()
    if intent.categories or intent.wants_unclassified:
        # A category question gets exactly that category's applications (never truncated away).
        rows = [
            (app, cc)
            for app, cc in rows
            if (cc is not None and cc.recommendation in intent.categories)
            or (intent.wants_unclassified and (cc is None or cc.recommendation is None))
        ]
    rows = rows[:_APPLICATION_ITEMS_LIMIT]

    members_by_app: dict[int, list[str]] = {}
    if rows:
        for app_id, name in session.execute(
            select(SAPObject.application_id, SAPObject.object_name)
            .where(SAPObject.application_id.in_([app.id for app, _ in rows]))
            .order_by(SAPObject.object_name)
        ):
            members_by_app.setdefault(app_id, []).append(name)

    items: list[CopilotContextItem] = []
    for app, cc in rows:
        members = members_by_app.get(app.id, [])
        shown = ", ".join(members[:_APPLICATION_MEMBERS_SHOWN])
        if len(members) > _APPLICATION_MEMBERS_SHOWN:
            shown += f" … (+{len(members) - _APPLICATION_MEMBERS_SHOWN})"
        if cc is not None:
            classification = (
                f"Classificação Clean Core: {_recommendation_label(cc.recommendation)}. "
                f"Risco técnico: {cc.technical_risk or 'n/d'}. Importância de negócio: {cc.business_importance or 'n/d'}. "
                f"Justificativa: {(cc.recommendation_rationale or '(sem justificativa)')[:_RATIONALE_CHARS]}"
            )
        else:
            classification = f"Classificação Clean Core: {UNCLASSIFIED_LABEL} (ainda não analisada)."
        items.append(
            CopilotContextItem(
                ref_id=f"CATALOG-CC-{app.id}",
                source_type="APPLICATION_CLEAN_CORE",
                entity_id=app.id,
                summary=f"Aplicação '{_application_label(app)}' ({len(members)} objetos: {shown}). {classification}",
                navigation=CopilotSelection(kind="application", id=app.id),
            )
        )
    return items


def _object_catalog_item(session: Session, assessment_id: int, intent: CopilotIntent) -> CopilotContextItem | None:
    scan = get_current_scan(session, assessment_id)
    if scan is None:
        return None
    rows = session.execute(
        select(SAPObject.object_name, SAPObject.object_type, Application, CleanCoreAssessment.recommendation)
        .join(SourceFile, SAPObject.source_file_id == SourceFile.id)
        .outerjoin(Application, Application.id == SAPObject.application_id)
        .outerjoin(CleanCoreAssessment, CleanCoreAssessment.application_id == SAPObject.application_id)
        .where(SourceFile.scan_id == scan.id)
        .order_by(SAPObject.object_name)
    ).all()
    if intent.categories or intent.wants_unclassified:
        rows = [r for r in rows if r[3] in intent.categories or (intent.wants_unclassified and r[3] is None)]
        scope = ", ".join(
            [_recommendation_label(c) for c in sorted(intent.categories)]
            + ([UNCLASSIFIED_LABEL] if intent.wants_unclassified else [])
        )
        header = f"Objetos classificados como {scope}: {len(rows)}."
    else:
        header = f"Todos os objetos analisados: {len(rows)}."

    def app_label(app: Application | None) -> str:
        return _application_label(app) if app is not None else "sem aplicação"

    if len(rows) <= _OBJECT_CATALOG_FULL_LIMIT:
        body = " | ".join(
            f"{name} ({otype}; {app_label(app)}; {_recommendation_label(rec)})" for name, otype, app, rec in rows
        )
    else:
        grouped: dict[str, list[str]] = {}
        for name, _otype, app, rec in rows:
            grouped.setdefault(f"{app_label(app)} — {_recommendation_label(rec)}", []).append(name)
        body = " | ".join(
            f"{key}: {len(names)} objetos (ex.: {', '.join(names[:_OBJECT_CATALOG_GROUPED_NAMES])})"
            for key, names in sorted(grouped.items(), key=lambda kv: -len(kv[1]))
        )
    return CopilotContextItem(
        ref_id="CATALOG-OBJECTS",
        source_type="OBJECT_CATALOG",
        entity_id=None,
        summary=f"{header} Formato: nome (tipo; aplicação; classificação Clean Core). {body or '(nenhum)'}",
    )


def _critical_findings_items(session: Session, assessment_id: int) -> list[CopilotContextItem]:
    """A bounded sample of real HIGH-severity TechnicalFinding rows, always available for
    citation — before this, the only findings signal in context was `_summary_item`'s aggregate
    count, so a question like "give me an example of a critical finding" had nothing concrete to
    cite and the model correctly refused rather than fabricate one. Bounded (not all findings,
    which can be in the thousands for a real ATC import) per Baseline core rule 10."""
    findings = list(
        session.scalars(
            select(TechnicalFinding)
            .where(
                TechnicalFinding.assessment_id == assessment_id,
                TechnicalFinding.severity == TechnicalFindingSeverity.HIGH.value,
            )
            .order_by(TechnicalFinding.id.desc())
            .limit(_CRITICAL_FINDINGS_LIMIT)
        )
    )
    return [
        CopilotContextItem(
            ref_id=f"FINDING-{f.id}",
            source_type="TECHNICAL_FINDING",
            entity_id=f.id,
            summary=f"[{f.severity}/{f.source}] {f.title}",
            navigation=CopilotSelection(kind="sap_object", id=f.sap_object_id) if f.sap_object_id else None,
        )
        for f in findings
    ]


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
                summary=f"Evidência já citada por uma análise de IA anterior ({source_type}).",
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
            summary=f"{obj.object_type} {obj.object_name}: {obj.description or '(sem descrição)'}",
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
                summary=f"Propósito funcional: {understanding.functional_purpose} Propósito técnico: {understanding.technical_purpose}",
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
            summary=f"Regra {rule.rule_type}: SE {rule.condition} ENTÃO {rule.action} (confiança {rule.confidence:.2f}).",
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
            summary=f"Aplicação '{_application_label(app)}': {app.description or '(sem descrição)'}",
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
                    f"Risco técnico: {cc.technical_risk or 'n/d'}. Importância de negócio: "
                    f"{cc.business_importance or 'n/d'}. Classificação: {_recommendation_label(cc.recommendation)} — "
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
