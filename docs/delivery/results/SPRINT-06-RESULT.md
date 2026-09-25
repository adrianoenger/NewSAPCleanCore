# SPRINT-06 Result — Durable Pipeline Execution

**Status:** Completed
**Completed at:** 2026-09-25
**Official commit:** resolve from Git history using `feat(sprint-06): complete durable pipeline execution`

## Delivered increment

A durable, resumable processing pipeline (ADR-005) that decomposes long-running work into persisted `PipelineRun` / `StageRun` / `WorkItem` rows in PostgreSQL. It wraps the already-available deterministic scan → parse → detect-dependencies capabilities as work-item-driven stages, without changing their domain contracts (same `SourceScan`/`SourceFile`/`SAPObject`/`SAPObjectDependency` models, same `classifier`/`dispatcher`/`dependency_detector` functions). Supports cooperative pause/resume, bounded per-item automatic retry plus manual retry of a failed item, and automatic recovery of work orphaned by an unclean backend shutdown. A new frontend panel ("Pipeline de Processamento") exposes stage progress, pause/resume controls, and failed-item retry.

## Demonstration path

1. Open the application; select or create a client and an assessment.
2. Navigate to **Pipeline de Processamento**, select a source directory, and click **Iniciar Pipeline**.
3. Observe per-stage progress bars (Scan de Arquivos → Parsing de Objetos → Detecção de Dependências) updating live.
4. Click **Pausar** mid-run; the run and current stage show `Pausado`, and processing stops before the next item/stage.
5. Restart the backend (`docker compose kill -s SIGKILL backend && docker compose up -d backend`) while a run is `running`: on startup, orphaned work items/stages are requeued and the run surfaces as `Pausado`/resumable, not stuck.
6. Click **Retomar**; processing continues from where it left off (no reprocessing of already-completed items).
7. If an item fails (e.g. a source file becomes unreadable), it appears under "Itens com falha" with its error; click **Retry**, then **Retomar** again to reach `Concluído`.

## Minimal validation executed

- [x] 68/68 pytest pass (`test_sprint06.py`'s 12 tests + all prior suites; `test_foundation.py` health-contract literal bumped to `0007_durable_pipeline_execution`).
- [x] TypeScript typecheck and `npm run build` clean.
- [x] Alembic migration 0007 (`pipeline_run`, `stage_run`, `work_item`) applies cleanly from 0006; `/health` reports the new revision.
- [x] Primary demonstrable flow reproduced live via the API (curl) against a synthetic 3000-file dataset: start → pause mid-scan → resume → `SIGKILL` the backend mid-scan → restart → orphan recovery → resume → full completion with real `SAPObject`/`SAPObjectDependency` rows.
- [x] Primary demonstrable flow reproduced live in a real browser (Playwright against the electron-vite renderer): start → pause → resume → deliberately failed item → Retry → resume → completion (801/801 across all 3 stages).

## Key implementation notes

- `backend/alembic/versions/0007_durable_pipeline_execution.py` — 3 new tables with FKs/indexes.
- `backend/src/persistence/models.py` — `PipelineRun`, `StageRun`, `WorkItem` ORM models + status enums; `Assessment.pipeline_runs` relationship.
- `backend/src/pipeline/stages.py` — `StageDefinition`s for `scan`/`parse`/`detect_dependencies`, each `prepare`/`process_item`/(`finalize`) wrapping the existing capability. `detect_dependencies` is scoped to the current run's own scan (`SourceFile.scan_id == run.source_scan_id`), matching `parse`'s scoping — fixed during this sprint after a live UI test exposed a cross-run scoping bug (see below).
- `backend/src/pipeline/engine.py` — `create_pipeline_run`, `run_pipeline` (DAG-ordered stage advancement, cooperative pause, SAVEPOINT-scoped bounded retry), `recover_orphans` (startup requeue).
- `backend/src/api/routes/pipeline.py` + `api/schemas/pipeline.py` — start/list/detail/work-items/pause/resume/retry-item endpoints. Reuses `ingestion._validate_scan_path`.
- `backend/src/api/main.py` — `lifespan` context manager (replacing the deprecated `on_event`) runs `recover_orphans` at startup.
- `frontend/src/renderer/src/components/pipeline/PipelineRunner.tsx` — new panel; `lib/api.ts` — pipeline types/fetchers; `Sidebar.tsx`/`Workspace.tsx` — new nav item. `SourceIngestion.tsx` (manual single-stage scan) is untouched; both flows coexist.

### Bugs found and fixed via live testing (not just automated tests)
1. `PipelineRunner.tsx`: `runsQuery.refetchInterval` didn't poll a freshly-created `pending` run (only polled on `running`), leaving the panel stuck on stale zeros. Fixed to poll on `pending` too.
2. `PipelineRunner.tsx`: the `activeRunId` auto-select effect raced the query cache and silently reverted the active run back to a previous one right after starting a new run. Fixed to only auto-select a default when `activeRunId` is `null`.
3. `pipeline/stages.py`: `_dependencies_prepare` scoped objects by `assessment_id` instead of the current run's scan, so a second pipeline run would reprocess every object ever parsed for the assessment — including ones from an earlier, possibly-deleted scan — and fail unrelated items. Fixed to scope via the run's `source_scan_id`; regression test `test_second_pipeline_run_dependencies_stage_ignores_other_scans` added.

These were caught specifically because `/clean-core-review-sprint`'s first pass returned `READY_TO_FINISH: NO` (CAP-006 had not been run in a real browser; the retry endpoint's success path had no reliable evidence) — the follow-up live browser pass surfaced all three issues, which would not have been visible from typecheck/build/pytest alone.

## Known limitations

- ATC import remains a standalone upload-triggered action, not wrapped as a pipeline stage (no natural per-run work-item decomposition for a user-supplied file today) — `BACKLOG.md` BL-002.
- Future AI-processing stages (SPRINT-07+) should register with this same engine rather than build a parallel mechanism — `BACKLOG.md` BL-003.
- Bounded retry is fixed at `max_attempts=3` per work item; not yet configurable per stage.

## Deferred items

- BL-002: wrap ATC import as an optional pipeline stage.
- BL-003: wrap future AI-processing stages (SPRINT-07+) in the same engine.

## Repository closure

- Sprint branch: `sprint/06-durable-pipeline-execution`
- Official commit message: `feat(sprint-06): complete durable pipeline execution`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
