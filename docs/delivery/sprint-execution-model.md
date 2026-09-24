# Sprint Execution Model

## Purpose
Define the canonical development lifecycle for the PoC. This process favors traceability and fast recovery without creating unnecessary Git history.

## Core invariant

**One sprint = one sprint branch = one official commit on `main`.**

Development changes remain uncommitted during the sprint. Progress and recovery are represented by persisted project state files, not intermediate commits.

## Branch convention
A sprint branch is derived deterministically from the sprint filename.

Example:
- sprint file: `SPRINT-00-engineering-foundation.md`
- branch: `sprint/00-engineering-foundation`

Do not invent alternate branch names.

## Lifecycle

### 1. Preflight
Before a new sprint starts:
- current branch is `main`;
- working tree is clean;
- local `main` is synced with the remote (`git fetch origin` + `git pull --ff-only origin main`);
- previous sprint is completed or no sprint has started yet;
- required canonical files exist;
- no secret/customer data is staged;
- the current sprint can be resolved from `EXECUTION_STATE.yaml` or, for the initial run, initialized as SPRINT-00.

### 2. Run or resume
`/clean-core-run-sprint`:
- reads canonical documentation and current execution state;
- for a new sprint, always creates the canonical sprint branch from the synced `main`;
- if the sprint branch already exists, switches to/reuses it;
- creates a sprint progress file from the template if missing;
- resumes from the first incomplete capability/checkpoint;
- performs all checkpoints, development and progress updates on the sprint branch;
- continues autonomously until implementation is ready for review or a genuine blocker is reached;
- never creates the sprint commit;
- never starts the next sprint.

### 3. Review
`/clean-core-review-sprint` is read-only. It reports:
- scope implemented;
- demonstrable flow readiness;
- minimal tests/checks status;
- progress/documentation consistency;
- unresolved blockers or known limitations;
- repository hygiene observations;
- `READY_TO_FINISH: YES|NO`.

### 4. Validate
`/clean-core-validate` runs the lean validation set for the current sprint without changing lifecycle state.

### 5. Finish
`/clean-core-finish-sprint` is the only official sprint closure command.

It must, in order:
1. confirm the current branch is the canonical branch of the active sprint and that `origin/main` has not advanced beyond the sprint base;
2. confirm all required sprint capabilities are complete or explicitly deferred with accepted rationale;
3. run the mandatory lean validation set;
4. verify migrations are applicable when database schema changed;
5. verify no secrets, customer data, local databases, generated indexes or temporary files are included;
6. generate `docs/delivery/results/SPRINT-XX-RESULT.md` from the result template;
7. update sprint progress to `completed` and `100%`;
8. update `SESSION_HANDOFF.md` with the completed result and next-sprint readiness;
9. update `EXECUTION_STATE.yaml` so the finished sprint is recorded and the next sprint is marked `not_started`/ready, without starting it;
10. `git add -A`;
11. create exactly one official sprint commit using the canonical message;
12. push the sprint branch: `git push -u origin <sprint-branch>`;
13. switch to `main`;
14. fast-forward `main` with `git merge --ff-only <sprint-branch>`;
15. push `main`: `git push origin main`;
16. delete the local sprint branch with `git branch -d <sprint-branch>` (the remote sprint branch is kept as the sprint record);
17. update local `main`: `git pull --ff-only origin main`;
18. verify current branch is `main`, working tree is clean, the local sprint branch is absent and `main` equals `origin/main`.

After a successful finish the repository is ready for the next `/clean-core-run-sprint`.

If any mandatory step fails before the commit, closure must abort. Do not mark the sprint complete prematurely. If a push fails after the commit, stop without additional commits, keep the local sprint branch and report the pending steps.

## Commit convention
Canonical format:

`feat(sprint-NN): complete <sprint title in concise lowercase form>`

Examples:
- `feat(sprint-00): complete engineering foundation`
- `feat(sprint-01): complete client system assessment`

There are no intermediate sprint commits and no merge commit. `main` is advanced by fast-forward.

## Scope control and backlog
During a sprint, discoveries that do not block the current demonstrable outcome go to `BACKLOG.md`. Do not silently expand scope.

## Architectural conflicts
Claude Code may make normal implementation choices autonomously. It must not contradict accepted ADRs or canonical architecture silently. Record the conflict in progress/handoff and stop only the affected work when a material architectural decision is required.

## Remote synchronization
Only `/clean-core-finish-sprint` pushes: the sprint branch and `main`, after the official commit. Sprint development never pushes. Force-push is never used (ADR-013, amendment 2026-09-24).
