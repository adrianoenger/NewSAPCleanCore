# Architecture Overview

## Style
PoC modular monolith with a desktop shell.

```text
Electron + React (host)
        │
        │ HTTP / WebSocket
        ▼
FastAPI / Python (Dev Container)
        │
        ├── ingestion & parsing
        ├── dependency / ATC analysis
        ├── durable pipeline manager
        ├── AI services
        ├── Clean Core engine
        ├── embeddings / retrieval
        ├── MCP knowledge adapters
        └── chat orchestrator
        │
        ├── PostgreSQL + pgvector
        ├── filesystem-mounted assessment sources
        ├── mcp-sap-docs
        └── mcp-abap
```

## Responsibility boundaries
### Electron
- native desktop shell;
- filesystem/directory selection;
- application lifecycle;
- path exchange with backend.

### React
- dashboards and views;
- exploration and navigation;
- persistent right-side Copilot panel;
- progress visualization;
- no Clean Core domain logic.

### FastAPI/Python
- all SAP parsing and domain processing;
- durable job orchestration;
- AI orchestration;
- persistence;
- retrieval and chat tools.

### PostgreSQL + pgvector
- structured source of truth;
- durable pipeline/work-item state;
- semantic embeddings.

## Backend modular layout
```text
backend/src/
  api/
  domain/
  ingestion/
  parsers/
  dependencies/
  atc/
  findings/
  pipeline/
  ai/
  business_rules/
  applications/
  clean_core/
  knowledge/
  embeddings/
  chat/
  persistence/
```


## Assessment-centric ownership
The runtime domain boundary is `Client → Assessment`. The source SAP system is Assessment metadata (`sap_source_system`), not an independently managed aggregate. Source scans, parsed objects, ATC findings, pipeline state, AI outputs and results are Assessment-scoped.

The React shell has two states: Assessments Home without a left sidebar, and Assessment Workspace with the left process/results sidebar. The right-side Copilot remains present in both.
