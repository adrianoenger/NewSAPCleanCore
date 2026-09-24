# ADR-015 — Assessment-Centric Workspace and Navigation

**Status:** Accepted  
**Date:** 2026-09-24

## Context
The first implementation increments introduced `Client → SAPSystem → Assessment` as a persistent navigation hierarchy and a three-column Client Hub. Product review showed that this adds an unnecessary entity and navigation step for the PoC. The user works primarily with assessments, while the SAP source system is descriptive context of an assessment rather than an independently managed product object.

The same review also clarified the desired workspace flow: ingestion, ATC import, AI processing and results are stages of one assessment; the initial application screen is an assessment portfolio; the left navigation is meaningful only after an assessment is opened; and the AI Copilot remains permanently available on the right.

## Decision
The canonical product hierarchy is:

```text
Client 1 ───── N Assessment

Assessment
  ├── sap_source_system
  ├── Source Ingestion
  ├── ATC Analysis
  ├── AI Processing
  └── Results
```

`SAPSystem` is removed as an independent domain/persistence/navigation entity. `sap_source_system` is an attribute of `Assessment`.

The application opens on an **Assessments Home** containing:
- assessment grid/list;
- filters by client and assessment;
- actions `Novo Assessment` and `Novo Cliente`;
- no left sidebar;
- permanent right-side AI Copilot.

After opening an assessment, the left sidebar appears with two groups:

```text
Clean Core
  1 - Ingestão dos dados
  2 - Análise ATC
  3 - Processamento por IA

Resultado
  Dashboard Geral
  Executive View
  Technical View
  Functional View
  Architecture View
```

Source Ingestion starts with an empty directory field. `Start Scan` is disabled until the user explicitly selects a valid directory. No default source path may be pre-populated in the UI.

## Consequences
- Existing code and migrations that persist `SAPSystem` require an explicit corrective migration; database history must not be rewritten.
- Existing nested APIs and frontend context based on Client/System/Assessment must be replaced with assessment-centric contracts.
- Existing Sprint 01/02 result documents remain historical records of what was implemented, but are superseded by this ADR and the current Implementation Baseline wherever they conflict.
- The four results perspectives are named Executive, Technical, Functional and Architecture. Dashboard Geral is a fifth synthesis entry point, not a fifth perspective.
- The Copilot remains mounted on Assessments Home and inside assessment workspaces.
