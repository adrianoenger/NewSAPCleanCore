# Session Handoff

## Current state
SPRINT-15 (Result Navigation Perspectives) is **completed** — closed by
`/clean-core-finish-sprint`. `docs/delivery/SPRINT-15-PROGRESS.yaml` is `status: completed`,
`progress_percent: 100`, `ready_for_review: false`; the result record is
`docs/delivery/results/SPRINT-15-RESULT.md`. The sprint branch was pushed and merged into `main`
by fast-forward; the local sprint branch was deleted (the remote copy is kept as the sprint
record).

**Next sprint:** SPRINT-16 — AI Copilot (`docs/delivery/sprints/SPRINT-16-ai-copilot.md`), not
started.

## What SPRINT-15 delivered
Result navigation now matches ADR-009/Baseline in full: Dashboard Geral and Executive View are
real pages (previously `PlaceholderView` stubs); all five result views (Dashboard Geral,
Executive, Technical, Functional, Architecture) support cross-view drill-down while preserving
Assessment/Client context and the permanent right-side Copilot.

- **`frontend/src/renderer/src/lib/resultNav.ts`**: `ResultFocus` union (`sap_object` |
  `business_rule` | `application`) + `FOCUS_VIEW` mapping each focus kind to its nav item.
  `App.tsx` lifts `activeView`/`focus` state; `selectView` (plain sidebar switch, clears focus) vs.
  `navigateToFocus` (drill-down: sets focus + switches view) are the only two ways navigation
  changes. `Workspace.tsx` threads `focus`/`onNavigate`/`onSelectView` to each view.
- **Backend**: `GET /assessments/{id}/dashboard-summary` (`api/routes/dashboard.py` +
  `api/schemas/dashboard.py`) aggregates the Baseline's Preliminary Processing Summary KPIs
  server-side (objects analisados, customizações identificadas = discovered `Application` count,
  findings críticos = `TechnicalFinding.severity=HIGH`, objetos com alto impacto = objects whose
  owning Application has `technical_risk` HIGH/CRITICAL, regras de negócio identificadas =
  `CANDIDATE` `BusinessRule` count) plus `is_stale`. `SAPObjectRead` gained `application_id` (the
  ORM column already existed, just wasn't exposed) so the frontend can resolve an object's owning
  Application. `backend/tests/test_dashboard.py` (2 tests).
- **`components/dashboard/DashboardGeral.tsx`**: 5 KPI cards + 4 quick-nav cards (deliberately no
  risk/roadmap detail — Baseline: "must not duplicate Executive View").
- **`components/dashboard/ExecutiveView.tsx`**: top-5 technical risks, high-risk+high-importance
  "critical applications", Clean Core distribution with macro-recommendation sentences, and a
  roadmap grouped by recommendation (RETIRE/REPLATFORM/REMEDIATE/REVIEW/RETAIN order) — all sourced
  from the existing `fetchApplications` (no new backend needed), every item drills into
  Architecture View via `onNavigate({kind:'application', id})`.
- **`components/shared/cleanCoreDisplay.tsx`**: `RecommendationChip`/`LevelBadge`/
  `countByRecommendation` extracted out of `ApplicationBrowser.tsx` so `ObjectBrowser.tsx`
  (Technical) doesn't need to import from `ApplicationBrowser.tsx` (Architecture) — would have been
  a circular import.
- **Technical View → remediation proposal** (`ObjectBrowser.tsx::RemediationPanel`): when an object
  has `application_id`, fetches that Application and shows its Clean Core
  `recommendation`/`recommendation_rationale` as the Baseline's "remediation proposal" — reuses the
  existing AI-generated, evidence-bound field (Baseline rule 8) rather than adding a second
  competing AI field/schema/migration.
- **Architecture View drill-down** (`ApplicationBrowser.tsx`): the previously-static
  `business_rules`/`findings` lists in `ApplicationDetail` are now buttons calling
  `onNavigate({kind:'business_rule'|'sap_object', id})`.
- **Functional View drill-down** (`BusinessRuleBrowser.tsx::RuleObjectContext`): the previously
  static "Objeto de origem" block is now a button calling `onNavigate({kind:'sap_object', id})`.
- **CAP-006 scope note**: Architecture View's "coupling patterns" (cross-application dependency
  graph) was NOT implemented — `SAPObjectDependency.target_name` is free text, never resolved to a
  target `SAPObject.id`, so there's no existing signal for whether a dependency edge crosses an
  Application boundary (same root gap as BL-016). Recorded as **BL-022**. **BL-021** also recorded:
  the Baseline's "customisation identification" AI step (distinct from `application_discovery`) has
  no dedicated capability yet — Dashboard Geral's "Customizações identificadas" KPI maps to the
  discovered-`Application` count instead.
