# SPRINT-06 — Durable Pipeline Execution

## Position in the sequence
- Prerequisite: SPRINT-05 completed.
- Coherence rule: Durable execution wraps the deterministic ingestion/parsing/dependency/ATC work already available; it must not change their domain contracts merely to simplify orchestration.

## Goal
Make long processing recoverable and user-controllable.

## Planned capabilities
- Persist PipelineRun, StageRun and WorkItem.
- Implement stage/work-item states and DAG dependencies.
- Implement cooperative pause/resume and bounded retry.
- Recover orphaned running work after backend restart.
- Show stage progress and failed-item retry in UI.

## Demonstrable outcome
Start processing, pause, restart backend, resume, and retry a deliberately failed item.

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
