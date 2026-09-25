> **HISTORICAL RESULT NOTICE (2026-09-24):** This is an accurate record of what Sprint 01 implemented. Its `SAPSystem` hierarchy is intentionally superseded by ADR-015 / Baseline R3.2 and will be corrected in Sprint 04. Do not reinterpret this result file as current architecture.

# SPRINT-01 Result — Client, SAP System and Assessment

**Status:** Completed  
**Completed at:** 2026-09-24  
**Official commit:** resolve from Git history using `feat(sprint-01): complete client system assessment`

## Delivered increment
Core navigation hierarchy: `Client`, `SAPSystem` and `Assessment` are persisted in PostgreSQL via SQLAlchemy/Alembic (migration `0002_client_system_assessment`). A CRUD-light FastAPI router (`/clients`) exposes creation and listing for all three entities with Pydantic-validated schemas. The demo seed was extended to v2 with one synthetic Client (Acme Industries), SAP System (S/4HANA Development / SID S4D) and Assessment (Clean Core PoC Assessment). The Electron desktop shell now opens to a Client Hub — a three-column selector (Client → SAP System → Assessment) that loads from the live API and updates a breadcrumb context bar in both the Workspace top bar and the Sidebar footer. The Copilot context label also reflects the active selection.

## Demonstration path
1. `docker compose up -d --build` — applies Alembic migrations to head `0002_client_system_assessment`; backend starts healthy.
2. `docker compose exec backend python -m seed apply` — inserts Acme Industries / S/4HANA Development / Clean Core PoC Assessment.
3. `cd frontend && npm run dev` — Electron shell opens to Client Hub showing the seeded client.
4. Click **Acme Industries** → **S/4HANA Development** → **Clean Core PoC Assessment** — breadcrumb updates in top bar and Sidebar footer; Copilot label switches to `assessment: Clean Core PoC Assessment`.
5. Reopen the app at any time: the API still returns the persisted context; re-select to resume navigation.

## Minimal validation executed
- [x] Startup/smoke checks — `npm run smoke` 5/5 PASS (sidebar, workspace, copilot, backend online, client hub rendered).
- [x] Critical contracts — `pytest -q` 8/8 passed: 3 foundation checks updated for revision `0002`; 5 new SPRINT-01 API contract tests (client create/list, system create/list, assessment create/list, 404 on missing client, wrong-client system isolation).
- [x] Primary demonstrable user flow — Client Hub loads seed data; three-step selection updates context in real time.
- [x] Integration — `/health` reports `migration_revision: 0002_client_system_assessment`; all API endpoints return correct status codes and Pydantic-validated payloads.
- [x] Migration applicability — `alembic downgrade base → upgrade head → alembic check`: no drift; round-trip clean.

## Key implementation notes
- `backend/src/persistence/models.py`: added `Client`, `SAPSystem`, `Assessment` ORM models with cascading FK deletes; `AssessmentStatus` enum.
- `backend/alembic/versions/0002_client_system_assessment.py`: creates `client`, `sap_system`, `assessment` tables with indexed FK columns.
- `backend/src/api/schemas/client_system_assessment.py`: Pydantic `Create` + `Read` schemas for all three entities.
- `backend/src/api/routes/clients.py`: nested REST router — `POST/GET /clients`, `POST/GET /clients/{id}/systems`, `POST/GET/GET-one /clients/{id}/systems/{id}/assessments`.
- `backend/src/api/main.py`: registered `clients_router`.
- `backend/src/seed/registry.py`: demo dataset bumped to v2 with `_seed_demo_client_system_assessment` step.
- `backend/tests/test_sprint01.py`: 5 new contract tests; `test_foundation.py` updated for schema revision `0002`.
- `frontend/src/renderer/src/components/hub/ClientHub.tsx`: three-column selector with TanStack Query, cascading clear on selection change, status badge for assessment.
- `frontend/src/renderer/src/lib/api.ts`: added `ClientRecord`, `SAPSystemRecord`, `AssessmentRecord` types and `fetchClients`, `fetchSystems`, `fetchAssessments` fetchers.
- `frontend/src/renderer/src/lib/useClientContext.ts`: `ClientContext` interface for typed prop drilling.
- `frontend/src/renderer/src/App.tsx`: selection state managed at root with cascading clear.
- `frontend/src/renderer/src/components/shell/Sidebar.tsx`: footer reflects selected context.
- `frontend/src/renderer/src/components/shell/Workspace.tsx`: top bar breadcrumb; Client Hub mounted when no assessment selected.
- `frontend/scripts/smoke.mjs`: updated to check for Client Hub heading (health card is now behind assessment selection).

## Known limitations
- Selection state is React-volatile: closing the app clears the selection; re-select on next launch (data remains in DB). Persistent "last context" can go to backlog.
- `selectinload` is imported but unused in `routes/clients.py` — cosmetic, no functional impact.
- `test_sprint01.py` cleanup uses raw `DELETE` which leaves `seed_run.version` intact; a fresh `python -m seed apply` after tests requires `alembic downgrade base && alembic upgrade head` first (the standard demo reset path always works).

## Deferred items
- BL-001 — remove duplicate root `gitignore` file (open from SPRINT-00).

## Repository closure
- Sprint branch: `sprint/01-client-sap-system-and-assessment`
- Official commit message: `feat(sprint-01): complete client system assessment`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
