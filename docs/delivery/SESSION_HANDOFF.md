# Session Handoff

## Current state
Documentation baseline R2 created. Implementation has not started.

## Git lifecycle
- Repository baseline is expected to be committed on `main` by the user.
- Initial implementation sprint: `SPRINT-00`.
- Canonical initial sprint branch: `sprint/00-engineering-foundation`.
- One official commit is allowed per sprint and is created only by `/clean-core-finish-sprint`.

## Restart instruction
1. read `CLAUDE.md`;
2. read `docs/delivery/IMPLEMENTATION_BASELINE.md`;
3. read `docs/delivery/sprint-execution-model.md`;
4. read `EXECUTION_STATE.yaml` and the current sprint progress file, if present;
5. run `/clean-core-run-sprint` to initialize or resume the active sprint;
6. do not create intermediate Git commits.

## Important
The legacy source package is reference material only. Do not copy its secrets or treat its notebooks as the target runtime architecture. New ideas outside current sprint scope belong in `BACKLOG.md`.
