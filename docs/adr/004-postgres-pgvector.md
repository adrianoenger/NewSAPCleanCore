# ADR-004 — PostgreSQL + pgvector Persistence

**Status:** Accepted  
**Date:** 2026-09-23

## Decision
Use PostgreSQL as the structured source of truth and durable job-state store, with pgvector for semantic embeddings. Do not target SQLite for the new PoC runtime.

## Consequence
Implementation and sprint acceptance criteria must remain consistent with this decision. Any future change requires updating or superseding this ADR.