- Validation: 215/215 backend pytest (213 pre-existing + 2 new), frontend `tsc`/`build` clean.
  **Live validation**: reprocessed the persistent Acme Industries demo assessment (id 1074, a real
  live Bedrock pipeline run, id 3327 — its prior processing predated `application_discovery`/
  `clean_core_analysis`) and drove the electron-vite renderer at `localhost:5173` with Playwright
  through the full chain Dashboard Geral → Executive View → Architecture View (business-rule
  click) → Functional View (source-object click) → Technical View (remediation-panel click) →
  Architecture View again — Assessment/Client breadcrumb and Copilot panel/context label stayed
  correct throughout, and direct sidebar navigation correctly cleared stale drill-down focus. Found
  and fixed one live bug: a pluralization concatenation bug in `ExecutiveView.tsx`'s macro
  recommendation sentence ("aplicaçãoões" → "aplicações").

## Restart instructions
SPRINT-15 has no unfinished work — `docs/delivery/SPRINT-15-PROGRESS.yaml` is `status: completed`
and all 8 capabilities are `done`. If resuming this session unexpectedly with no sprint branch
checked out, `main` is the correct branch to be on; the next action is `/clean-core-run-sprint`
for SPRINT-16, not a resume of SPRINT-15.

## Previous sprint (SPRINT-14)
SPRINT-14 (Embeddings and Semantic Retrieval) is **completed** — closed by
`/clean-core-finish-sprint`. `docs/delivery/SPRINT-14-PROGRESS.yaml` is `status: completed`,
`progress_percent: 100`, `ready_for_review: false`; the result record is
`docs/delivery/results/SPRINT-14-RESULT.md`. The sprint branch was pushed and merged into `main`
by fast-forward; the local sprint branch was deleted (the remote copy is kept as the sprint
record).

