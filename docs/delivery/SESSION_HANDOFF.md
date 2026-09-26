# Session Handoff

## Current state
SPRINT-17 (Demo Readiness) is **completed** — closed by `/clean-core-finish-sprint`.
`docs/delivery/SPRINT-17-PROGRESS.yaml` is `status: completed`, `progress_percent: 100`,
`ready_for_review: false`; the result record is `docs/delivery/results/SPRINT-17-RESULT.md`. The
sprint branch was pushed and merged into `main` by fast-forward; the local sprint branch was
deleted (the remote copy is kept as the sprint record).

**Next sprint:** none planned yet — `EXECUTION_STATE.yaml`'s `next_sprint` is `null`. Await a new
sprint file under `docs/delivery/sprints/` before running `/clean-core-run-sprint` again.

## What SPRINT-17 delivered
Demo-hardening polish across the full PoC journey, no new domain capability, no schema change
(alembic head unchanged).

- **CAP-001 — Resizable three-panel shell**: `lib/useResizableWidth.ts` (drag + localStorage
  persistence, no new dependency) + `components/shell/ResizeHandle.tsx`, wired into `App.tsx`
  between Sidebar/Workspace and Workspace/Copilot. `Sidebar`/`CopilotPanel` take a `width` prop
  instead of a fixed Tailwind width class.
- **CAP-002 — Monaco source viewer** (`components/parsing/SourceViewer.tsx`): new bounded
  backend endpoint `GET /assessments/{id}/objects/{object_id}/source`
  (`api/routes/parsing.py::get_object_source`, `_MAX_SOURCE_BYTES=512_000`, truncates rather than
  loading a large real file wholesale — Baseline core rule 10) reads straight from the scan's
  source directory (same `scan.source_path`+`rel_path` lookup pipeline stages already use).
  `lib/monacoSetup.ts` bundles Monaco locally (`loader.config({monaco})`, no CDN — ADR-002
  offline desktop) and relies on monaco-editor's own built-in `abap` Monarch language (no custom
  tokenizer needed). No worker wired up — see BL-024. An automated security review flagged the
  source endpoint's `scan.source_path`+`rel_path` join as a path-traversal gap (no containment
  check) — fixed with `realpath`+`commonpath` verification and an absolute-path rejection; BL-025
  recorded for the same unguarded join pattern pre-existing elsewhere in the codebase (lower
  severity there — none of those call sites return raw file content over HTTP).
- **CAP-003 — React Flow dependency graph** (`components/parsing/DependencyGraph.tsx`, new
  `@xyflow/react` dependency): replaces Technical View's flat dependency list with a small graph
  centered on the selected object; target nodes stay plain labels (never navigable) since
  `SAPObjectDependency.target_name` is unresolved free text (BL-022/BL-016, untouched).
- **CAP-004 — Empty/loading/error state audit**: new `components/shared/ErrorState.tsx`, wired
  into every primary list/summary query that previously only branched on `isLoading` (silently
  rendering a misleading "empty" state on a real fetch error) — `DashboardGeral`, `ExecutiveView`,
  `ApplicationBrowser`, `BusinessRuleBrowser`, `ObjectBrowser`, `ATCImport` (runs list),
  `EvidenceDatasets`, `PipelineRunner`.
- **CAP-005 — Reproducible demo seed extension**: extracted `atc.persistence.persist_atc_import`
  out of `api/routes/atc.py::import_atc_file` (now shared by the route and the seed, no duplicated
  ~150 lines) + `seed/registry.py` v6→v8 adds `_seed_demo_atc_import` (a compact 4-finding ATC
  run against the demo-source objects) and `_seed_demo_evidence_dataset` (a compact real-format
  HANA Sizing Report .txt, imported through the actual adapter/durable-pipeline path) for the
  persistent Acme demo assessment. Applied live: 1 ATCRun (4 findings, all correlated), 4 derived
  TechnicalFindings, 1 EvidenceDataset (`IMPORTED_FULL`, 4 EvidenceRecords).
- **CAP-006 — Full live Playwright demo pass** against the electron-vite renderer over the
  persistent Acme assessment (id 1074): Assessments Home → Ingestion (new evidence dataset
  visible) → ATC (new correlated run) → Technical View (Monaco + dependency graph + AI
  understanding + remediation panel) → Dashboard Geral (KPIs reflect new data) → Executive/
  Functional/Architecture Views → Copilot (grounded answer + graceful insufficient-context
  refusal) → resizable panel drag-and-persist. **One real blocking defect found and fixed**:
  React Flow's internal worker was blocked by `index.html`'s CSP (`script-src 'self'`, no
  `worker-src`) — added `worker-src 'self' blob:`.
- Backend 229/229 pytest passing (224 pre-existing + 5 new in `test_source_snippet.py`, incl. 2
  path-traversal contract tests added for the CAP-002 security fix above; CAP-005's extraction is
  already covered by pre-existing `test_sprint05.py` ATC API tests). Frontend `tsc`/`build` clean
  throughout. **BL-024 recorded** (Monaco's own editor worker cannot be wired up under
  electron-vite's Rollup build — cosmetic console error only, editor fully functional via
  main-thread fallback, not blocking). **BL-025 recorded** (same unguarded
  `scan.source_path`+`rel_path` join pattern pre-exists in `dependencies.py`/`pipeline/stages.py`,
  lower severity since neither returns raw content over HTTP).
- **Demo-readiness note**: the persistent Acme assessment's existing Clean Core/Executive View AI
  analysis predates this sprint's new ATC run + evidence dataset, so its risk narratives currently
  read "no ATC findings/evidence reported" — re-run "3 - Processamento por IA" to let
  `clean_core_analysis` pick up the new signals before a live demo. Not a defect (ADR-012: seeding
  new evidence does not retroactively invalidate already-persisted AI output).

