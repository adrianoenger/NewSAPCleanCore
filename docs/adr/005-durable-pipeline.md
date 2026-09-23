# ADR-005 — Durable Work-Item Pipeline

**Status:** Accepted  
**Date:** 2026-09-23

## Decision
Long stages are decomposed into persisted work items with pause/resume/retry/recovery, idempotency and incremental invalidation. PostgreSQL is sufficient as the PoC durable queue/state store; no Celery/Redis initially.

## Consequence
Implementation and sprint acceptance criteria must remain consistent with this decision. Any future change requires updating or superseding this ADR.
