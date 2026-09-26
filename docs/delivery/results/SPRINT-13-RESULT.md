# SPRINT-13 Result — Clean Core Intelligence

**Status:** Completed
**Completed at:** 2026-09-26
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
`clean_core_analysis` registers as a 7th `source_processing` pipeline stage, after
`application_discovery`. For every non-`MERGED` `Application`, it assembles a Clean Core evidence
package (`ai/clean_core_analysis/evidence_package.py`) spanning source/dependency identity,
correlated ATC findings, deterministic `TechnicalFinding` severities and technical supplemental
signals (technical pool); object identity plus quality-gated process/usage/user/role supplemental
signals tagged `PROCESS_USAGE_EVIDENCE` (business pool, only ever populated from `MATCHED_*`
correlations — ADR-017's quality gate); and already-retrieved `SapKnowledgeReference` guidance
(external authoritative context, ADR-007, available to both dimensions). It calls the configured
`AIProvider` through the versioned `clean_core_analysis/v1` prompt+schema and upserts one
`CleanCoreAssessment` row per Application (migration `0015`, mirrors `ObjectUnderstanding`'s
upsert-not-recreate pattern).

Baseline core rule 8 ("Clean Core output separates Technical Risk, Business Importance and
Recommendation") is enforced structurally: each dimension has its own rationale + evidence_refs
field, drawn from its own pool only (never the other dimension's), and — after a mid-sprint fix
described below — each dimension is independently determinable. `recommendation` is
RETAIN/REMEDIATE/REPLATFORM/RETIRE/**REVIEW**, with `REVIEW` as the explicit fallback: forced when
neither dimension could be determined at all, and a legitimate model choice otherwise when the
evidence is too thin or conflicting for a confident non-REVIEW call. `business_importance`'s
resolved evidence_refs are inspected at persistence time to set
`business_importance_uses_process_usage_evidence` — a transparency flag surfaced directly in the
UI so the analyst can see whether a conclusion actually rested on a process/usage/role signal
(Baseline core rule 11) or on object identity alone.

The Architecture View (`ApplicationBrowser.tsx`, already built in SPRINT-11) gained a `CleanCore`
panel per application (risk/importance/recommendation, rationale, evidence-ref chips, the
process/usage transparency line) and a recommendation-distribution summary atop the application
list — the sprint's "dashboards and drill-down" capability delivered inside the existing screen
rather than building out Dashboard Geral/Executive View, which remain SPRINT-15's dedicated scope.

### Mid-sprint schema fix
The first live Bedrock run over `demo-source/ABAP` showed **all 4** discovered applications
persisting as `CleanCoreStatus.FAILED`. Root cause: the original `CleanCoreAnalysisResult` tied
`technical_risk`/`business_importance` nullability to one blanket `status` field
(`INSUFFICIENT_CONTEXT` ⇒ both must be null). Real model behavior: a sparsely-evidenced
single-object cluster routinely gets a determined `technical_risk` (e.g. "no findings, no risky
dependencies" already supports LOW) while the model still judges the naming/business evidence too
thin for a confident recommendation and reports `status=INSUFFICIENT_CONTEXT` for the overall
call — a legitimate partial result the original validator always rejected (the opposite of
ADR-012's "allow insufficient-context results rather than forced conclusions" intent). Fixed by
making each dimension independently nullable — gated only by its own rationale/evidence — with
`status` now *derived* from whether anything was determined at all. Re-validated live after the
fix: 4/4 applications persisted with a real conclusion (2 RETAIN, 1 REPLATFORM, 1 REVIEW for the
one genuinely under-evidenced single-object cluster), zero FAILED.

## Demonstration path
1. Open an Assessment, ingest `demo-source/ABAP`, run "3 - Processamento por IA" to completion
   (now 7 stages, ending in "Análise Clean Core").
2. Open Architecture View — the application list header shows a recommendation-distribution
   summary (e.g. "Manter · 2", "Revisão necessária · 1", "Replataformar · 1").
3. Select an application — its detail panel shows a "Clean Core" section with Risco Técnico and
   Importância de Negócio (each with rationale + evidence chips) kept visually and structurally
   separate, a line stating whether process/usage evidence was actually used, and a Recomendação
   chip with its own rationale + evidence.
4. Selecting a sparsely-evidenced single-object application shows both dimensions as "—"
   (undetermined) and Recomendação "Revisão necessária", with a rationale explaining the gap.

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint (backend `/health` reports
  `migration_revision: 0015_clean_core_analysis`; `alembic current` at
  `0015_clean_core_analysis (head)`, applied linearly from `0014`; `alembic check` shows only the
  pre-existing BL-013 drift, nothing new from `clean_core_assessment`).
- [x] Critical contracts introduced by the sprint: `CleanCoreEvidencePackage`/`EvidenceItem`
  (`ai/clean_core_analysis/evidence_package.py`), `CleanCoreAnalysisResult`/`validate_result`
  (`ai/clean_core_analysis/schema.py`), the `clean_core_analysis/v1` prompt registration
  (`ai/clean_core_analysis/__init__.py`), the 7th `StageDefinition` and
  `_upsert_clean_core_assessment` (`pipeline/stages.py`), and `ApplicationRead.clean_core`
  (`api/schemas/clean_core.py` + `api/routes/applications.py`) — covered by
  `tests/test_clean_core_analysis.py` (15 domain-validator/registry tests) and
  `tests/test_clean_core_analysis_pipeline.py` (4 pipeline-integration + API tests: completed,
  insufficient-context, provider-error, and the embedded API contract).
- [x] Primary demonstrable user flow: reproduced live via Playwright against the real
  electron-vite renderer (`localhost:5173`) with a real Bedrock pipeline run over
  `demo-source/ABAP` — ingested, processed all 7 stages to completion, opened Architecture View,
  confirmed the recommendation distribution and the Clean Core panel's risk/importance/
  recommendation/evidence/process-usage-transparency rendering for both a fully-determined
  (RETAIN) and an undetermined-dimensions (REVIEW) application. Disposable demo Client/Assessment
  deleted afterward (scoped `DELETE FROM client WHERE name = 'Sprint13 Live Smoke'`).
- [x] Required integration checks: full backend suite **208/208** `pytest` passed (confirmed twice
  with no concurrent activity, after two runs interfered with a concurrently-running live demo —
  see Known limitations/BL-008); frontend `tsc --noEmit` and `npm run build` both clean.
  Pre-existing tests updated for the new 7-stage pipeline: `test_foundation.py` (migration
  revision), `test_sprint06.py` (stage count 6→7), and a default `clean_core_analysis_result` fake-
  provider output added to `test_application_discovery_pipeline.py`/
  `test_business_rule_discovery_pipeline.py` so their existing mocks still reach a "completed" run
  (same technique SPRINT-11 used when it added `application_discovery_result` to SPRINT-10's test
  file).
- [x] Migration applicability: `0014_sap_knowledge_mcp` → `0015_clean_core_analysis` applied;
  `alembic current`/`heads` both at `0015_clean_core_analysis (head)`.

## Key implementation notes
- **`backend/src/persistence/models.py`**: `CleanCoreAssessment` (+ `CleanCoreStatus`/`RiskLevel`/
  `ImportanceLevel`/`CleanCoreRecommendation`) — migration `0015_clean_core_analysis`.
- **`backend/src/ai/clean_core_analysis/`** (new): `evidence_package.py`, `schema.py`,
  `__init__.py`.
- **`backend/src/pipeline/stages.py`**: `_clean_core_analysis_prepare`/`_process_item`,
  `_upsert_clean_core_assessment`, 7th `StageDefinition`.
- **`backend/src/api/`**: `schemas/clean_core.py::CleanCoreAssessmentRead`, embedded into
  `schemas/applications.py::ApplicationRead` and populated in `routes/applications.py::_to_read`.
- **Frontend**: `components/architecture/ApplicationBrowser.tsx` — `CleanCorePanel`,
  `CleanCoreDistribution`, `RecommendationChip`, `LevelBadge` (design system's `low`/`attention`/
  `legacy`/`risk` severity palette); `lib/api.ts::CleanCoreAssessmentRecord`; `SOURCE_TYPE_LABELS`
  (`ObjectBrowser.tsx`) gained `TECHNICAL_FINDING`/`PROCESS_USAGE_EVIDENCE`/`SAP_KNOWLEDGE`;
  `PipelineRunner.tsx` gained `application_discovery`/`clean_core_analysis` stage labels (the
  first was a pre-existing gap, fixed in passing).

## Known limitations
- No manual user-override/validation endpoint for the Clean Core recommendation — recorded as
  **BL-019**.
- **BL-008** (pre-existing, `pipeline.engine.recover_orphans` global/unscoped) reproduced live
  twice during this sprint's own validation when a pytest run and a live Playwright demo overlapped
  against the shared dev database. Both transient (resuming the paused demo run completed it
  correctly; a subsequent isolated full-suite run passed 208/208) — no code change made, unrelated
  to this sprint's own logic.
- Dashboard Geral / Executive View remain placeholders — intentionally deferred to SPRINT-15.

## Deferred items
- **BL-019** (new): no manual override/validation for the Clean Core recommendation.
- **BL-008** (pre-existing): amended with a SPRINT-13 live reproduction note.
- BL-013/BL-014/BL-015/BL-016/BL-017/BL-018 are pre-existing and unrelated to this sprint,
  untouched.

## Repository closure
- Sprint branch: `sprint/13-clean-core-intelligence`
- Official commit message: `feat(sprint-13): complete clean core intelligence`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