## Restart instructions
SPRINT-17 has no unfinished work — `docs/delivery/SPRINT-17-PROGRESS.yaml` is `status: completed`
and all 6 capabilities are `done`. If resuming this session unexpectedly with no sprint branch
checked out, `main` is the correct branch to be on. There is no next sprint file yet
(`docs/delivery/sprints/` ends at `SPRINT-17-demo-readiness.md`) — a new sprint must be authored
under `docs/delivery/sprints/` before `/clean-core-run-sprint` can start one.

## Previous sprint (SPRINT-16)
SPRINT-16 (AI Copilot) is **completed** — closed by `/clean-core-finish-sprint`.
`docs/delivery/SPRINT-16-PROGRESS.yaml` is `status: completed`, `progress_percent: 100`,
`ready_for_review: false`; the result record is `docs/delivery/results/SPRINT-16-RESULT.md`. The
sprint branch was pushed and merged into `main` by fast-forward; the local sprint branch was
deleted (the remote copy is kept as the sprint record).

During `/clean-core-review-sprint`, one documentation gap was found and resolved before closure:
the sprint's demonstrable outcome mentions following Copilot references back to
source/findings/datasets/guidance, but only `sap_object`/`business_rule`/`application` references
are actually click-through navigable (`resultNav.ts::ResultFocus` doesn't support the other
kinds) — this was an undocumented scope narrowing, now recorded as **BL-023** with rationale in
`SPRINT-16-PROGRESS.yaml`'s notes before finishing.

## What SPRINT-16 delivered
The permanent right-side Copilot (previously a disabled placeholder, ADR-010) is now a real
chat: it answers questions about the open Assessment, grounded in evidence, with working
cross-view navigation, and the conversation survives view/focus switches.

- **Backend — new `copilot` AI capability** (`backend/src/ai/copilot/`): `schema.py`
  (`CopilotAnswerResult` — status ANSWERED/INSUFFICIENT_CONTEXT, `answer`, `evidence_refs`,
  `navigation_ref`; `validate_result` rejects any ref_id not actually present in context) +
  `__init__.py` (registers `copilot/v1` in `ai.registry`, mirroring every other AI capability).
  `context.py` assembles a bounded, citable context package per question — a structured
  summary (`pipeline/dashboard_summary.py`, extracted from `api/routes/dashboard.py` so both
  share one definition — the "structured query" channel), the current UI selection's own
  already-persisted evidence-bound detail (`ObjectUnderstanding`/`BusinessRule`/
  `CleanCoreAssessment`, reusing their existing `evidence_refs` rather than rebuilding a parallel
  evidence package — "source retrieval"/"supplemental evidence retrieval"), `semantic_search`
  hits for the question text ("semantic retrieval"), and already-retrieved
  `SapKnowledgeReference` rows for the selection via `ai.knowledge_service.list_guidance`,
  read-only — the Copilot never itself triggers a new MCP query ("MCP" channel, deliberately
  scoped to avoid contradicting ADR-007's "never a background/bulk job").
- **API**: `POST /assessments/{id}/copilot/ask` (`api/routes/copilot.py` +
  `api/schemas/copilot.py`) — read-only, never mutates assessment state, never persists the
  conversation (stateless, mirrors `semantic_search`'s precedent). A provider/domain-validation
  failure returns `status: "FAILED"` with a message, never a 500.
- **Frontend**: a plain in-view "selection" concept (reusing `ResultFocus`) is lifted from
  ObjectBrowser/BusinessRuleBrowser/ApplicationBrowser up to `App.tsx` via a new
  `onSelectEntity` prop threaded through `Workspace.tsx`, distinct from drill-down `focus`.
  `components/shell/CopilotPanel.tsx` is now a real chat (message list, reference chips via the
  existing `SOURCE_TYPE_LABELS`, a navigation button reusing `onNavigate`/`ResultFocus`) — its
  message state lives in the component itself, which is never unmounted while an assessment is
  open, so the conversation naturally survives every view/focus change without any new
  persistence.
- **Live bug found and fixed**: the first live Bedrock call returned `status: FAILED` because
  the model copied the prompt's `[navigable: kind#id]` annotation text into `navigation_ref`
  instead of the item's real `ref_id`. Fixed by rewording the annotation and tightening the
  system prompt to state `evidence_refs`/`navigation_ref` may only ever be a `ref_id` copied
  verbatim — reverified live immediately after.
- 224/224 backend pytest (215 pre-existing + 9 new in `backend/tests/test_copilot.py`), frontend
  `tsc`/`build` clean, `alembic check` shows only the pre-existing BL-013 drift (no new drift —
  no migration needed this sprint, by design). Live Playwright + real Bedrock validation against
  the persisted Acme Industries assessment (id 1074): asked a grounded question about a selected
  SAPObject in Technical View, followed its navigation reference, switched to Functional View
  (prior conversation still visible, context label updated), selected a business rule, asked a
  second grounded question citing the rule's own evidence plus 2 semantic-search hits, followed
  its navigation reference. BL-023 recorded (see above).

## Previous sprint (SPRINT-15)
SPRINT-15 (Result Navigation Perspectives) is **completed** — closed by
`/clean-core-finish-sprint`. `docs/delivery/SPRINT-15-PROGRESS.yaml` is `status: completed`,
`progress_percent: 100`, `ready_for_review: false`; the result record is
`docs/delivery/results/SPRINT-15-RESULT.md`. The sprint branch was pushed and merged into `main`
by fast-forward; the local sprint branch was deleted (the remote copy is kept as the sprint
record).

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
