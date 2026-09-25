# SPRINT-00 Result — Engineering Foundation

**Status:** Completed  
**Completed at:** 2026-09-24  
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Runnable development foundation: Docker Compose stack with PostgreSQL + pgvector and a FastAPI backend (Dev Container ready), SQLAlchemy + Alembic migration baseline, a synthetic idempotent seed mechanism, and an Electron + React + TypeScript desktop shell with the permanent Sidebar | Workspace | AI Copilot layout that renders live backend/database health.

## Demonstration path
1. `docker compose up -d --build` (applies Alembic migrations on backend start).
2. `cd frontend && npm install && npm run dev`.
3. The desktop window shows the left navigation, the center workspace with the "Platform health" card (backend online, database ok, pgvector true, schema revision `0001_foundation`) and the right AI Copilot placeholder, which collapses to a rail and reopens.
4. Optional: `docker compose stop backend` → indicator switches to "Backend offline" within ~5s; `docker compose start backend` restores it.

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint — Compose stack healthy; `npm run smoke` (Electron via CDP) all PASS.
- [x] Critical contracts introduced by the sprint — `pytest -q` 3 passed (`/health` contract, CORS for renderer origin, seed idempotency).
- [x] Primary demonstrable user flow — desktop shell shows three regions and health online (smoke + live demo).
- [x] Required integration checks, if any — backend ↔ PostgreSQL/pgvector via `/health`.
- [x] Migration applicability, if schema changed — `alembic downgrade base && alembic upgrade head && alembic check`: no drift, head `0001_foundation`.

## Key implementation notes
- `compose.yml`, `.devcontainer/devcontainer.json`, `.env.example`.
- `backend/`: `api/main.py`, `api/routes/health.py`, `persistence/` (SQLAlchemy base, `SeedRun`), `alembic/versions/0001_foundation.py` (vector extension + `seed_run`), `seed/` CLI (`python -m seed apply|status`), `tests/test_foundation.py`.
- `frontend/`: electron-vite (main/preload/renderer), React 19, Tailwind v4 with design-system tokens, shadcn-style primitives, TanStack Query health polling, `scripts/smoke.mjs`.
- `.gitignore`: explicit exception for `frontend/src/**/lib/` (generic `lib/` rule hid source).
- README: "Running the application (development)".

## Known limitations
- VS Code "Reopen in Container" not exercised interactively (config validated against the same compose service).
- Renderer CSP allows backend connections only to localhost/127.0.0.1.
- Vite pinned to ^7 (electron-vite 5 peer range); TypeScript pinned to ~5.9.
- MCP compose services deferred to SPRINT-10 per the corrected roadmap.

## Deferred items
- BL-001 — remove duplicate root `gitignore` file.

## Repository closure
- Sprint branch: `sprint/00-engineering-foundation`
- Official commit message: `feat(sprint-00): complete engineering foundation`
- Final branch after closure: `main`
- Local sprint branch removed: yes
- Working tree clean: yes
