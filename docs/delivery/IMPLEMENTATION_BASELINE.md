# Implementation Baseline

**Baseline:** 2026-09-25-R3.3  
**Supersedes:** 2026-09-24-R3.2

## Purpose
This document is the implementation contract for the SAP Clean Core Analysis PoC. Claude Code must implement the architecture and product behavior described here and in accepted ADRs. Historical sprint result files describe what was built at that time; they do not override this baseline.

## Target runtime
- Electron + React desktop application on host.
- FastAPI/Python backend in Dev Container.
- PostgreSQL + pgvector.
- SQLAlchemy with Alembic for schema evolution.
- local filesystem assessment source mounted/accessible to backend.
- optional supplemental evidence packages (Panaya ETL, SAP Signavio Process Insights, FUE User Validation, HANA Sizing Report, SAP Readiness Check) imported through adapter-based ingestion.
- optional local Docker MCPs: `mcp-sap-docs`, `mcp-abap`.
- LLM providers: AWS Bedrock and Azure AI Foundry through adapters.

## Canonical product hierarchy

```text
Client 1 ───────────── N Assessment

Client
  ├── id
  ├── name
  └── description

Assessment
  ├── id
  ├── client_id
  ├── name
  ├── sap_source_system
  ├── description
  ├── status
  ├── ingestion
  │    └── supplemental_evidence (optional)
  ├── atc_analysis
  ├── ai_processing
  └── results
```

There is **no independently managed `SAPSystem` entity** in the target model. The source SAP system is an Assessment attribute named conceptually `sap_source_system`.

## Canonical user flow

```text
Assessments Home
   ↓
Open/Create Assessment
   ↓
1. Ingestão dos dados
   ↓
2. Análise ATC
   ↓
3. Processamento por IA
   ↓
Preliminary result summary
   ↓
Dashboard Geral + Executive / Technical / Functional / Architecture Views
```

### Assessments Home
- First application screen after startup.
- Grid/list of all assessments.
- Filter by Client and Assessment; additional lightweight filters such as status are allowed.
- `Novo Assessment` and `Novo Cliente` actions.
- No left sidebar.
- Permanent right-side AI Copilot remains available.

### Assessment creation
A new Assessment requires:
- pre-registered Client;
- Assessment name;
- SAP source system;
- description.

Client initially contains only generated id, name and description.

### Assessment workspace navigation
The left sidebar appears **only after an Assessment is opened**:

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

Current Client / Assessment must remain visible in the workspace context.

## Source Ingestion rule
The source-ingestion step has two complementary inputs:
1. canonical SAP/source artifact acquisition and parsing;
2. optional supplemental evidence datasets.

Direct SAP/RFC/PyRFC remains the target canonical collection path for SAP source artifacts. Supplemental datasets enrich the Assessment and must not silently replace canonical source acquisition.

- Source directory field starts blank.
- No default path is shown or implicitly selected.
- `Start Scan` starts disabled.
- It becomes enabled only after explicit selection of a valid directory.
- Directory selection does not automatically start scanning.
- Backend safety boundaries/path mapping may exist, but they must not appear as a user-selected default directory.

## ATC Analysis
- User imports an `.xlsx` ATC report.
- The XLSX is a **semi-structured source**, not a fixed-column contract.
- Discover candidate worksheet/header structure at runtime; do not depend permanently on sheet name, column order or the reviewed 21-column sample.
- Known columns are mapped by normalized header/explicit aliases. Missing optional columns are accepted with warnings; unknown extra columns are preserved.
- Preserve original headers and each imported row as raw evidence before canonical normalization.
- Persist a per-run mapping/header snapshot and importer/profile version.
- Canonical ATC finding attributes are nullable when the source column/value is unavailable.
- Support successful `FULL` and `PARTIAL` imports; reject only files whose structure cannot be read reliably.
- Placeholder/sentinel handling is field/profile-aware. Never treat values such as `25` as a universal null token.
- Checks, SAP Notes, packages and related catalogs are data-driven; counts observed in one sample are not schema invariants.
- Multiple ATC runs may coexist inside one Assessment and must not overwrite one another.
- ATC findings complement source/object analysis; they do not replace ingestion.
- Findings are later correlated to parsed SAP objects and technical evidence. Ambiguous/unavailable correlation remains explicit rather than fabricated.

The canonical import behavior is defined in `docs/data/atc-import-contract.md` and ADR-016.

## Supplemental Evidence
Inside **1 - Ingestão dos dados**, the user may optionally import complementary evidence packages. The supported profiles are Panaya ETL, SAP Signavio Process Insights, FUE User Validation, HANA Sizing Report and SAP Readiness Check.

Canonical rules:
- model each package/version as an Assessment-scoped `EvidenceDataset`;
- keep physical members as `EvidenceArtifact` and normalized units as `EvidenceRecord`;
- correlate records explicitly through `EvidenceCorrelation`;
- keep provider-specific schemas inside adapters; downstream analysis queries capabilities/canonical records;
- preserve source hash, importer version, source locator and warnings;
- allow `FULL` or `PARTIAL` imports when only a subset of capabilities is supported;
- Panaya XML must be streamed/batched and must not be fully loaded into memory or copied wholesale into PostgreSQL;
- Signavio chunked JSON must preserve key-figure/system/timestamp/member provenance and must not assume a fixed key-figure catalogue;
- FUE binary payloads are decoder/profile-gated; unreadable/unknown binary structures remain explicit and are never guessed;
- supplemental evidence is optional and never creates new `SAPObject` subtypes.

