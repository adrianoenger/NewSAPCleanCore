# Session Handoff

## Current state
SPRINT-03 (SAP Object Parsing) is **completed** — officially closed by `/clean-core-finish-sprint` on 2026-09-24. All capabilities implemented: ABAP/DDIC parsers, SAPObject model + migration 0004, API routes, ObjectBrowser frontend, seed v5 (6 SAP objects).

The product baseline is R3.1 / ADR-015 (2026-09-24). The next sprint is **SPRINT-04 — Assessment-Centric Product Alignment**, canonical branch `sprint/04-assessment-centric-product-alignment`.

Do **not** start the old Dependencies/ATC scope as Sprint 04. That work moved to Sprint 05.

## Working implementation available from Sprints 00–03
- Docker Compose PostgreSQL/pgvector + FastAPI foundation and Alembic migrations (through 0004).
- Electron + React shell with permanent right-side Copilot region.
- Client → SAPSystem → Assessment persistence/API/frontend selector from Sprint 01 (to be corrected by Sprint 04).
- Source scanning/classification from Sprint 02.
- SAP object parsing and ObjectBrowser from Sprint 03.
- `GET /assessments/{id}/objects` and object-detail APIs.
- Scan/parse flows scoped to Assessment.
- Seed v5 applied: 2 clients, 2 assessments, 1 scan, 9 source files, 6 SAP objects.

## Restart instruction
1. Read `CLAUDE.md`.
2. Read `docs/delivery/IMPLEMENTATION_BASELINE.md`.
3. Read `docs/adr/015-assessment-centric-workspace.md`.
4. Read `docs/delivery/EXECUTION_STATE.yaml`.
5. Start SPRINT-04 using `/clean-core-run-sprint`.

## Known divergence that Sprint 04 must correct
Current code still reflects the old model:
- `SAPSystem` ORM/table/entity;
- nested Client → System → Assessment APIs;
- three-column Client Hub;
- Client/System/Assessment frontend context;
- seed datasets based on SAPSystem;
- Source Ingestion configuration currently exposes `scan_root`/`demo_path` behavior and has historically used defaults.

Target model is now:

```text
Client 1 ───── N Assessment
Assessment.sap_source_system
```

The first screen must be Assessments Home (grid/list, filters, Novo Assessment/Novo Cliente), with no left sidebar. The sidebar appears only after an Assessment is opened. Copilot remains on the right at all times.

## Sprint 04 migration rule
Do not rewrite old Alembic migrations. Add a new forward migration that backfills Client and SAP source-system data into Assessment before removing obsolete relationships/table. Preserve Assessment-owned scans/files/objects where practical.

## Source Ingestion correction
- directory field blank initially;
- no default user path;
- Start Scan disabled until explicit valid selection;
- no automatic scan on directory selection.

## Restart instruction
1. Read `CLAUDE.md`.
2. Read `docs/delivery/IMPLEMENTATION_BASELINE.md`.
3. Read ADR-015.
4. Read `docs/delivery/EXECUTION_STATE.yaml`.
5. Review/finish SPRINT-03 if appropriate using the canonical lifecycle.
6. Start SPRINT-04 only after Sprint 03 is formally closed.

## Important
The result files for Sprints 01 and 02 are historical implementation records. Where they conflict with R3/ADR-015, the new baseline wins.
