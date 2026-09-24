# Claude Code Prompt — Align Existing Code to Baseline R3.1 / ADR-015

Use this prompt only after the updated documentation package has replaced the current `/docs` and root documentation files.

---

Read the current repository documentation before changing code, in this order:

1. `CLAUDE.md`
2. `docs/delivery/IMPLEMENTATION_BASELINE.md`
3. `docs/adr/015-assessment-centric-workspace.md`
4. `docs/delivery/EXECUTION_STATE.yaml`
5. `docs/delivery/SESSION_HANDOFF.md`
6. the active/next sprint file under `docs/delivery/sprints/`

The accepted baseline has changed. Existing code from Sprints 01–03 contains known divergences and must be aligned without discarding working ingestion/parsing capabilities.

## Lifecycle first
SPRINT-03 is currently documented as `ready_for_review`, not officially completed. Respect the repository sprint lifecycle.

- If Sprint 03 is still the active branch and its validations remain valid, review and formally close it using the canonical `/clean-core-finish-sprint` flow before starting Sprint 04.
- Do not mix the corrective implementation into the official Sprint 03 commit unless the canonical lifecycle/documentation already says Sprint 04 has started.
- Then run/start **SPRINT-04 — Assessment-Centric Product Alignment** on branch `sprint/04-assessment-centric-product-alignment`.
- Do not implement the old Dependencies/ATC Sprint 04 scope; it is now Sprint 05.

## Mandatory target model
Replace the canonical runtime hierarchy:

```text
Client → SAPSystem → Assessment
```

with:

```text
Client 1 ───── N Assessment
Assessment.sap_source_system
```

`SAPSystem` must cease to be an independent canonical ORM/domain/API/frontend entity.

### Client
Keep the initial model simple:
- id generated internally;
- name;
- description.

### Assessment
At minimum:
- id;
- client_id;
- name;
- sap_source_system;
- description;
- status and existing timestamps where useful.

## Database migration
Do not edit or delete already-applied Alembic migrations from Sprints 01–03.

Create a new forward migration that safely transforms the current schema. Inspect the actual current migration/schema first. The intended transformation is:

1. add direct `assessment.client_id` as needed;
2. add `assessment.sap_source_system`;
3. backfill both from the existing `sap_system` relation;
4. create/update indexes and constraints;
5. remove obsolete `assessment.sap_system_id` after successful backfill;
6. remove the obsolete `sap_system` table only after code no longer depends on it.

Preserve existing Assessment-owned `source_scan`, `source_file` and `sap_object` data whenever practical. Because this is a PoC, synthetic seed data may be reseeded if necessary, but the migration itself must be explicit, forward-only and reproducible.

## Backend/API changes
Remove nested System-centric contracts and implement Assessment-centric APIs consistent with the current architecture.

Required behavior:
- list Clients;
- create Client;
- list all Assessments;
- filter Assessments by Client and Assessment/name query;
- create Assessment selecting a pre-existing Client;
- retrieve/open Assessment directly;
- expose `sap_source_system` as Assessment metadata.

Update schemas, ORM relationships, services/routes, tests and seed data accordingly.

Do not preserve obsolete APIs merely to keep the old hierarchy alive unless a temporary compatibility shim is strictly necessary for the migration. If a shim is used, mark it temporary and do not expose it as canonical UX.

## Frontend — first screen
The first screen after application startup must be **Assessments Home**.

It must show:
- assessment grid/list;
- filter by Client;
- filter/search by Assessment;
- action `Novo Assessment`;
- action `Novo Cliente`;
- useful lightweight columns such as Assessment, Client, SAP source system, status and updated timestamp when available.

There must be **no left sidebar on Assessments Home**.

The right-side AI Copilot must remain visible/available.

Remove the current three-column Client → SAP System → Assessment Hub.

## New Client flow
Create a simple form/modal:
- Nome;
- Descrição.

## New Assessment flow
Create a form/modal with:
- Cliente — selection of a pre-registered Client;
- Nome do Assessment;
- SAP System de Origem;
- Descrição.

After creation, allow the user to open the Assessment.

## Assessment workspace shell
The left sidebar appears only after an Assessment is active.

Canonical menu:

```text
Clean Core
  1 - Ingestão dos dados
  2 - Análise ATC
  3 - Processamento por IA

Resultado
  Dashboard Geral
  Executive View
  Technical View
  Functional View
  Architecture View
```

For capabilities not yet implemented (ATC, AI processing, later result views), create coherent lightweight placeholders/routes if needed for Sprint 04 navigation, but do not prematurely implement later sprint domain logic.

Always show current Client / Assessment context. Do not reintroduce SAP System as a selected hierarchy level.

## Source Ingestion correction
Current Sprint 02 behavior must be aligned:

- source directory field starts blank every time a new selection action is expected;
- do not pre-populate `/workspace`, demo path, project root or any other default as the user's chosen source directory;
- `Start Scan` starts disabled;
- enable it only after explicit valid directory selection;
- selecting a directory must not automatically start scanning;
- backend `scan_root` may remain an internal safety boundary if architecturally required, but must not be presented as the selected user path;
- existing scan history may be displayed without auto-selecting its path as a new scan input.

## Preserve working capabilities
Do not regress:
- source scanning/classification;
- existing source-file persistence;
- SAP object parsing;
- Assessment-scoped object list/detail APIs;
- ObjectBrowser capability;
- permanent right-side Copilot shell;
- PostgreSQL/pgvector foundation;
- lean PoC testing approach.

Move/reintegrate ObjectBrowser into the appropriate Technical context if the navigation refactor affects it.

## Status/progress
Use a lightweight Assessment status model sufficient for the home grid and processing flow. Do not build an enterprise workflow engine.

Conceptually support states equivalent to:
- Draft;
- Ingestion in progress;
- Ingestion completed;
- ATC imported;
- AI processing;
- Ready;
- Processing failed.

Reuse/refine existing enum values where sensible rather than creating unnecessary complexity.

## Validation required before Sprint 04 can finish
At minimum validate:

1. forward Alembic migration from the current Sprint 03 schema;
2. no canonical `SAPSystem` ORM/API/frontend dependency remains;
3. seed creates Client → Assessment data with `sap_source_system`;
4. app starts on Assessments Home;
5. home has no left sidebar;
6. Copilot is available on home;
7. Client filter and Assessment search/filter work;
8. Novo Cliente works;
9. Novo Assessment works and requires/selects Client;
10. opening an Assessment shows the left sidebar;
11. Client / Assessment context is visible;
12. Source Ingestion initial path is blank;
13. Start Scan is disabled before explicit directory selection and enabled afterward;
14. scanning still works;
15. existing parsed-object list/detail flow still works;
16. TypeScript typecheck and lean backend/smoke tests pass.

## Documentation during implementation
Update Sprint 04 progress and `SESSION_HANDOFF.md` as checkpoints are validated. Record any migration compromise or compatibility shim explicitly.

Do not modify accepted product architecture to make the old code easier to keep. The code must adapt to Baseline R3.1 / ADR-015.

When all Sprint 04 capabilities and minimal validations are complete, leave the sprint `ready_for_review`. Do not create the official sprint commit except through `/clean-core-finish-sprint`.


## ATC forward constraint
When Sprint 05 is reached, follow ADR-016 and `docs/data/atc-import-contract.md`; do not hard-code the reviewed 21-column sample.
