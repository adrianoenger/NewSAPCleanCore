# ADR-013 — One Branch and One Official Commit per Sprint

**Status:** Accepted  
**Date:** 2026-09-23

## Context
The PoC is developed through sequential autonomous sprints. The repository should remain easy to understand and every main-branch commit should correspond to a demonstrable product increment.

## Decision
- Each sprint uses one canonical local branch named `sprint/<NN>-<slug>`.
- No Git commits are created during normal sprint development.
- `/clean-core-run-sprint` starts or resumes work and never commits.
- `/clean-core-finish-sprint` is the only closure command.
- Finish updates completion documentation, creates exactly one sprint commit, fast-forwards `main`, deletes the local sprint branch, and stops without starting the next sprint.
- ~~No automatic remote push is performed.~~ Superseded by the 2026-09-24 amendment below.
- Progress recovery relies on persisted project state/progress files plus the sprint working tree, not intermediate commits.

## Consequences
The `main` history remains one commit per sprint plus explicit baseline/administrative commits created by the user outside sprint implementation. Interrupted development must preserve the local sprint working tree and progress files until resumed.

## Amendment — 2026-09-24 (remote synchronization)
**Decided by:** project owner, after SPRINT-00 closure.

- `/clean-core-run-sprint` always starts a sprint by syncing local `main` with `origin/main` (fast-forward only) and creating the canonical sprint branch from it. All checkpoints and development happen on that branch.
- `/clean-core-finish-sprint`, after creating the single sprint commit, pushes the sprint branch to `origin`, fast-forwards local `main`, pushes `main` to `origin`, deletes the local sprint branch and updates local `main` from the remote.
- The remote sprint branch is kept as the sprint record.
- Force-push is never used. If a push fails after the commit exists, closure stops without creating additional commits and reports the pending steps.

**Consequence:** after a successful finish, local and remote `main` are identical and the repository is ready to start the next sprint.
