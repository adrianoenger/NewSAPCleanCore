# SPRINT-02 — Source Ingestion

## Goal
Turn an assessment directory into a persistent source inventory.

## Planned capabilities
- Use Electron to select a local directory.
- Implement backend-visible path mapping/validation.
- Scan files and persist path, size, mtime and SHA-256.
- Classify known artifact categories without parsing domain content yet.
- Show scan progress and file counts.

## Demonstrable outcome
Select a large directory and see a persisted classified file inventory.

## Minimal validation
- Primary user flow for this sprint works.
- Relevant smoke test(s) pass.
- Critical API/schema/domain contracts introduced by this sprint are validated.
- Do not add broad test coverage unrelated to the demonstrated capability.

## Completion criteria
- Planned capabilities implemented or explicitly deferred with rationale.
- Demonstrable outcome reproduced successfully.
- Progress/state files updated.
- Application remains runnable for the next sprint.
