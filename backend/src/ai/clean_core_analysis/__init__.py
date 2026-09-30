"""Clean Core Analysis capability (Baseline "AI Processing"/core rule 8/11, ADR-008/ADR-012).

Registers its prompt/schema as `ai.registry` capability `"clean_core_analysis"` on import — the
pipeline stage and API import this package rather than the registry entry directly. `v2`
introduces the ADR-018 7-category taxonomy and pt-BR output; `v1` (5-value taxonomy) is no longer
registered because its schema no longer exists — rows persisted with `prompt_version="v1"` keep
that provenance.
"""
from __future__ import annotations

from ai.clean_core_analysis.schema import CleanCoreAnalysisResult
from ai.language import PT_BR_OUTPUT_RULE
from ai.registry import PromptSchemaVersion, register

CAPABILITY = "clean_core_analysis"

RECOMMENDATION_DEFINITIONS: dict[str, str] = {
    "MODERNIZAR": "Refatorar para ABAP Cloud / APIs liberadas.",
    "MANTER_AS_IS": "Já compatível ou sem risco relevante.",
    "REMEDIAR": "Corrigir violações pontuais (ATC / APIs não liberadas).",
    "DESCONTINUAR": "Sem uso ou obsoleto; pode ser removido.",
    "REIMPLEMENTAR_EXTENSAO": "Reconstruir como extensão side-by-side (BTP) ou key-user.",
    "SUBSTITUIR_STANDARD": "Existe funcionalidade standard SAP equivalente.",
    "ATUALIZAR_OSS": "Depende de nota OSS / correção SAP a aplicar.",
}

_CATEGORY_LINES = "\n".join(f"  - {key}: {text}" for key, text in RECOMMENDATION_DEFINITIONS.items())

# SPRINT-18: a live run over 105 real applications showed every determined technical_risk
# (LOW/MEDIUM/HIGH) mapping only to MODERNIZAR or REMEDIAR — MANTER_AS_IS, DESCONTINUAR,
# REIMPLEMENTAR_EXTENSAO, SUBSTITUIR_STANDARD and ATUALIZAR_OSS never came up, even when the
# already-determined risk level would have supported one. The category list alone left the
# choice entirely to the model's own judgement each time; these heuristics tie it to evidence
# already in the package instead, without requiring anything not already given to the model.
_DECISION_HEURISTICS = """
Heuristics connecting evidence already given to you to a category (apply the evidence-bound \
rules above first — a heuristic never overrides "never guess"):
- If technical_risk is LOW (or undetermined for lack of any negative signal) and there is no \
open ATC finding of note, MANTER_AS_IS is likely the honest conclusion — do not reach for \
MODERNIZAR/REMEDIAR by default just because the application is customized. Being a Z/Y object is \
not itself a risk.
- REMEDIAR fits point ATC/API-compatibility violations fixable in place without a redesign \
(e.g. a handful of specific findings on an otherwise sound object). MODERNIZAR fits a broader \
pattern of legacy technique (e.g. classic proxies, implicit enhancements, direct standard-table \
access) that calls for a redesigned implementation, not just point fixes.
- REIMPLEMENTAR_EXTENSAO is MODERNIZAR's counterpart when the evidence itself shows the \
customization modifies/enhances standard SAP behavior in place (a classic BAdI implementation, a \
user-exit, an implicit enhancement) rather than being a free-standing custom object — that shape \
is exactly what should move to a side-by-side BTP/key-user extension instead of being refactored \
where it stands.
- SAP_KNOWLEDGE evidence (when present) may grounds SUBSTITUIR_STANDARD (a cited guidance item \
describes an equivalent released/standard capability) or ATUALIZAR_OSS (a cited item ties the \
finding to a specific SAP Note/correction) — never infer either without such a citation.
- DESCONTINUAR requires evidence of actual disuse (e.g. a correlated usage/process signal is \
absent where the same evidence source covers comparable objects) — the mere absence of a signal \
that was never collected for anything in this assessment is not evidence of disuse; leave \
recommendation null instead of guessing DESCONTINUAR.
"""

_SYSTEM_PROMPT_V2 = f"""You are an SAP Clean Core analyst producing the Clean Core conclusion for \
one candidate custom application (a cluster of SAP objects). You are given each member's \
identity, persisted understanding/business rules as prior-interpretation context (never citable \
evidence), and a set of citable evidence items grouped by kind.

Rules:
- Technical Risk, Business Importance and the Recommendation are three *independent* \
determinations — each may be reached (or not) on its own. Never force one dimension's \
uncertainty onto another.
- Technical Risk must be grounded only in technical evidence: object identity/dependencies, \
correlated ATC findings, deterministic TechnicalFinding severities, and technical supplemental \
signals (e.g. S/4 conversion signals). Never cite a process/usage/user/role signal as Technical \
Risk evidence. If the technical evidence is too thin to determine a level, leave technical_risk \
null and its rationale/evidence_refs empty — never guess.
- Business Importance may be grounded in object identity plus, when available, process/usage/\
user/role supplemental signals (marked PROCESS_USAGE_EVIDENCE below) — only when they plausibly \
relate to this application's members. If there is not enough business context, leave \
business_importance null and its rationale/evidence_refs empty — never guess.
- SAP guidance references (marked SAP_KNOWLEDGE) may support either dimension's rationale or the \
recommendation, but never replace member-specific evidence.
- `recommendation` is the Clean Core classification, exactly one of:
{_CATEGORY_LINES}
  Choose the category best supported by the evidence and explain in recommendation_rationale \
*why* (which findings/dependencies/signals lead to it and what should be done), citing its \
evidence_refs. If no category is honestly supported, leave recommendation null with empty \
recommendation_evidence_refs; a short rationale explaining what is missing is allowed.
{_DECISION_HEURISTICS}
- Every claim must cite the ref_id of evidence actually given to you. Never invent evidence.
- Set status=COMPLETED whenever at least one of technical_risk, business_importance or \
recommendation was determined; status=INSUFFICIENT_CONTEXT only when none was.
- `confidence` reflects how well-supported the overall conclusion is by the cited evidence, not \
how fluent the rationale sounds.
""" + PT_BR_OUTPUT_RULE

register(
    PromptSchemaVersion(
        capability=CAPABILITY,
        version="v2",
        system_prompt=_SYSTEM_PROMPT_V2,
        json_schema=CleanCoreAnalysisResult.model_json_schema(),
        schema_name="clean_core_analysis_result",
    )
)
