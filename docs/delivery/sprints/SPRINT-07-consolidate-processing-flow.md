# SPRINT-07 — Consolidate Processing Flow

## Position in the sequence
- Prerequisite: SPRINT-06 completed.
- Coherence rule: This sprint does not add new domain capability — it consolidates navigation and removes duplicate work between Ingestão (Sprint 02) and the durable pipeline (Sprint 06, ADR-005), without changing ADR-005's engine contract or touching ATC import (ADR-016/BL-002).

## Why
"Pipeline de Processamento" (Sprint 06) was added as an unnumbered nav item between "1 - Ingestão dos dados" and "2 - Análise ATC". Its `scan` stage re-walks the filesystem, duplicating the inventory Ingestão already persisted (`SourceScan`/`SourceFile`). Meanwhile "3 - Processamento por IA" — the canonical third step of the Baseline R3.2 / ADR-015 flow — is still an empty placeholder. This sprint finishes what Sprint 06 started: the durable engine becomes the real Step 3, fed by the ingestion already done in Step 1, with no redundant re-scan.

## Goal
One coherent 3-step Assessment flow (Ingestão → Análise ATC → Processamento por IA) with no duplicate scanning and explicit invalidation when a new ingestion supersedes a previously processed one.

## Planned capabilities
- CAP-001: Sprint bootstrap — renumber SPRINT-07..15 to SPRINT-08..16, update roadmap/backlog/execution-state (this checkpoint).
- CAP-002: `pipeline/status.py` (`get_current_scan`, `compute_processing_status`); make the pipeline's `scan` stage idempotent — reuse an already-completed `SourceScan` for the same resolved `source_path` instead of re-walking the disk.
- CAP-003: `GET /assessments/{id}/pipeline-runs/processing-status` endpoint exposing current scan + staleness (`is_stale`) so the UI knows when Step 3 needs to (re)run.
- CAP-004: Scope `GET /assessments/{id}/objects` to the current scan; remove the standalone manual parse route (`POST .../scans/{id}/parse`) and its schema.
- CAP-005: Frontend — remove the orphan "Pipeline de Processamento" nav item; `PipelineRunner` becomes the real "3 - Processamento por IA" view, auto-detecting the current ingestion (no manual directory picker) and showing a "desatualizado" banner when `is_stale`.
- CAP-006: `ObjectBrowser` becomes read-only (remove manual "Parse" trigger); full validation pass (pytest + typecheck/build + manual end-to-end flow); record BL-004 (ATC correlation vs. reprocessing) in BACKLOG.

## Out of scope
- ATC import (`ATCImport.tsx`, `backend/src/atc/`) — stays standalone per ADR-016/BL-002.
- Manual dependency-detection routes in `dependencies.py` — same class of duplication, but not used by any component today; not removed here to avoid silent scope expansion.

## Demonstrable outcome
Open an Assessment → run Step 1 (ingestão) over a directory → Step 3 auto-detects it and processes (parse + dependency detection) without re-scanning → Technical View shows the parsed objects → run Step 1 again over a different directory → Step 3 shows "desatualizado" → reprocess → Technical View shows only the current scan's objects (no mixing).

## Minimal validation
- Primary user flow for this sprint works end to end (see Demonstrable outcome).
- `pytest` (new `test_sprint07.py` + full suite, no regression in `test_sprint06.py`).
- `tsc --noEmit` / `npm run build` clean.
- Do not add broad test coverage unrelated to the demonstrated capability.

## Completion criteria
- Planned capabilities implemented or explicitly deferred with rationale.
- Demonstrable outcome reproduced successfully.
- Progress/state files updated; BL-004 recorded.
- Application remains runnable for the next sprint (SPRINT-08, AI Object Understanding).
