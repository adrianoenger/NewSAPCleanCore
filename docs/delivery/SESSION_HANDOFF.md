# Session Handoff

## Current state
SPRINT-01 (Client, SAP System and Assessment) is **completed** — see `docs/delivery/results/SPRINT-01-RESULT.md`. Official commit: derive from Git history using `feat(sprint-01): complete client system assessment`.

Next sprint: **SPRINT-02 — Source Ingestion**, ready but **not started**. Canonical branch: `sprint/02-source-ingestion`.

## Foundation available to SPRINT-02
- `docker compose up -d --build` → postgres (pgvector) + backend; Alembic migrations applied on backend start (head `0002_client_system_assessment`).
- `docker compose exec backend python -m seed apply` → seeds Acme Industries / S/4HANA Development (S4D) / Clean Core PoC Assessment.
- Add domain models in `backend/src/persistence/models.py` and a new Alembic revision (`alembic revision --autogenerate`).
- Extend the synthetic seed by adding steps to the `demo` dataset in `backend/src/seed/registry.py` and bumping its version.
- Desktop shell: `cd frontend && npm run dev`; tests: `docker compose exec backend pytest -q` (8 pass); smoke: `cd frontend && npm run smoke` (backend must be running).
- Client Hub is the entry point: select Acme Industries → S/4HANA Development → Clean Core PoC Assessment to activate the context for SPRINT-02 views.
- Node.js is at `C:\Program Files\nodejs` (add to PATH in Git Bash if missing); Docker Desktop must be running.

## Open backlog
- BL-001 — duplicate root `gitignore` file (low priority, admin only).

## Git lifecycle
- One official commit is allowed per sprint and is created only by `/clean-core-finish-sprint`.
- Lifecycle (ADR-013, 2026-09-24): run-sprint syncs `main` and creates the sprint branch; finish commits, pushes the sprint branch, fast-forwards and pushes `main`, deletes the local sprint branch and updates local `main`.

## Restart instruction
1. Read `CLAUDE.md`;
2. Read `docs/delivery/IMPLEMENTATION_BASELINE.md`;
3. Read `docs/delivery/sprint-execution-model.md`;
4. Read `EXECUTION_STATE.yaml`;
5. Run `/clean-core-run-sprint` to initialize SPRINT-02 from a clean `main`;
6. Do not create intermediate Git commits.

## Important
The legacy source package is reference material only. Do not copy its secrets or treat its notebooks as the target runtime architecture. New ideas outside current sprint scope belong in `BACKLOG.md`.
