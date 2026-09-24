# SAP Clean Core Analysis PoC — Documentation Baseline R3.1

**Baseline date:** 2026-09-24  
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
- Each sprint uses one sprint branch (created from the synced `main`) and produces exactly one official Git commit when it is formally finished.
- `/clean-core-run-sprint` starts or resumes the current sprint and never creates the official sprint commit.
- `/clean-core-finish-sprint` is the only project command allowed to finalize sprint status, create the sprint commit, push the sprint branch, fast-forward and push `main`, delete the local sprint branch and update local `main`.
- New ideas outside the active sprint go to `docs/delivery/BACKLOG.md`; they must not silently expand sprint scope.
- Architectural decisions must not be changed silently during implementation.
- Canonical ownership is `Client → Assessment`; SAP source system is Assessment metadata, not an independent managed entity.
- The left sidebar is hidden on Assessments Home and appears only inside an Assessment.
- Prefer deterministic extraction for facts; use AI for interpretation; use SAP knowledge providers for authoritative guidance.
- Treat ATC XLSX as semi-structured external evidence: preserve raw rows/header mapping and tolerate optional/additional columns.
- Persist long-running processing state so work can pause, resume, retry and recover.
- The application opens on Assessments Home; inside an Assessment, results are explored through Dashboard Geral plus Executive, Technical, Functional and Architecture views.
- The right side of the application is permanently dedicated to the AI Copilot.
- LLM providers are **AWS Bedrock** and **Azure AI Foundry** behind a provider abstraction.
- SAP knowledge uses `mcp-sap-docs` and `mcp-abap`, configurable by URL.
- Backend development uses Docker + Dev Container.
- Persistence uses PostgreSQL + pgvector and schema changes use Alembic migrations.
- Testing is intentionally lean for PoC speed.
- Seed/demo data should exist from early sprints so each increment can be reproduced quickly.

Start with `CLAUDE.md`, `docs/delivery/IMPLEMENTATION_BASELINE.md`, and `docs/delivery/sprint-execution-model.md`.

## Running the application (development)

### Prerequisites
- Docker Desktop (Compose v2.24+).
- Node.js 22+ on the host (Electron/React run on the host, see ADR-003).
- Optional: VS Code with the Dev Containers extension.

### 1. Configuration
```bash
cp .env.example .env   # optional; defaults work out of the box. Never commit .env.
```

### 2. Backend + PostgreSQL/pgvector
```bash
docker compose up -d --build            # starts postgres + backend; applies Alembic migrations on start
curl http://localhost:8000/health       # {"status":"ok", "database":{"pgvector":true, ...}}
```
Alternatively open the folder in VS Code and choose **Reopen in Container** (`.devcontainer/`), which attaches to the same `backend` service.

Backend commands (run inside the container, e.g. `docker compose exec backend <cmd>`):

| Purpose | Command |
|---|---|
| Apply migrations | `alembic upgrade head` |
| New migration | `alembic revision --autogenerate -m "<message>"` |
| Apply synthetic demo seed (idempotent) | `python -m seed apply demo` |
| Show applied seeds | `python -m seed status` |
| Backend smoke/contract tests | `pytest -q` |

### 3. Desktop shell (host)
```bash
cd frontend
npm install
npm run dev          # Electron + Vite with hot reload
npm run typecheck
npm run smoke        # builds, launches Electron, checks shell regions + health (backend must be running)
```

### Layout
```text
backend/     FastAPI + SQLAlchemy + Alembic (runs in Docker)
frontend/    Electron + React + TypeScript + Tailwind/shadcn (runs on host)
compose.yml  postgres (pgvector) + backend
.devcontainer/
docs/        canonical documentation
```
