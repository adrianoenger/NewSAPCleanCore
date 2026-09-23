# Durable Pipeline Execution

## Goal
Long-running stages must survive application closure, backend restart, temporary provider failure and deliberate user pause.

## Persistent hierarchy
Assessment → PipelineRun → StageRun → WorkItem.

## Stage states
`PENDING`, `RUNNING`, `PAUSING`, `PAUSED`, `COMPLETED`, `FAILED`, `CANCELLED`.

## Work-item states
`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `SKIPPED`.

## Rules
- Checkpoint after every completed work item.
- Persist results and completion atomically where practical.
- Processing is idempotent for the same assessment, stage, entity and input version.
- Pause is cooperative: finish in-flight operations, start no new work, then become `PAUSED`.
- On backend startup, orphaned `RUNNING` items are recovered into retryable/pending state.
- Retry transient Bedrock, Foundry and MCP errors with a bounded number of attempts.
- Failed items do not necessarily fail the whole stage; provide `Retry Failed`.
- PostgreSQL acts as durable state and lightweight work queue for the PoC.
- Do not introduce Celery/Redis unless a future requirement proves necessary.

## Stage dependencies
Model the pipeline as a simple DAG so stages start only after required predecessors have reached an acceptable completion state.