## What SPRINT-14 delivered
`embeddings` registers as an 8th `source_processing` pipeline stage, after `clean_core_analysis`:
for every Assessment, it builds embeddable text/metadata for meaningful semantic entities —
`SAP_OBJECT` (only objects with a `COMPLETED` `ObjectUnderstanding`; the AI-understood purpose,
never raw ABAP source), `APPLICATION`, `BUSINESS_RULE` (`CANDIDATE` only), and quality-gated
process/usage `EVIDENCE_RECORD` signals (same `MATCHED_*`-correlated, business-capability-tagged
pool `ai.clean_core_analysis.evidence_package` already trusts) — calls the configured
`EmbeddingProvider` (new ADR-006-style abstraction mirroring `AIProvider`, since embedding is a
different API shape from structured completion) and upserts one `Embedding` row per
`(assessment_id, entity_type, entity_id)` (migration `0016_embeddings`, pgvector `Vector(1024)` +
HNSW cosine index). `content_hash` skips re-calling the provider when an entity's rebuilt text is
unchanged (pipeline-architecture.md's Incrementality principle) — verified live: `BUSINESS_RULE`
still re-embeds every run because `business_rule_discovery` deletes+reinserts its rows rather than
upserting (BL-020, pre-existing, not this sprint's stage's own gap).

- **`backend/src/ai/embedding_provider.py`** + **`ai/embedding_providers/{bedrock,azure_foundry}.py`**
  + **`ai/embedding_providers/__init__.py::get_embedding_provider`**: Bedrock (Amazon Titan Text
  Embeddings V2, live-validated) + Azure AI Foundry (unit-tested only, no credentials — mirrors
  the ADR-006 Azure precedent since SPRINT-09/12). New `settings.py` fields:
  `embedding_provider`/`bedrock_embedding_model_id`/`embedding_dimensions`/
  `azure_foundry_embedding_deployment`.
- **`backend/src/persistence/models.py::Embedding`** (+ `SemanticEntityType`) — migration
  `0016_embeddings`. Polymorphic `entity_type`/`entity_id` (no FK, mirrors
  `EvidenceCorrelation.target_type`/`target_id`); `pgvector.sqlalchemy.Vector(1024)` column with
  an HNSW cosine-ops index declared in `__table_args__` (so `alembic check` sees zero new drift —
  the index must be declared in the ORM model, not just raw SQL in the migration, or autogenerate
  will propose removing it every time).
- **`backend/src/ai/embeddings/`**: `source_builder.py` (`collect_embeddable_entities`),
  `search.py` (`semantic_search` — pgvector cosine-distance ranking, always `assessment_id`-
  filtered).
- **`backend/src/pipeline/stages.py`**: `_embeddings_prepare`/`_embeddings_process_item` + the 8th
  `StageDefinition`.
- **API**: `api/routes/semantic_search.py` — `GET /assessments/{id}/semantic-search?q=...&entity_types=...`
  (debug endpoint, read-only, never exposes raw vectors).
- **Frontend**: `components/debug/SemanticSearchPanel.tsx` + a new sidebar "Debug" nav group
  (`Sidebar.tsx`/`Workspace.tsx`) — deliberately separate from the canonical Dashboard Geral +
  4-perspective result views (Baseline core rule 15), since this is the sprint's own "simple
  semantic search UI/debug endpoint" capability, not a 5th perspective.
- **`.gitignore` fix**: the pre-existing blanket `embeddings/` ignore pattern (meant for a
  file-based vector-index cache from before pgvector was decided) shadowed the new
  `backend/src/ai/embeddings/` source directory — re-anchored to `/embeddings/` (root-only).
- 213/213 backend pytest (fresh rebuilt Docker image with `pgvector` baked into
  `backend/pyproject.toml`), frontend `tsc`/`build` clean. Live-validated twice: a real Bedrock
  HTTP run (structured completion + Titan embeddings) over demo-source/ABAP completing the full
  8-stage pipeline with 0 failures, and a real Playwright pass against the electron-vite renderer
  confirming the demonstrable outcome (search ranked order-validation rules/objects highest for a
  Portuguese business-concept query; the entity-type filter chips reactively narrow results).
  Disposable demo clients deleted after both runs.
- **BL-020 recorded** (pre-existing `business_rule_discovery` recreate-not-upsert semantics leave
  orphaned `Embedding` rows on reprocessing — see BACKLOG.md).

## Previous sprint (SPRINT-13)

SPRINT-13 (Clean Core Intelligence) is **completed** — closed by `/clean-core-finish-sprint`.
`docs/delivery/SPRINT-13-PROGRESS.yaml` is `status: completed`, `progress_percent: 100`,
`ready_for_review: false`; the result record is `docs/delivery/results/SPRINT-13-RESULT.md`. The
sprint branch was pushed and merged into `main` by fast-forward; the local sprint branch was
deleted (the remote copy is kept as the sprint record).

## What SPRINT-13 delivered
`clean_core_analysis` registers as a 7th `source_processing` pipeline stage, after
`application_discovery`: for every non-`MERGED` `Application`, it assembles a Clean Core evidence
package spanning source/dependency/ATC/`TechnicalFinding` (technical pool), quality-gated
supplemental `EvidenceRecord`s split into technical-signal vs. business/process/usage/role-signal
pools, and already-retrieved `SapKnowledgeReference` guidance (external context, both pools), then
calls the configured `AIProvider` through the versioned `clean_core_analysis/v1` prompt+schema and
persists one `CleanCoreAssessment` row per Application (upsert, mirroring `ObjectUnderstanding`).

- **`backend/src/persistence/models.py::CleanCoreAssessment`** (+ `CleanCoreStatus`/`RiskLevel`/
  `ImportanceLevel`/`CleanCoreRecommendation`) — migration `0015_clean_core_analysis`. One row per
  `Application`; `technical_risk`/`business_importance` are independently nullable columns (see
  the schema redesign note below); `recommendation` includes `REVIEW` as the explicit fallback.
- **`backend/src/ai/clean_core_analysis/`**: `evidence_package.py` (technical/business/guidance
  pools, `PROCESS_USAGE_EVIDENCE` vs `SUPPLEMENTAL_EVIDENCE` source-type tagging so the UI can show
  whether a business_importance conclusion actually used a process/usage signal), `schema.py`
  (`CleanCoreAnalysisResult` + `validate_result`), `__init__.py` (registers `clean_core_analysis/v1`
  prompt+schema).
- **`backend/src/pipeline/stages.py`**: `_clean_core_analysis_prepare`/`_process_item` + the 7th
  `StageDefinition`, `_upsert_clean_core_assessment` (mirrors `_upsert_understanding`).
- **API**: `api/schemas/clean_core.py::CleanCoreAssessmentRead` embedded as `ApplicationRead.clean_core`
  (both list and detail `/assessments/{id}/applications[...]` endpoints) — no new routes.
- **Frontend**: `components/architecture/ApplicationBrowser.tsx` — `CleanCorePanel` (risk/
  importance/recommendation with rationale + evidence chips + the process/usage transparency line),
  `CleanCoreDistribution` (recommendation counts atop the application list), `RecommendationChip`/
  `LevelBadge` using the design system's existing 4-level severity palette (`low`/`attention`/
  `legacy`/`risk`). `PipelineRunner.tsx` gained `application_discovery`/`clean_core_analysis` stage
  labels (the first was a pre-existing gap, fixed in passing). `SOURCE_TYPE_LABELS` (ObjectBrowser)
  gained `TECHNICAL_FINDING`/`PROCESS_USAGE_EVIDENCE`/`SAP_KNOWLEDGE`.
