# Session Handoff

## Current state
SPRINT-07 (Consolidate Processing Flow) is **completed** on branch `main`, closed via `/clean-core-finish-sprint`. See `docs/delivery/results/SPRINT-07-RESULT.md` for the full closure record.

This sprint was inserted before the sprint previously numbered SPRINT-07 (AI Object Understanding, now **SPRINT-08**); sprints previously numbered 08-15 shifted to 09-16 — see `development-roadmap.md` and `EXECUTION_STATE.yaml`.

## Why this sprint existed
SPRINT-06's durable pipeline ("Pipeline de Processamento") duplicated Step 1's ingestion scan and lived as an orphan, unnumbered nav item between "1 - Ingestão" and "2 - Análise ATC", while the canonical Baseline R3.2 / ADR-015 third step ("3 - Processamento por IA") was still an empty placeholder. This sprint finished what SPRINT-06 started: the durable engine is now the real Step 3.

## What was delivered

### Backend
- **`pipeline/status.py`** (new): `get_current_scan` (latest completed `SourceScan` for an assessment — "last ingestion wins") and `compute_processing_status` (derives `is_processed`/`is_stale` from `PipelineRun`/`StageRun` rows — no new persisted state, no migration).
- **`pipeline/stages.py`**: `_scan_prepare` now reuses Step 1's already-completed `SourceScan` for the same resolved directory instead of re-walking the disk — guarded by `_same_directory()`, which requires the candidate scan's directory to still *exist* on disk (an older, unrelated scan whose directory was since deleted/moved must never be treated as reusable; this is exactly the scenario `test_second_pipeline_run_dependencies_stage_ignores_other_scans` protects, and it regressed once during implementation before the existence guard was added).
- **`api/routes/pipeline.py`** + **`api/schemas/pipeline.py`**: new `GET /assessments/{id}/pipeline-runs/processing-status` (`ProcessingStatusRecord`).
- **`api/routes/parsing.py`**: `list_objects` now scoped to the current scan only (an older, superseded scan's objects are excluded — this is what makes "new ingestion invalidates stale results" real, not cosmetic). Manual `POST /assessments/{id}/scans/{scan_id}/parse` route, `_parse_scan_files`, and `ParseJobRead` schema removed — parsing is only triggered by the durable pipeline now.
- **`backend/tests/test_sprint07.py`** (new, 10 tests): scan reuse, `compute_processing_status` scenarios (no scan / not processed / processed / stale-after-newer-ingestion), `processing-status` endpoint contract, `/objects` scoping, and 404 on the removed parse route.
- **`backend/tests/test_sprint03.py`**: removed `test_parse_endpoint_returns_accepted` (route no longer exists).

### Frontend
- **`components/pipeline/PipelineRunner.tsx`**: rewritten as the real "3 - Processamento por IA" view — no manual directory picker; auto-detects the current ingestion via `fetchProcessingStatus`, shows an empty state when there is none yet, a "Desatualizado" banner + "Iniciar Processamento"/"Reprocessar" button when `is_stale`, and the existing progress/pause/resume/retry/history panels otherwise. `activeRunId` auto-selection now prefers the run matching the current scan and resets when the current scan changes.
- **`components/shell/Sidebar.tsx`** / **`Workspace.tsx`**: orphan "Pipeline de Processamento" nav item removed; `ai-processing` now renders `PipelineRunner` instead of a placeholder.
- **`components/parsing/ObjectBrowser.tsx`**: manual "Parse" button removed — Technical View is read-only now, with a staleness indicator sourced from `fetchProcessingStatus`.
- **`lib/api.ts`**: removed `triggerParse`/`ParseJobResult`; added `fetchProcessingStatus`/`ProcessingStatusRecord`.

### Bug found and fixed during the live browser pass
**`PipelineRunner.tsx` — the "Desatualizado" banner never cleared after a run finished.** `processingStatus` was only invalidated once, right when `handleStart` fired; if the background pipeline task hadn't completed by that single refetch, nothing ever refetched it again (unlike `runsQuery`, which polls continuously while a run is active). Fixed by tying `statusQuery`'s `refetchInterval` to the same "is any run active" condition as `runsQuery`; re-verified live.

## Validation performed
- `docker compose exec backend pytest -q` → **77/77 passed** (68 prior + 9 new in `test_sprint07.py`, minus 1 removed in `test_sprint03.py`).
- `npm run typecheck` and `npm run build` (frontend) both clean.
- **Live browser pass** (Playwright against the electron-vite renderer dev server, `localhost:5173`): created a client/assessment; ingested `/workspace/demo-source/ABAP` (5 files) via Step 1; opened Step 3 — it auto-detected the ingestion with no path input, showed "Desatualizado", started processing (scan/parse/detect_dependencies all completed, no re-scan); Technical View showed the 4 parsed objects (2 classes, 1 function module, 1 report), read-only, no Parse button; ingested `/workspace/demo-source/DDIC` (2 files, a different directory) via Step 1 again; Step 3 auto-switched to the new ingestion and showed "Desatualizado" again; reprocessed; banner cleared, button relabeled "Reprocessar"; Technical View then showed **only** the 2 DDIC objects — the earlier ABAP objects were correctly excluded, confirming invalidation works end to end.

## Known deferrals / backlog
- ATC import remains standalone, not wrapped as a pipeline stage — see `BACKLOG.md` BL-002. Untouched by this sprint (ADR-016).
- Future AI-processing stages (SPRINT-08+) should register with the same `StageDefinition`/`PipelineRun` engine rather than build a parallel mechanism — see BL-003.
- **BL-004 (new)**: reprocessing Step 3 recreates `SAPObject` rows per `source_file_id`, which can break `ATCFinding.correlated_object_id`. Out of scope for this sprint (ATC untouched); needs a human decision on stable object identity or a re-correlation pass.

## Next sprint
SPRINT-08: **AI Object Understanding** — slug `ai-object-understanding`. Not started. Its first planned capability (`AIProvider` abstraction with Bedrock/Azure Foundry adapters) will need real provider credentials — none are configured anywhere in this repo today (no `.env`, no AWS/Bedrock fields in `settings.py` or `compose.yml`); this must be sourced from the user before that work can be validated end to end.

## Restart instructions
Run `/clean-core-run-sprint` to start SPRINT-08.
