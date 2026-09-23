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
- No automatic remote push is performed.
- Progress recovery relies on persisted project state/progress files plus the sprint working tree, not intermediate commits.

## Consequences
The `main` history remains one commit per sprint plus explicit baseline/administrative commits created by the user outside sprint implementation. Interrupted development must preserve the local sprint working tree and progress files until resumed.
