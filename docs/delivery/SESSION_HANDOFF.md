# Session Handoff

## Current state
SPRINT-02 (Source Ingestion) is **completed** — official commit on `main`. Working tree is clean, local sprint branch removed.

Next sprint: **SPRINT-03 — SAP Object Parsing**, not started. Canonical branch: `sprint/03-sap-object-parsing`.

## Foundation available to SPRINT-03
- `docker compose up -d --build` → postgres (pgvector) + backend; Alembic migrations applied on backend start (head `0003_source_ingestion`).
- `docker compose exec backend python -m seed apply` → seeds Acme/S4D/Assessment (with demo scan, 9 files) + Rodobens/ECC/Assessment01 (no scan, for full-flow testing).
- After running `pytest`, re-seed is needed: `DELETE FROM seed_run` then `python -m seed apply`.
- `GET /assessments/{id}/scans` → list scans; `GET /assessments/{id}/scans/{id}` → scan detail with category counts; `GET /assessments/{id}/source-files` → file inventory.
- `POST /assessments/{id}/scans` → start new scan (`{source_path: string}`); resumes interrupted scans automatically.
- Desktop shell: `cd frontend && npm run dev`; tests: `docker compose exec backend pytest -q` (22 pass).
- Client Hub → select Rodobens/ECC/Assessment01 → SourceIngestion view (empty, ready for scanning).

## SPRINT-02 deliverables
- `demo-source/` — 9 synthetic SAP files (ABAP classes, FMs, DDIC, config, docs)
- `backend/src/ingestion/classifier.py` — extension-based file classifier (7 categories, .html→abap_source)
- `backend/src/ingestion/scanner.py` — synchronous directory scanner with SHA-256, batch commit, resume
- `backend/src/api/routes/ingestion.py` — scan lifecycle + file inventory API with path traversal protection
- `backend/src/api/schemas/ingestion.py` — Pydantic schemas
- `backend/alembic/versions/0003_source_ingestion.py` — source_scan + source_file tables
- `frontend/src/renderer/src/components/ingestion/SourceIngestion.tsx` — full scan UI with real-time progress
- Electron IPC: `dialog:selectDirectory` + `app:getProjectRoot` for host→container path mapping

## Known limitation for SPRINT-03
- Test isolation: `pytest` clears the real database. After running tests, re-seed manually. File content not yet read (extension-only classification). SPRINT-03 will parse file content to extract SAP objects.

## Open backlog
- BL-001 — duplicate root `gitignore` file (low priority, admin only).

## Git lifecycle
- One official commit per sprint, created only by `/clean-core-finish-sprint`.
- Lifecycle: run-sprint syncs `main` and creates the sprint branch; finish commits, pushes the sprint branch, fast-forwards and pushes `main`, deletes the local sprint branch.

## Restart instruction
1. Read `CLAUDE.md`;
2. Read `docs/delivery/IMPLEMENTATION_BASELINE.md`;
3. Read `docs/delivery/sprint-execution-model.md`;
4. Read `EXECUTION_STATE.yaml`;
5. Run `/clean-core-run-sprint` (will start SPRINT-03 from `main`).
6. Do not create intermediate Git commits.

## Important
The legacy source package is reference material only. Do not copy its secrets or treat its notebooks as the target runtime architecture. New ideas outside current sprint scope belong in `BACKLOG.md`.
