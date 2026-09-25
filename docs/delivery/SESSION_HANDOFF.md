# Session Handoff

## Current state
SPRINT-06 (Durable Pipeline Execution) is **completed** on branch `main`.

## What was delivered

### Backend
- **Alembic 0007**: new tables `pipeline_run`, `stage_run`, `work_item` (ADR-005).
- **`persistence/models.py`**: `PipelineRun`, `StageRun`, `WorkItem` ORM models + `PipelineRunStatus`/`StageRunStatus`/`WorkItemStatus` enums. `Assessment.pipeline_runs` relationship added.
- **`pipeline/stages.py`**: stage definitions (`scan`, `parse`, `detect_dependencies`) that wrap the existing `ingestion.classifier.classify`, `parsing.dispatcher.parse_file`, and `parsing.dependency_detector.detect_dependencies` as work-item-driven handlers — their signatures and the SourceScan/SourceFile/SAPObject/SAPObjectDependency domain contracts are unchanged.
- **`pipeline/engine.py`**: orchestrator —
  - `create_pipeline_run`: creates a PipelineRun with one StageRun per stage in DAG dependency order.
  - `run_pipeline`: advances stages one work item at a time; cooperative pause (checked before each item and between stages); bounded automatic retry (`WorkItem.max_attempts`, default 3) using SAVEPOINT-scoped attempts so a failed item doesn't corrupt sibling state.
  - `recover_orphans`: called from the FastAPI lifespan on startup — requeues WorkItem/StageRun rows stuck in `running` (from an unclean shutdown) to `pending`, and marks any `running` PipelineRun as `paused` (`pause_requested=true`) so a human must explicitly resume it.
- **`api/routes/pipeline.py`** + **`api/schemas/pipeline.py`**: `POST/GET /assessments/{id}/pipeline-runs`, `GET .../pipeline-runs/{run_id}`, `GET .../work-items` (filter by stage_key/status), `POST .../pause`, `POST .../resume`, `POST .../work-items/{item_id}/retry`. Reuses `ingestion._validate_scan_path` for the same symlink-escape-safe path validation as the existing scan endpoint.
- **`api/main.py`**: switched to a `lifespan` context manager (from the deprecated `on_event`) that runs `recover_orphans` at startup.
- **`backend/tests/test_sprint06.py`**: 12 tests — orphan recovery, full run wrapping all 3 stages with real dependency detection, cross-run scoping regression, cooperative pause+resume, bounded retry + manual retry-then-resume, and API contract checks (start/list/detail, pause/retry 409 guards, and the retry endpoint's real success path followed by resume-to-completion). `test_foundation.py`'s health-contract literal bumped to `0007_durable_pipeline_execution` (existing per-sprint convention).

### Frontend
- **`components/pipeline/PipelineRunner.tsx`**: new panel — directory picker (reuses the Electron `selectDirectory`/host-path-mapping pattern from `SourceIngestion`), start pipeline, per-stage progress bars (scan/parse/detect_dependencies) with completed/total/failed counts, pause/resume controls, failed-work-item list with per-item retry, and run history.
- **`lib/api.ts`**: `PipelineRunRecord`/`StageRunRecord`/`WorkItemRecord` types + `startPipelineRun`/`fetchPipelineRuns`/`fetchPipelineRun`/`fetchPipelineWorkItems`/`pausePipelineRun`/`resumePipelineRun`/`retryWorkItem` fetchers.
- **`components/shell/Sidebar.tsx`** / **`Workspace.tsx`**: new nav item "Pipeline de Processamento" (id `pipeline`) rendering `PipelineRunner`. `SourceIngestion` (manual single-stage scan) is untouched — both flows coexist.

## Validation performed
- `docker compose exec backend pytest -q` → **68/68 passed**.
- `alembic upgrade head` applied cleanly (0006 → 0007); `/health` reports `migration_revision: "0007_durable_pipeline_execution"`.
- `npm run typecheck` and `npm run build` (frontend) both clean.
- **Live API smoke test** (curl) against a synthetic 3000-file dataset: started a pipeline run, paused it cooperatively mid-scan (250/3000), resumed, then `docker compose kill -s SIGKILL backend` mid-scan again (961/3000) to simulate a crash, restarted the backend, confirmed orphan recovery surfaced the run as `paused`/resumable with progress intact (no reprocessing), resumed, and watched all 3 stages complete with real `SAPObject`/`SAPObjectDependency` rows persisted.
- **Live browser smoke test** (Playwright against the electron-vite renderer dev server, `localhost:5173`): created a client/assessment, opened the new "Pipeline de Processamento" nav item, started a run, clicked **Pausar** mid-scan, clicked **Retomar**, deliberately broke a not-yet-processed file so the parse stage failed one item, clicked **Retry** in the failed-items panel, clicked **Retomar** again, and watched the run reach `Concluído` (801/801 across all 3 stages) with the failed-items panel clearing. This first pass surfaced two real UI bugs (see below), both fixed and re-verified live before closure.

### Bugs found and fixed during the live browser pass
1. **`PipelineRunner.tsx` — `runsQuery.refetchInterval` never polled a freshly-started run.** The predicate only kept polling while a run's status was `'running'`; immediately after `POST .../pipeline-runs` the run is still `'pending'` (the background task hasn't flipped it yet), so if that first snapshot landed on `'pending'` the interval evaluated to `false` and polling never started, leaving the panel stuck showing stale zeros. Fixed to also poll while `'pending'`.
2. **`PipelineRunner.tsx` — the `activeRunId` auto-select effect raced the query cache and silently reverted to the previous run.** After `handleStart` called `setActiveRunId(newRun.id)`, a re-render on the *stale* (pre-refetch) query cache — which didn't yet contain the new run — tripped the effect's fallback ("if the current id isn't in the list, pick `runs[0]`") and reset `activeRunId` back to the old run; a later render with the fresh cache then saw the (wrong) id was valid and never corrected it. Fixed by only auto-selecting a default when `activeRunId` is `null` (first load), never as a fallback afterward.
3. **`pipeline/stages.py` — `_dependencies_prepare` scoped objects by `assessment_id` instead of the current run's own scan.** A *second* pipeline run for the same assessment would enumerate every `SAPObject` ever parsed for that assessment — including ones from an earlier, unrelated scan — so if that earlier scan's source directory had since been deleted or moved, this run's `detect_dependencies` stage failed items that had nothing to do with it. Fixed to scope via `SourceFile.scan_id == run.source_scan_id`, matching `_parse_prepare`'s existing (correct) scoping. Regression test: `test_second_pipeline_run_dependencies_stage_ignores_other_scans`.

`clean-core-review-sprint`'s first pass returned `READY_TO_FINISH: NO` specifically because CAP-006 had not been run in a real browser and the retry endpoint's success path had no reliable evidence — both gaps are what this pass closed. `test_retry_endpoint_success_path_then_resume_completes` now also exercises the real `POST .../work-items/{id}/retry` and `POST .../resume` HTTP routes end to end (not just the engine).

## Known deferrals / backlog
- ATC import remains a standalone upload-triggered action, not wrapped as a pipeline stage (needs a per-run file; no natural work-item decomposition yet) — see `BACKLOG.md` BL-002.
- Future AI-processing stages (SPRINT-07+) should register with the same `StageDefinition`/`PipelineRun` engine rather than build a parallel mechanism — see BL-003.

## Next sprint
SPRINT-07: **AI Object Understanding** — slug `ai-object-understanding`.

## Restart instructions
Run `/clean-core-run-sprint` to start SPRINT-07.
