# Session Handoff

## Current state
SPRINT-13 (Clean Core Intelligence) is **completed** — closed by `/clean-core-finish-sprint`.
`docs/delivery/SPRINT-13-PROGRESS.yaml` is `status: completed`, `progress_percent: 100`,
`ready_for_review: false`; the result record is `docs/delivery/results/SPRINT-13-RESULT.md`. The
sprint branch was pushed and merged into `main` by fast-forward; the local sprint branch was
deleted (the remote copy is kept as the sprint record).

**Next sprint:** SPRINT-14 — Embeddings and Semantic Retrieval
(`docs/delivery/sprints/SPRINT-14-embeddings-and-semantic-retrieval.md`), not started.

## What was delivered
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
SPRINT-13 has no unfinished work — `docs/delivery/SPRINT-13-PROGRESS.yaml` is `status: completed`
and all 6 capabilities are `done`. If resuming this session unexpectedly with no sprint branch
checked out, `main` is the correct branch to be on; the next action is `/clean-core-run-sprint`
for SPRINT-14, not a resume of SPRINT-13.
