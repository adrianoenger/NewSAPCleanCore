# App Shell and Navigation

## Two shell states
The PoC uses two related layouts rather than one permanent three-column layout.

### 1. Assessments Home
```text
CENTER / ASSESSMENTS HOME                         RIGHT
Assessment grid, filters and create actions       AI Copilot
flexible                                           ~360-480px, resizable
```

Rules:
- this is the first screen after application startup;
- no left navigation sidebar;
- list all Assessments;
- filters by Client and Assessment;
- actions `Novo Assessment` and `Novo Cliente`;
- permanent Copilot on the right.

### 2. Assessment Workspace
```text
LEFT                 CENTER                         RIGHT
Assessment nav       Current stage/result           AI Copilot
~220-260px           flexible                       ~360-480px, resizable
```

React shell concept:
```text
AppShell
  ├── optional AssessmentSidebar
  ├── WorkspaceOutlet
  └── CopilotPanel
```

`AssessmentSidebar` is mounted only when an Assessment is active. `CopilotPanel` remains mounted across home/workspace transitions to preserve conversation/context.

## Assessment sidebar
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

## Top context bar
On Assessments Home, identify the portfolio context and filters without pretending that an Assessment is selected.

Inside an Assessment, always make current **Client / Assessment** visible. Do not show a separately selected SAP System hierarchy; source SAP system may appear as Assessment metadata.

## Source Ingestion interaction
- directory field blank on first entry;
- Browse opens native directory selection;
- Start Scan disabled until valid explicit selection;
- no scan begins automatically;
- previously persisted scans may be shown as history without using a historical path as a new default selection.

## Global interaction principle
Any relevant entity may support `Ask AI` / `Add to Copilot`. Source code selection should be transferable to Copilot without copy/paste.
