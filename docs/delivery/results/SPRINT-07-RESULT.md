# SPRINT-07 Result — Consolidate Processing Flow

**Status:** Completed
**Completed at:** 2026-09-25
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Consolidated the Assessment workflow into the canonical 3-step flow (Baseline R3.2 / ADR-015): **1 - Ingestão dos dados → 2 - Análise ATC → 3 - Processamento por IA**. The orphan, unnumbered "Pipeline de Processamento" nav item introduced in SPRINT-06 is gone — the durable pipeline engine (ADR-005: scan → parse → detect_dependencies, with pause/resume/retry/orphan-recovery) is now the real implementation of Step 3. It auto-detects the current (latest completed) ingestion instead of asking the user to pick a directory again, and its `scan` stage reuses Step 1's already-completed `SourceScan` instead of re-walking the filesystem. A new ingestion now genuinely invalidates previously derived results: `GET /objects` is scoped to the current scan, and Step 3 shows a "Desatualizado" banner until reprocessed.

## Demonstration path
1. Open an Assessment → Step 1 (Ingestão) → scan a directory (e.g. `/workspace/demo-source/ABAP`).
2. Open Step 3 (Processamento por IA) → it auto-shows that directory as the current ingestion, with a "Desatualizado" banner and an "Iniciar Processamento" button (no path input).
3. Click it → scan/parse/detect_dependencies stages complete (scan is reused, not re-walked) → Technical View shows the parsed SAP objects, read-only.
4. Go back to Step 1 → scan a *different* directory (e.g. `/workspace/demo-source/DDIC`).
5. Open Step 3 → it now shows the new directory and "Desatualizado" again → click "Reprocessar" → banner clears.
6. Technical View now shows **only** the new scan's objects — the previous ingestion's objects are excluded, confirming invalidation.

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint (backend `/health` reports `migration_revision: 0007_durable_pipeline_execution`, unchanged — no schema change this sprint).
- [x] Critical contracts introduced by the sprint (`GET /assessments/{id}/pipeline-runs/processing-status`; `/objects` scoping; removal of `POST /assessments/{id}/scans/{scan_id}/parse`, verified via `test_sprint07.py`).
- [x] Primary demonstrable user flow (reproduced live via Playwright against the Electron renderer dev server — see Demonstration path above).
- [x] Required integration checks: full backend suite `pytest` 77/77 passed (68 prior + 9 new in `test_sprint07.py`, minus 1 removed obsolete test in `test_sprint03.py`); frontend `tsc --noEmit` and `npm run build` both clean.
- [x] Migration applicability: N/A — no schema change; `alembic current`/`heads` both remain at `0007_durable_pipeline_execution`.

## Key implementation notes
- **`backend/src/pipeline/status.py`** (new): `get_current_scan` (latest completed `SourceScan` per assessment) and `compute_processing_status` (derives `is_processed`/`is_stale` purely from existing `PipelineRun`/`StageRun` rows — no new persisted field, no migration).
- **`backend/src/pipeline/stages.py`**: `_scan_prepare` reuses a completed `SourceScan` for the same resolved directory instead of re-scanning; guarded by `_same_directory()`, which requires the candidate's directory to still exist on disk (an older, unrelated scan whose directory was deleted/moved must never be treated as reusable — caught during implementation by a regression in `test_second_pipeline_run_dependencies_stage_ignores_other_scans`, fixed with the existence guard).
- **`backend/src/api/routes/pipeline.py`** / **`schemas/pipeline.py`**: new `GET .../pipeline-runs/processing-status` (`ProcessingStatusRecord`).
- **`backend/src/api/routes/parsing.py`**: `list_objects` scoped to the current scan; manual `POST /assessments/{id}/scans/{scan_id}/parse` route, `_parse_scan_files`, and `ParseJobRead` schema removed.
- **`frontend/.../pipeline/PipelineRunner.tsx`**: rewritten as Step 3 — no manual directory picker, driven by `fetchProcessingStatus`; empty state, staleness banner, and "Iniciar Processamento"/"Reprocessar" button; `activeRunId` auto-selection prefers the run for the current scan and resets when the current scan changes; `processingStatus` polling now tied to whether a run is active (fixes a live-tested bug where the staleness banner never cleared after a run finished).
- **`frontend/.../shell/Sidebar.tsx`** / **`Workspace.tsx`**: orphan nav item removed; `ai-processing` renders `PipelineRunner`.
- **`frontend/.../parsing/ObjectBrowser.tsx`**: read-only now (manual "Parse" button removed), with a staleness indicator.
- **`frontend/.../lib/api.ts`**: removed `triggerParse`/`ParseJobResult`; added `fetchProcessingStatus`/`ProcessingStatusRecord`.
- **`backend/tests/test_sprint07.py`** (new, 10 tests) + `test_sprint03.py` (1 obsolete test removed).
- Documentation renumbering: sprints previously numbered 07-15 (AI Object Understanding onward) shifted to 08-16 to make room for this sprint, per the roadmap's existing "Sequence invariant" precedent — `development-roadmap.md`, `BACKLOG.md` (BL-003), and all 9 sprint definition files updated in the same change.

## Known limitations
- Step 3 ("Processamento por IA") currently runs only the deterministic capabilities carried over from SPRINT-03/05 (regex/heuristic ABAP parsing and dependency detection) — no AWS Bedrock/Azure AI Foundry call happens yet. Real AI processing is planned for SPRINT-08 (AI Object Understanding), which will register its stages in the same durable engine (BL-003).
- ATC import remains intentionally standalone, not wrapped as a pipeline stage (ADR-016/BL-002) — untouched by this sprint.
- Manual dependency-detection routes in `dependencies.py` are the same class of pre-existing duplication as the old manual parse route, but are not used by any UI component today, so were left as-is to avoid silent scope expansion.

## Deferred items
- **BL-004** (new): reprocessing Step 3 recreates `SAPObject` rows per `source_file_id`, which can break `ATCFinding.correlated_object_id`. Needs a human decision on stable object identity or a re-correlation pass — out of scope here since ATC was not touched.
- **BL-002**, **BL-003** (carried over from SPRINT-06, references updated to SPRINT-08+).

## Repository closure
- Sprint branch: `sprint/07-consolidate-processing-flow`
- Official commit message: `feat(sprint-07): complete consolidate processing flow`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
