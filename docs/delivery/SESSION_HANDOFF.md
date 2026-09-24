# Session Handoff

## Current state
SPRINT-00 (Engineering Foundation) is **completed** — see `docs/delivery/results/SPRINT-00-RESULT.md`. The official commit is on `main` (derive the hash from Git history: `feat(sprint-00): complete engineering foundation`).

Next sprint: **SPRINT-01 — Client, SAP System and Assessment**, ready but **not started**. Canonical branch: `sprint/01-client-sap-system-and-assessment`.

## Foundation available to SPRINT-01
- `docker compose up -d --build` → postgres (pgvector) + backend; Alembic migrations applied on backend start (head `0001_foundation`).
- Add domain models in `backend/src/persistence/models.py` and a new Alembic revision (`alembic revision --autogenerate`).
- Extend the synthetic seed by adding steps to the `demo` dataset in `backend/src/seed/registry.py` and bumping its version.
- Desktop shell: `cd frontend && npm run dev`; smoke: `npm run smoke` (backend must be running).
- Node.js is at `C:\Program Files\nodejs` (add to PATH in Git Bash if missing); Docker Desktop must be running.

## Open backlog
- BL-001 — duplicate root `gitignore` file.

## Git lifecycle
- One official commit is allowed per sprint and is created only by `/clean-core-finish-sprint`.
- Lifecycle amended 2026-09-24 (ADR-013): run-sprint syncs `main` and creates the sprint branch; finish commits, pushes the sprint branch, fast-forwards and pushes `main`, deletes the local sprint branch and updates local `main`.
- SPRINT-00 commit `feat(sprint-00): complete engineering foundation` was created before this amendment and was not pushed.

## Restart instruction
1. read `CLAUDE.md`;
2. read `docs/delivery/IMPLEMENTATION_BASELINE.md`;
3. read `docs/delivery/sprint-execution-model.md`;
4. read `EXECUTION_STATE.yaml`;
5. run `/clean-core-run-sprint` to initialize SPRINT-01 from a clean `main`;
6. do not create intermediate Git commits.

## Important
The legacy source package is reference material only. Do not copy its secrets or treat its notebooks as the target runtime architecture. New ideas outside current sprint scope belong in `BACKLOG.md`.