- **Pre-existing test updates**: `test_foundation.py` (migration_revision 0014→0015),
  `test_sprint06.py` (stage count 6→7), `test_application_discovery_pipeline.py`/
  `test_business_rule_discovery_pipeline.py` (added a default `clean_core_analysis_result` fake-
  provider output so the now-7-stage pipeline still reaches "completed" under their existing mocks
  — same technique SPRINT-11 used for `application_discovery_result` in the SPRINT-10 test file).
- 208/208 backend pytest, frontend `tsc`/`build` clean, a real live Bedrock run over
  demo-source/ABAP (4 discovered applications: 2 RETAIN, 1 REPLATFORM, 1 REVIEW — no FAILED after
  the schema fix below) and a real Playwright pass against the electron-vite renderer confirming
  the demonstrable outcome end to end (disposable demo client deleted after).

### Mid-sprint schema redesign (read before touching this capability again)
The first live Bedrock run showed **all 4** discovered applications persisting as
`CleanCoreStatus.FAILED`. Root cause: the original `CleanCoreAnalysisResult` tied
`technical_risk`/`business_importance` nullability to one blanket `status` field
(`INSUFFICIENT_CONTEXT` ⇒ both must be null). Real model behavior: a sparsely-evidenced
single-object cluster routinely gets a determined `technical_risk` (e.g. "no findings, no risky
dependencies" already supports LOW) while the model still judges the naming/business evidence too
thin for a confident recommendation and reports `status=INSUFFICIENT_CONTEXT` — a legitimate
partial result the old validator always rejected. Fixed by making each dimension independently
nullable (own rationale/evidence_refs gate), with `status` now *derived* from whether anything was
determined at all rather than dictating what may be determined. See
`ai/clean_core_analysis/schema.py`'s module docstring for the full rationale — do not revert to the
blanket-status design.

## Known deferrals / backlog
- No manual user-override/validation endpoint for the Clean Core recommendation — not in this
  sprint's planned capabilities. Worth reconsidering alongside SPRINT-15's Functional View
  user-validation work if a demo asks for it.
- **BL-008** (pre-existing, unrelated to this sprint's own logic) reproduced live twice during
  validation: running the backend pytest suite concurrently with a live Playwright pipeline demo
  paused the demo's own run and inflated `recover_orphans`' count in
  `test_sprint06.py::test_recover_orphans_requeues_running_work`. Both were transient (resuming the
  paused run completed correctly; a subsequent full-suite run alone passed 208/208) — do not run
  pytest and a live demo concurrently against the shared dev database in future sessions.

## Restart instructions
SPRINT-14 has no unfinished work — `docs/delivery/SPRINT-14-PROGRESS.yaml` is `status: completed`
and all 7 capabilities are `done`. If resuming this session unexpectedly with no sprint branch
checked out, `main` is the correct branch to be on; the next action is `/clean-core-run-sprint`
for SPRINT-15, not a resume of SPRINT-14.

Note for SPRINT-15 (or whichever sprint next touches the backend Docker image): SPRINT-14 rebuilt
the backend image (`docker compose build backend`) to bake the new `pgvector` Python dependency
into `backend/pyproject.toml`. If a fresh environment/CI ever builds from a cached pre-SPRINT-14
image, `pgvector` will be missing — rebuild rather than reuse a stale cached layer.
