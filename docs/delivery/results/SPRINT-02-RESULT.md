> **HISTORICAL UX NOTICE (2026-09-24):** This result records the source-ingestion implementation at Sprint 02. Baseline R3.2 now requires an empty initial source-directory field and Start Scan disabled until explicit valid selection. Sprint 04 performs that UI/config alignment.

# SPRINT-02 Result — Source Ingestion

**Status:** Completed  
**Completed at:** 2026-09-24  
**Official commit:** resolve from Git history — `feat(sprint-02): complete source ingestion`

## Delivered increment

End-to-end source file ingestion pipeline: the user selects a local directory from the Electron app, the backend scans every file under that path, computes SHA-256 per file, classifies each one into one of 7 artifact categories (abap_source, xml_metadata, cds, ddic, configuration, documentation, other), persists results to PostgreSQL, and the UI displays real-time scan progress, a category breakdown chart, and a paginated file inventory. Interrupted scans resume from where they stopped.

## Demonstration path

1. Start the stack: `docker compose up -d` → `cd frontend && npm run dev`
2. In the app, navigate to **Rodobens → ECC 6.0 → Assessment01** (no pre-loaded scan — clean state for testing).
3. Click **Browse**, pick any subdirectory of the project (e.g. `SAP_Files/MASS_ABAP`).
4. Observe the host path and the mapped container path displayed in the UI.
5. Click **Start Scan** — the progress bar increments in real time (polling every 1.5 s); file count and percentage update live.
6. On completion, the category bar chart, category legend, and file inventory table appear.
7. Alternatively, navigate to **Acme Industries → S/4HANA Development → Clean Core PoC Assessment** for the pre-loaded demo scan (9 files, 4 categories).

## Minimal validation executed

- [x] 22/22 pytest pass (`docker compose exec backend pytest -q`)
- [x] TypeScript typecheck clean (`cd frontend && npm run typecheck`)
- [x] Alembic migration at `head` — `0003_source_ingestion` (source_scan + source_file tables)
- [x] Path traversal security: `_validate_scan_path` rejects paths outside `scan_root` (test `test_scan_path_outside_root_rejected`)
- [x] SHA-256 correctness verified in `test_scan_lifecycle`
- [x] 10 parametrized classifier tests cover all 7 categories
- [x] Demonstrated end-to-end: 3 469 HTML files from `SAP_Files/MASS_ABAP` scanned and persisted in ~39 s
- [x] Resume: re-scanning same path reuses existing PENDING/SCANNING scan and skips already-persisted files

## Key implementation notes

- `backend/src/ingestion/classifier.py` — extension-based classifier; `.html`/`.htm` mapped to `abap_source` because SAP ABAPDoc exports embed ABAP code in HTML files
- `backend/src/ingestion/scanner.py` — walks directory, SHA-256, batch commit every 10 files, resume via existing `source_file.rel_path` set
- `backend/src/api/routes/ingestion.py` — two routers (`/assessments`, `/ingestion`); `_validate_scan_path` enforces `scan_root` boundary; background task via `FastAPI BackgroundTasks`
- `backend/alembic/versions/0003_source_ingestion.py` — `source_scan` and `source_file` tables with indexes on `(scan_id, rel_path)`
- `frontend/src/renderer/src/components/ingestion/SourceIngestion.tsx` — TanStack Query 1.5 s polling during active scan; `toContainerPath()` maps Windows host path to Docker container path
- Electron IPC: `dialog:selectDirectory` (native folder picker) + `app:getProjectRoot` (host→container path mapping)
- Seed: `_seed_rodobens_client_system_assessment` adds Rodobens/ECC/Assessment01 with no pre-loaded scan for full-flow testing

## Known limitations

- Test isolation: `pytest` uses the real database; running the test suite clears all scan data. Workaround: `DELETE FROM seed_run` then `python -m seed apply` after test runs. Test database isolation is deferred to a future sprint.
- File content is not read — classification is extension-only. Content parsing is SPRINT-03 scope.
- `source_scan.completed_at` is not set by the seed step (only by the live scanner).

## Deferred items

- No new backlog items created during this sprint.

## Repository closure

- Sprint branch: `sprint/02-source-ingestion`
- Official commit message: `feat(sprint-02): complete source ingestion`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
