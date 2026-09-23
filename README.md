# SAP Clean Core Analysis PoC — Documentation Baseline R1

**Baseline date:** 2026-09-23  
**Purpose:** canonical documentation for the next PoC generation of the SAP Clean Core analysis application.

This repository is documentation-first. It defines what must be implemented before implementation proceeds. The existing notebook-based solution is treated as a source of proven parsing and analysis ideas, not as the target architecture.

## Product in one sentence

Transform a large set of SAP/ABAP artifacts into structured technical knowledge, discovered business rules, functional applications, evidence-based Clean Core recommendations, visual dashboards, and a context-aware AI Copilot.

## Canonical hierarchy

1. `docs/product/` — product scope, capabilities and user journey.
2. `docs/architecture/` — target technical architecture and runtime behavior.
3. `docs/data/` — domain and persistence model.
4. `docs/ux/` — navigation, views and permanent AI Copilot.
5. `docs/ai/` — LLM orchestration, structured outputs and evidence rules.
6. `docs/integrations/` — SAP documentation MCP providers.
7. `docs/adr/` — decisions that constrain implementation.
8. `docs/delivery/` — implementation baseline, roadmap, sprints and execution state.
9. `docs/legacy/` — mapping from the current solution to the new architecture.

## Ground rules

- This is a **PoC**, not a production enterprise platform.
- Build sequentially by sprint; every sprint leaves the application executable and demonstrable.
- Prefer deterministic extraction for facts; use AI for interpretation; use SAP knowledge providers for authoritative guidance.
- Persist long-running processing state so work can pause, resume, retry and recover.
- The same assessment is explored through four navigation views: Executive, Architecture & Clean Core, Business & Rules, Engineering & Code.
- The right side of the application is permanently dedicated to the AI Copilot.
- LLM providers: **AWS Bedrock** and **Azure AI Foundry** behind a provider abstraction.
- SAP knowledge: `mcp-sap-docs` and `mcp-abap`, configurable by URL.
- Development backend: Docker + Dev Container.
- Persistence: PostgreSQL + pgvector.
- Testing is intentionally lean for PoC speed.

Start with `docs/delivery/IMPLEMENTATION_BASELINE.md` and `CLAUDE.md`.
