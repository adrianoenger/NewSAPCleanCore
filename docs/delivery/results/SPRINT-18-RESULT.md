# SPRINT-18 Result — Final Adjustments

**Status:** Completed
**Completed at:** 2026-09-29
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
All AI-generated analysis text is now Brazilian Portuguese by default (v2 prompts + translated
deterministic strings). Clean Core moved to a 7-category recommendation taxonomy assigned per
Application (ADR-018, migration 0017). Dashboard Geral is now the single results entry screen
(ADR-019): clickable KPIs → full-page lists → full-page detail, plus inventory/ATC/Clean Core
reference panels and charts — the four separate Executive/Technical/Functional/Architecture
sidebar views were removed. The Copilot can answer assessment-level questions (object catalog,
per-application Clean Core classification with rationale, ATC counts) via a deterministic catalog
context and intent router. A new Executive Summary pipeline stage generates a persisted,
evidence-bound pt-BR markdown summary with on-demand regeneration. An AI-only reprocessing run
(reuse the current scan, skip parse/dependencies) lets an assessment's texts be regenerated
without a full rescan, with a second, faster variant that starts at application clustering and
reuses already-correct object understanding/business rules.

Reprocessing the two real assessments (the persistent Acme demo and the 422-object Rodobens
customer scan) to pt-BR surfaced and fixed several real defects the smaller demo dataset could
never have exposed: stale orphan applications after reclustering, an application double-claimed
by two split clusters, a single misplaced evidence ref failing an entire Clean Core analysis, an
AI concept-based clustering signal that collapsed 421 of 422 Rodobens objects into one
application (overflowing the model's input), and a systematic "leftover rationale on a null
dimension" domain-validation failure hitting ~30% of Clean Core rows at that scale. All fixed and
re-validated end to end. A live follow-up review of the resulting Clean Core category
distribution (too concentrated in just 2 of 7 categories) led to wiring the previously-unused
`mcp-sap-docs`/`mcp-abap` SAP knowledge providers to their real public hosted endpoints and adding
decision heuristics to the Clean Core prompt tying already-determined risk/importance to specific
categories — which measurably broadened the real distribution from 2 to 5 categories on Rodobens.

## Demonstration path
1. Open an assessment and land on Dashboard Geral: 5 clickable summary KPIs plus 4 reference
   panels (object inventory, ATC findings by priority, Clean Core donut with 7 categories +
   "Não classificado", ATC priority bars).
2. Click "Objetos analisados" → filtered list → an object detail (understanding, source, ATC
   findings, business rules, owning application's Clean Core classification).
3. Click a Clean Core donut slice or an ATC priority bar → filtered list → detail.
4. Open "Resumo Executivo" in the sidebar — formatted pt-BR markdown (visão geral, achados,
   distribuição Clean Core, riscos críticos, recomendações, próximos passos); "Regerar" updates it.
5. Ask the Copilot "Quais objetos o clean core categorizou como Remediar? Explique o porquê" —
   receive a grounded pt-BR answer citing the exact objects/rationale, with a navigable
   "Ver aplicação" reference.
6. In "3 - Processamento por IA", use "Reprocessar IA" (full AI reprocess) or "Só aplicações →
   Clean Core → resumo" (faster, reuses understanding/rules) to regenerate an assessment's texts
   without a full rescan.
7. Open an Application detail — "Orientação SAP" shows real, live-retrieved guidance links from
   `mcp-sap-docs`/`mcp-abap` (help.sap.com/ABAP docs), fetched via "Consultar SAP Docs".

## Minimal validation executed
- [x] Backend: 264/264 pytest, full suite, with no live pipeline run active (BL-008-safe).
- [x] Frontend: `tsc --noEmit` (both tsconfigs) and `electron-vite build` clean.
- [x] Critical contracts introduced this sprint: Clean Core 7-category schema/domain validation
      (`test_clean_core_analysis.py`), dashboard-overview/object-list/atc-findings endpoints
      (`test_dashboard.py`), Copilot catalog/intent routing (`test_copilot.py`), executive-summary
      generate/regenerate (`test_executive_summary.py`), AI-only reprocess incl. the
      from-applications variant (`test_reprocess_ai.py`), bounded evidence packages
      (`test_clean_core_analysis.py`), the real `mcp-sap-docs` JSON response shape
      (`test_sap_knowledge.py`).
- [x] Primary demonstrable user flow: live Bedrock + Playwright against the electron-vite renderer
      over both the persistent Acme demo assessment (1074) and the real Rodobens customer
      assessment (1075, 422 objects / 105 applications) — dashboard, application detail with
      pt-BR Risco Técnico/Importância de Negócio, Executive Summary, Copilot, SAP Guidance panel.
- [x] Migration applicability: alembic 0017 (Clean Core taxonomy) and 0018 (executive summary)
      applied on the dev DB; `alembic upgrade head` is a no-op at closure; `alembic check` shows
      only the pre-existing BL-013 drift (unchanged signature).

## Key implementation notes
- `ai/language.py::PT_BR_OUTPUT_RULE` appended to every v2 prompt; deterministic UI/clustering
  strings translated; `index.html lang="pt-BR"`.
- `ai/clean_core_analysis/schema.py` (ADR-018 taxonomy, nullable recommendation, no fallback
  category) + `evidence_package.py` (per-pool context budget: ATC/DEP/TF/EVD caps, most-severe
  first, `omitted` counts, ATC priority totals as non-citable context) + `__init__.py` (v2 prompt
  with explicit decision heuristics tying risk/importance to a category).
- `ai/application_discovery/clustering.py` — `shared_concept` removed from the union-find
  entirely (AI-generated free-text concepts are interpretation, not a transitive grouping
  signal); clustering is dependency + shared_package only. `evidence_package.py` bounded the same
  way as Clean Core's.
- `api/routes/dashboard.py` (`/dashboard-overview`, `/object-list`, `/atc-findings`) +
  `components/dashboard/{DashboardGeral,EntityList,DetailPage,charts}.tsx` — the ADR-019
  single-screen drill-down; `ExecutiveView.tsx` and the sidebar perspective views removed.
- `ai/copilot/intent.py` + `context.py` (`CATALOG-*` items) — deterministic pt/en intent routing
  and a bounded assessment catalog so the Copilot can answer inventory/classification questions
  without inventing or refusing every time.
- `ai/executive_summary/` + `api/routes/executive_summary.py` + migration 0018 — new pipeline
  stage between `clean_core_analysis` and `embeddings`; `GET/POST .../executive-summary[/regenerate]`.
- `persistence/models.py::PipelineRunKind.{AI_REPROCESSING,AI_REPROCESSING_APPLICATIONS}` +
  `pipeline/stages.py::{AI_REPROCESSING_STAGES,APPLICATION_REPROCESSING_STAGES}` +
  `api/routes/pipeline.py::reprocess_ai?from_stage=` — the two AI-only reprocessing variants;
  `PipelineRunner.tsx` "Reprocessar IA" button + warning + "Só aplicações → Clean Core → resumo".
- `ai/knowledge_providers/mcp_client.py::_parse_search_results_json` — decodes the real, verified
  JSON `{"results": [...]}` shape the public `mcp-sap-docs`/`mcp-abap` `search` tool returns
  (fixing a real bug where the old "first line = title" heuristic mangled it), falling back to
  the original heuristic for any other shape. `.env`/`.env.example` now document the real public
  hosted endpoints (`https://mcp-sap-docs.marianzeis.de/mcp`, `https://mcp-abap.marianzeis.de/mcp`
  — no auth required).
- Defects found and fixed while reprocessing real data (see `SPRINT-18-PROGRESS.yaml` for full
  detail): orphan empty applications after reclustering; an application double-claimed by a split
  cluster; `clean_core_analysis.schema.sanitize_result` dropping out-of-pool refs per dimension
  and leftover rationale on a dimension the model itself left null, instead of failing the whole
  analysis.
- Cosmetic: the permanent chat panel is rebranded "AIDA" (`CopilotPanel.tsx` header/aria-labels)
  with a reworded empty-state welcome message.

## Known limitations
- Business/usage/OSS-note supplemental evidence for the real Rodobens export could not be
  correlated to any `SAPObject` — verified against the real adapters/payloads (Panaya SAP Notes,
  Signavio process KPIs, Readiness Check simplification/custom-code items are all structurally
  object-less in this export), not a decoding bug. `DESCONTINUAR`/`SUBSTITUIR_STANDARD`/
  `ATUALIZAR_OSS` therefore stayed unused on real data this sprint (BL-026).
- The now-wired `mcp-sap-docs`/`mcp-abap` guidance is real and renders in the UI, but the generic
  `search` tool's hits were never specific enough for the model to cite as recommendation
  evidence on Rodobens (0/105 applications) — `sap_get_object_details`'s real Clean Core A/B/C/D
  verdicts would be a stronger fit and is deferred (BL-027).
- MCP guidance retrieval remains a manual, per-target trigger (ADR-007) — the pipeline never
  auto-queries it; broad backfills (as done once for Rodobens this sprint) are an explicit,
  bounded operational action, not an automated one.

## Deferred items
- BL-018 — resolved this sprint (real public `mcp-sap-docs`/`mcp-abap` endpoints wired).
- BL-026 — Panaya SAP Notes / Signavio process KPIs cannot correlate to a `SAPObject`; candidate
  unmapped Panaya sections (`SCI_HANA_ISSUES(_DETAILS)`) cannot be verified without the original
  export file, no longer present in this environment.
- BL-027 — `MCPKnowledgeProvider` only calls the generic `search` tool; `sap_search_objects`/
  `sap_get_object_details` (real Clean Core A/B/C/D verdicts) are unused.

## Repository closure
- Sprint branch: `sprint/18-final-adjustments`
- Official commit message: `feat(sprint-18): complete final adjustments`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
