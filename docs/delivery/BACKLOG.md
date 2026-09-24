# Controlled Backlog

This file captures useful discoveries that are outside the active sprint. Recording an item here does **not** authorize implementation.

| ID | Title | Description | Origin | Priority | Suggested Sprint | Status |
|---|---|---|---|---|---|---|
| BL-001 | Remove duplicate root `gitignore` file | Repository root contains `gitignore` (no dot), identical to `.gitignore` and without effect. Remove it or confirm it is intentional. | SPRINT-00 hygiene review | Low | Any (administrative) | Open |

## Rules
- Use a stable ID such as `BL-001`.
- Do not implement backlog items during the active sprint unless they are promoted into canonical sprint scope.
- A prerequisite defect that blocks the sprint is not backlog; it may be fixed as part of the active sprint and documented in progress.
- Architectural proposals must also respect ADR governance; a backlog entry cannot override an accepted ADR.
