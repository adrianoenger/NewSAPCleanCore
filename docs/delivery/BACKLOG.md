# Controlled Backlog

This file captures useful discoveries that are outside the active sprint. Recording an item here does **not** authorize implementation.

| ID | Title | Description | Origin | Priority | Suggested Sprint | Status |
|---|---|---|---|---|---|---|
| BL-001 | Remove duplicate root `gitignore` file | Repository root contains `gitignore` (no dot), identical to `.gitignore` and without effect. Remove it or confirm it is intentional. | SPRINT-00 hygiene review | Low | Any (administrative) | Open |
| BL-002 | Wrap ATC import as an optional pipeline stage | SPRINT-06's durable pipeline wraps scan/parse/detect_dependencies; ATC import stays a standalone upload-triggered action (ADR-016) since it requires a user-supplied file per run and has no natural work-item decomposition today. Could become a 4th DAG stage once a "re-run last uploaded ATC file" use case exists. | SPRINT-06 design | Low | Future | Open |
| BL-003 | Wrap future AI-processing stages (SPRINT-07+) in the same PipelineRun/StageRun/WorkItem engine | The engine in `backend/src/pipeline/` is generic (stage handlers registered via `StageDefinition`); object understanding, business-rule discovery, etc. should register as additional stages instead of building a parallel execution mechanism. | SPRINT-06 design | Medium | SPRINT-07+ | Open |

## Rules
- Use a stable ID such as `BL-001`.
- Do not implement backlog items during the active sprint unless they are promoted into canonical sprint scope.
- A prerequisite defect that blocks the sprint is not backlog; it may be fixed as part of the active sprint and documented in progress.
- Architectural proposals must also respect ADR governance; a backlog entry cannot override an accepted ADR.
