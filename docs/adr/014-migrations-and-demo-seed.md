# ADR-014 — Alembic Migrations and Reproducible Demo Seed

**Status:** Accepted  
**Date:** 2026-09-23

## Context
The persistence model will evolve across many sprints. The PoC also needs fast, repeatable demonstration and validation without processing a full customer assessment every time.

## Decision
- Use Alembic for PostgreSQL schema evolution once persistence is introduced.
- Avoid manual database recreation as the normal development workflow.
- Maintain a small reproducible seed/demo dataset that grows only as needed to demonstrate implemented capabilities.
- Seed data must be synthetic or otherwise safe for the repository; do not commit customer data.

## Consequences
Sprints that change schema must include a minimal migration applicability check. Seed/demo data is an accelerator for sprint validation, not a substitute for later reference-assessment testing.
