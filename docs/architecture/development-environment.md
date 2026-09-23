# Development Environment

## Decision
Backend development runs in Docker through a Dev Container.

## Compose services
Minimum target services:
- `backend`: FastAPI/Python development service;
- `postgres`: PostgreSQL with pgvector;
- `mcp-sap-docs`: local SAP documentation MCP when enabled;
- `mcp-abap`: local ABAP MCP when enabled.

Electron/React runs on the host during development unless a later sprint demonstrates a better workflow. This preserves natural desktop filesystem access.

## Developer objective
`git clone` → open in VS Code → **Reopen in Container** → backend dependencies available and core services start with one documented command.

## Configuration
Use `.env.example` plus non-secret application configuration. Never commit provider credentials. The existing legacy `.env` is not a source of truth and must not be copied into the new baseline.
