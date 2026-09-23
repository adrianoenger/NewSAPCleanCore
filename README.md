# SAP Clean Core Analysis PoC — Documentation Baseline R2

**Baseline date:** 2026-09-23  
**Purpose:** canonical documentation for the initial PoC generation of the SAP Clean Core analysis application.

This repository is documentation-first. The existing notebook-based solution is a source of proven parsing and analysis ideas, not the target runtime architecture.

## Product in one sentence

Transform a large set of SAP/ABAP artifacts into structured technical knowledge, discovered business rules, functional applications, evidence-based Clean Core recommendations, visual dashboards, and a context-aware AI Copilot.

## Canonical hierarchy

1. `docs/product/` — product scope, capabilities and user journey.
2. `docs/architecture/` — target technical architecture and runtime behavior.
3. `docs/data/` — domain and persistence model.
4. `docs/ux/` — navigation, views and permanent AI Copilot.
5. `docs/ai/` — LLM orchestration, structured outputs and evidence rules.
6. `docs/integrations/` — SAP documentation MCP providers.
7. `docs/adr/` — accepted decisions that constrain implementation.
8. `docs/delivery/` — implementation baseline, roadmap, sprint lifecycle and execution state.
9. `docs/legacy/` — mapping from the current solution to the new architecture.

## Ground rules

- This is a **PoC**, not a production enterprise platform.
- Development is sequential by sprint and every sprint leaves an executable, testable and demonstrable increment.
- Each sprint uses one local branch and produces exactly one official Git commit when it is formally finished.
- `/clean-core-run-sprint` starts or resumes the current sprint and never creates the official sprint commit.
- `/clean-core-finish-sprint` is the only project command allowed to finalize sprint status, create the sprint commit, fast-forward `main`, and delete the local sprint branch.
- New ideas outside the active sprint go to `docs/delivery/BACKLOG.md`; they must not silently expand sprint scope.
- Architectural decisions must not be changed silently during implementation.
- Prefer deterministic extraction for facts; use AI for interpretation; use SAP knowledge providers for authoritative guidance.
- Persist long-running processing state so work can pause, resume, retry and recover.
- The same assessment is explored through four navigation views: Executive, Architecture & Clean Core, Business & Rules, Engineering & Code.
- The right side of the application is permanently dedicated to the AI Copilot.
- LLM providers are **AWS Bedrock** and **Azure AI Foundry** behind a provider abstraction.
- SAP knowledge uses `mcp-sap-docs` and `mcp-abap`, configurable by URL.
- Backend development uses Docker + Dev Container.
- Persistence uses PostgreSQL + pgvector and schema changes use Alembic migrations.
- Testing is intentionally lean for PoC speed.
- Seed/demo data should exist from early sprints so each increment can be reproduced quickly.

Start with `CLAUDE.md`, `docs/delivery/IMPLEMENTATION_BASELINE.md`, and `docs/delivery/sprint-execution-model.md`.
