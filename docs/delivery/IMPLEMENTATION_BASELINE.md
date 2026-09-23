# Implementation Baseline

## Purpose
This document is the implementation contract for the initial PoC. Claude Code must implement the architecture and product behavior described here and in accepted ADRs.

## Target runtime
- Electron + React desktop application on host.
- FastAPI/Python backend in Dev Container.
- PostgreSQL + pgvector.
- local filesystem assessment source mounted/accessible to backend.
- optional local Docker MCPs: `mcp-sap-docs`, `mcp-abap`.
- LLM providers: AWS Bedrock and Azure AI Foundry through adapters.

## Canonical processing flow
Client → SAP System → Assessment → Source Scan → Classification → Parsing → Dependencies + ATC → Technical Findings → Object Understanding → Business Rules → Applications → SAP Knowledge → Clean Core → Recommendations → Embeddings → Aggregations → Dashboards/Explorer/Copilot.

## Core product rules
1. Multiple Clients, SAP Systems and Assessments are supported.
2. Source files and SAP objects are distinct entities.
3. Deterministic facts precede AI interpretation.
4. Long-running stages use durable work items.
5. Pipeline supports pause/resume/retry/recovery.
6. AI persistable outputs are structured and evidence-bound.
7. Clean Core output separates Technical Risk, Business Importance and Recommendation.
8. SAP MCP evidence is external authoritative context; it is not copied indiscriminately into local RAG.
9. Embeddings represent meaningful semantic entities with assessment metadata.
10. Four selectable navigation perspectives expose the same assessment differently.
11. Right-side Copilot is permanently available and context-aware.
12. Chat may route to SQL, semantic search, source retrieval and MCP.
13. Chat never mutates assessment state without an explicit user action.
14. Testing remains intentionally lean.

## PoC acceptance narrative
A successful final demonstration should allow a user to:
1. choose a client/system/assessment;
2. process a large source directory with visible durable progress;
3. pause and resume processing;
4. explore discovered custom applications and business rules;
5. inspect Clean Core findings and supporting source evidence;
6. see SAP guidance attached to relevant findings/recommendations;
7. switch between Executive, Architecture, Functional and Technical views;
8. ask the Copilot questions about the current context and navigate from answers to evidence.
