# User Journey

## Entry mode — Assessments Home
1. Open application.
2. View all Assessments in a grid/list; no left sidebar is shown.
3. Filter by Client and Assessment name (and optionally status).
4. Create a simple Client when required (`name`, `description`).
5. Create an Assessment by selecting a pre-registered Client and informing Assessment name, SAP source system and description.
6. Open an Assessment.

The AI Copilot remains accessible on the right even on this home screen.

## Assessment processing mode
After an Assessment is opened, show the left sidebar with:

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

### 1 - Ingestão dos dados
1. Open Source Ingestion.
2. Source directory is blank by default.
3. `Start Scan` remains disabled until a valid directory is explicitly selected.
4. Select a directory through Electron.
5. Start scan explicitly.
6. Observe discovery/classification/parsing progress and persisted inventory.

### 2 - Análise ATC
1. Select an ATC `.xlsx` report.
2. Discover the usable worksheet and headers.
3. Show recognized, missing-known and unknown columns plus row count.
4. Classify the import as full, partial or rejected; missing optional columns produce warnings rather than failure.
5. Preserve the raw source rows/header mapping and normalize the available recognized fields.
6. Import/persist findings and run provenance.
7. Correlate findings with Assessment objects/evidence when possible; keep unmatched/ambiguous rows explicit.
8. Show imported findings, warning summary and correlation summary.

### 3 - Processamento por IA
1. Start/resume Assessment processing.
2. Observe stage-by-stage durable progress.
3. Pause/resume/retry as supported.
4. Produce object understanding, business rules, applications, Clean Core interpretation, recommendations and embeddings.
5. On completion, show preliminary KPIs: analyzed objects, identified customizations, critical findings, high-impact objects and identified business rules.

## Results mode
The user can navigate among:
- **Dashboard Geral** — synthesis and entry point;
- **Executive View** — risks, critical applications, macro recommendations, Clean Core distribution and roadmap;
- **Technical View** — objects, code, findings, evidence and remediation;
- **Functional View** — business rules, processes, applications, functional dependencies and validation of AI interpretation;
- **Architecture View** — applications, dependencies, coupling patterns, SAP guidance and modernization paths.

The four Views are presentation perspectives, not access roles. Dashboard Geral is a synthesis page.

## Universal exploration principle
**Explore visually. Ask naturally. Validate through evidence.**

The AI Copilot remains on the right and receives the current Assessment, stage/view, selected entity and source/evidence context. It may return navigable references to code, findings, rules, applications, dependencies or SAP guidance.
