# SPRINT-04 — Assessment-Centric Product Alignment

## Goal
Correct the already-implemented product hierarchy and application shell before adding more Clean Core analysis capabilities.

## Why this sprint exists
Sprints 01–03 implemented valuable persistence, ingestion and parsing capabilities, but Sprint 01 introduced `Client → SAPSystem → Assessment` and a three-column Client Hub. Product review replaced that model with `Client → Assessment`, where `sap_source_system` is Assessment metadata. Source Ingestion also currently exposes/defaults path configuration that must no longer become a preselected user path.

This sprint is a corrective migration, not a rewrite of working ingestion/parsing behavior.

## Planned capabilities
### Domain/persistence correction
- Remove `SAPSystem` from canonical ORM/domain/API contracts.
- Add direct `Assessment.client_id` and `Assessment.sap_source_system`.
- Create a forward Alembic migration that backfills existing data from `sap_system` before removing obsolete relationships/table.
- Preserve existing source scans/files/SAP objects by Assessment where practical.
- Update synthetic seed data to Client → Assessment.

### API correction
- Provide CRUD-light Client endpoints.
- Provide Assessment list/create/detail endpoints without nested SAP System routes.
- Assessment listing supports Client/name filters and exposes status/source-system metadata needed by the home grid.

### Assessments Home
- Make the first application screen a grid/list of all Assessments.
- Add filters by Client and Assessment.
- Add `Novo Assessment` and `Novo Cliente` flows.
- No left sidebar on this screen.
- Keep permanent right-side Copilot.

### Assessment workspace shell
- Render left sidebar only when an Assessment is active.
- Show Client / Assessment context.
- Replace top-level navigation with:
  - `1 - Ingestão dos dados`
  - `2 - Análise ATC`
  - `3 - Processamento por IA`
  - Dashboard Geral
  - Executive View
  - Technical View
  - Functional View
  - Architecture View
- ATC/AI/result screens may initially be placeholders when their underlying capability belongs to later sprints, but routes/navigation must be coherent.

### Source Ingestion correction
- Start with source path blank.
- `Start Scan` disabled until a directory is explicitly selected and valid.
- No `demo_path` or backend scan root is used as a pre-populated user selection.
- Existing scan history may remain visible.

### Existing parsing integration
- Keep the ObjectBrowser capability produced in Sprint 03 accessible from the appropriate Technical context without regressing parsing contracts.

## Demonstrable outcome
Launch the desktop app and see Assessments Home with no left sidebar and the Copilot on the right. Create/filter/open an Assessment directly under a Client. Once opened, see the Assessment sidebar. In Source Ingestion, the directory field is blank and Start Scan is disabled until Browse selects a directory. Existing scan/parsing data remain Assessment-scoped and usable.

## Minimal validation
- Forward migration succeeds against the current schema created by Sprints 01–03.
- Existing synthetic Assessment data are preserved/backfilled or reproducibly reseeded with documented behavior.
- Client/Assessment API critical contracts pass.
- Home grid and create/open Assessment smoke flow passes.
- Sidebar absent on home and present inside Assessment.
- Source path blank + Start Scan disabled before selection.
- Existing ingestion and object parsing critical flows still pass.
- Typecheck/smoke tests remain lean; do not expand into broad coverage.

## Completion criteria
- No canonical runtime dependency on independent `SAPSystem` remains.
- No user-facing three-column Client → System → Assessment selector remains.
- Documentation/progress/handoff reflect the migration outcome.
- Application remains runnable for Sprint 05.
