# SPRINT-03 Result — SAP Object Parsing

**Status:** Completed  
**Completed at:** 2026-09-24  
**Official commit:** resolve from Git history using `feat(sprint-03): complete sap object parsing`

## Delivered increment
ABAP and DDIC parsers that extract named SAP objects (classes, function modules, programs, tables, domains) from classified source files. Results are persisted as `SAPObject` entities in PostgreSQL, exposed via REST API, and browsable in the desktop app via the `ObjectBrowser` frontend component.

## Demonstration path
1. Open the Electron app (`npm run dev` in `frontend/`).
2. Navigate to the Engineering tab in the Workspace.
3. Observe the ObjectBrowser listing 6 SAP objects (2 classes, 2 function modules, 1 program, 1 table) for the Acme / Clean Core PoC Assessment.
4. Alternatively, call `GET http://localhost:8000/assessments/82/objects` for the JSON representation.
5. Call `GET http://localhost:8000/health` — confirms `migration_revision: 0004_sap_object_parsing`.

## Minimal validation executed
- [x] `pytest tests/` — 35/35 passed (unit tests for all parsers + API contracts).
- [x] TypeScript `npx tsc --noEmit` — 0 errors.
- [x] Health smoke: `GET /health` returns `migration_revision: 0004_sap_object_parsing`, pgvector ok.
- [x] API smoke: `GET /assessments/82/objects` returns 6 SAP objects with correct types and names.
- [x] Alembic migration `0004_sap_object_parsing` applied from clean migration baseline.
- [x] Seed v5 re-applied; 2 clients, 2 assessments, 1 scan, 9 source files, 6 SAP objects persisted.

## Key implementation notes
- `backend/src/parsing/` — dispatcher + 4 parser modules (abap_class, abap_function, abap_program, ddic).
- `backend/src/parsing/models.py` — `ParsedObject` dataclass (object_type, object_name, attributes, line_start/end).
- `backend/alembic/versions/0004_sap_object_parsing.py` — adds `sap_object` table.
- `backend/src/persistence/models.py` — `SAPObject` ORM model added.
- `backend/src/api/routes/parsing.py` + `schemas/parsing.py` — trigger-parse, list-objects, object-detail endpoints.
- `backend/src/seed/registry.py` — seed v5 adds `_seed_demo_sap_objects` step; auto-parses demo-source on seed.
- `frontend/src/renderer/src/components/parsing/ObjectBrowser.tsx` — browse SAP objects by type/name.
- `frontend/src/renderer/src/components/shell/Workspace.tsx` — ObjectBrowser wired into engineering view.

## Known limitations
- `SAPObject` is scoped to `assessment_id` but the parsing trigger currently requires a completed scan to be present (seed-driven for demo).
- Parsers use regex heuristics; complex ABAP patterns with non-standard spacing may not extract cleanly.
- `ObjectBrowser` shows all objects flat; filtering and detail view belong to a later sprint.
- Seed uses `with factory() as session:` context manager which may not commit under some script invocations — workaround: use explicit session without context manager or call via API.

## Deferred items
- Test isolation: pytest wipes seed data; `seed_run` metadata stale after tests. Tracked as SPRINT-04 pre-condition: apply seed after pytest run or use a separate test database. (Previously noted in `project_test_isolation.md`.)
- `SAPSystem` entity and `Client → SAPSystem → Assessment` hierarchy remain; removal deferred to SPRINT-04.
- Assessment-centric navigation and new app shell (SPRINT-04).
- ATC import and ATCFinding model (SPRINT-05).

## Repository closure
- Sprint branch: `sprint/03-sap-object-parsing`
- Official commit message: `feat(sprint-03): complete sap object parsing`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