The canonical behavior is defined by ADR-017 and `docs/data/supplemental-evidence-import-contract.md`.

## AI Processing
AI processing consumes persisted ingestion/parsing/ATC data plus any available supplemental evidence/correlations and progressively performs:
- object understanding;
- customisation identification;
- ATC interpretation;
- dependency and application discovery;
- business-rule discovery;
- interpretation of process, usage and user/role signals where reliably correlated;
- Clean Core analysis and recommendations;
- embeddings / semantic indexing;
- result aggregation for dashboards and Copilot.

Persistable AI output must remain structured, validated, evidence-bound and provider-agnostic. AWS Bedrock and Azure AI Foundry are supported behind the existing provider abstraction.

## Preliminary processing summary
At completion, show KPI cards based on real Assessment data, including at minimum:
- Objetos analisados;
- Customizações identificadas;
- Findings críticos;
- Objetos com alto impacto;
- Regras de negócio identificadas.

## Result views
### Dashboard Geral
Cross-perspective synthesis and navigation entry point. It must not duplicate Executive View.

### Executive View
- risks;
- critical applications;
- macro recommendations;
- Clean Core distribution;
- suggested roadmap.

### Architecture View
- applications;
- dependencies;
- coupling patterns;
- SAP guidance;
- modernization paths.

### Technical View
- objects;
- code;
- findings;
- evidence;
- remediation proposal.

### Functional View
- business rules;
- processes;
- applications;
- functional dependencies;
- validation/correction of AI interpretation.

User validation must distinguish AI interpretation, supporting evidence, user-validated content and user-corrected content.

## Permanent AI Copilot
The right side is permanently dedicated to the AI Copilot, including Assessments Home and every Assessment view. Inside an Assessment it receives, when applicable:
- Client and Assessment;
- current stage/view;
- selected objects/findings/rules/applications/code ranges;
- ATC context;
- evidence and recommendations;
- current filters/selections.

The Copilot may navigate or suggest UI actions through controlled structured actions, but never mutates assessment state without explicit user action.

## Canonical processing flow
Assessment → Source Acquisition/Scan → Classification → Parsing → Dependencies + ATC + Supplemental Evidence Import → Evidence Correlation → Technical Findings → Object Understanding → Business Rules → Applications → SAP Knowledge → Clean Core → Recommendations → Embeddings → Aggregations → Dashboards/Explorer/Copilot.

## Core product rules
1. Multiple Clients and Assessments are supported; one Client can own many Assessments.
2. `SAPSystem` is not an independent target entity; SAP source system is an Assessment attribute.
3. Source files and SAP objects are distinct entities.
4. Deterministic facts precede AI interpretation.
5. Long-running stages use durable work items.
6. Pipeline supports pause/resume/retry/recovery.
7. AI persistable outputs are structured and evidence-bound.
8. Clean Core output separates Technical Risk, Business Importance and Recommendation.
9. Supplemental provider schemas remain behind adapters; downstream domain logic consumes canonical evidence capabilities/correlations.
10. Large evidence packages use streaming/batched processing with bounded persistence; raw multi-GB payloads are referenced, not duplicated in the database.
11. Process/usage/user-role signals may inform Business Importance but do not prove causality without a valid correlation chain.
12. SAP object identity used by ATC/evidence correlations must remain stable across reprocessing, or correlations must be deterministically rebuilt before downstream use.
13. SAP MCP evidence is external authoritative context; it is not copied indiscriminately into local RAG.
14. Embeddings represent meaningful semantic entities with Assessment metadata.
15. Results expose Dashboard Geral plus four perspectives: Executive, Technical, Functional and Architecture.
16. Right-side Copilot is permanently available and context-aware.
17. Chat may route to SQL, semantic search, source retrieval, supplemental evidence retrieval and MCP.

## Canonical delivery rules
1. Sprints execute sequentially and cumulatively.
2. Every sprint leaves a runnable and demonstrable increment.
3. One sprint uses one canonical sprint branch and exactly one official commit.
4. `/clean-core-run-sprint` initializes or resumes; it never commits or formally closes the sprint.
5. `/clean-core-review-sprint` is read-only.
6. `/clean-core-finish-sprint` is the only closure path and updates status/result documentation before the official commit.
7. Accepted architecture must not be changed silently.
8. Historical sprint result documents never override a newer accepted baseline/ADR.

## PoC acceptance narrative
A successful final demonstration should allow a user to:
1. open the application directly on the Assessments Home;
2. filter assessments by client/name and create a simple client or assessment;
3. open an assessment and see its assessment-only sidebar;
4. explicitly select a source directory and start ingestion;
5. optionally import one or more supplemental evidence packages and inspect capability/correlation summaries;
6. import an ATC `.xlsx` report;
7. run durable AI processing with visible progress and recovery;
8. see preliminary processing KPIs;
9. explore Dashboard Geral and Executive, Technical, Functional and Architecture views;
10. navigate from recommendations/findings/rules back to source, ATC or supplemental evidence;
11. ask the permanently available Copilot questions about the current context.
