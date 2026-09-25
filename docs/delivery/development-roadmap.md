# Development Roadmap

The PoC is built through sequential, cumulative sprints. Each sprint leaves an executable and demonstrable product increment. The canonical lifecycle is defined in `sprint-execution-model.md`.

The 2026-09-24 product correction inserted Sprint 04 before further analysis work. On 2026-09-25, before AI work started, ADR-017 inserted Sprint 08 for supplemental evidence foundations. Completed Sprints 00–07 retain their numbers; former future Sprints 08–16 were shifted to 09–17. **Baseline R3.3** is canonical; obsolete pre-shift files must not coexist in `docs/delivery/sprints/`.

| Sprint | Canonical definition | Theme | Demonstrable outcome |
|---|---|---|---|
| 00 | `SPRINT-00-engineering-foundation.md` | Engineering Foundation | Dev Container, services, backend/frontend shell, migration foundation and health path run |
| 01 | `SPRINT-01-client-sap-system-and-assessment.md` | Historical Client/System/Assessment increment | Historical implementation record; hierarchy is superseded by ADR-015 |
| 02 | `SPRINT-02-source-ingestion.md` | Source Ingestion | Select/scan directory and persist fingerprinted files; UI default-path behavior corrected in Sprint 04 |
| 03 | `SPRINT-03-sap-object-parsing.md` | SAP Object Parsing | Build and browse normalized SAP object catalog |
| 04 | `SPRINT-04-assessment-centric-product-alignment.md` | Assessment-Centric Product Alignment | Migrate to Client → Assessment, new Assessments Home, conditional sidebar, blank Source Ingestion selection and staged navigation |
| 05 | `SPRINT-05-dependencies-atc-and-technical-findings.md` | Dependencies & ATC | Import schema-tolerant ATC `.xlsx`, browse dependencies and deterministic findings |
| 06 | `SPRINT-06-durable-pipeline-execution.md` | Durable Pipeline | Pause/resume/recover/retry stage processing |
| 07 | `SPRINT-07-consolidate-processing-flow.md` | Consolidate Processing Flow | Ingestion, ATC import and durable processing form one coherent 3-step Assessment flow with no duplicate scanning |
| 08 | `SPRINT-08-supplemental-evidence-foundation.md` | Supplemental Evidence Foundation | Import Panaya/Signavio/FUE evidence through adapters, normalize/correlate it and preserve provenance |
| 09 | `SPRINT-09-ai-object-understanding.md` | Object Understanding | Provider-agnostic AI produces validated functional/technical object understanding using canonical evidence |
| 10 | `SPRINT-10-business-rule-discovery.md` | Business Rule Discovery | Browse evidence-bound rules with confidence and validation hooks |
| 11 | `SPRINT-11-application-discovery.md` | Application Discovery | Browse functional applications composed of related objects/rules |
| 12 | `SPRINT-12-sap-knowledge-mcp.md` | SAP Knowledge MCP | Findings/applications show contextual SAP/ABAP guidance |
| 13 | `SPRINT-13-clean-core-intelligence.md` | Clean Core Intelligence | Risk, business importance and recommendation with technical + process/usage evidence where available |
| 14 | `SPRINT-14-embeddings-and-semantic-retrieval.md` | Embeddings & Semantic Retrieval | Semantic search works within Assessment boundaries |
| 15 | `SPRINT-15-navigation-perspectives.md` | Navigation Perspectives | Dashboard Geral + Executive/Technical/Functional/Architecture views over the same Assessment |
| 16 | `SPRINT-16-ai-copilot.md` | AI Copilot | Permanent contextual chat routes across facts, semantic data, source, supplemental evidence and MCP |
| 17 | `SPRINT-17-demo-readiness.md` | Demo Readiness | Refined UX, graphs, code explorer, reference Assessment and end-to-end journey |

## Sequence invariant
- Exactly one canonical sprint definition exists for each sprint number 00–17.
- A future sprint may be renumbered only by updating the roadmap, filename, document title and all cross-references in the same documentation change.
- Obsolete pre-renumbering sprint files must be deleted rather than retained alongside the new sequence.
- Progress files live in `docs/delivery/sprints/` and use `SPRINT-XX-PROGRESS.yaml`.
- `EXECUTION_STATE.yaml` is the operational source for the completed/current/next sprint; roadmap numbering never overrides a completed historical result.

## Delivery invariant
`run/resume → review → validate as needed → finish → one commit on main → branch removed`

A sprint may be split only if the increment becomes too large to remain testable and demonstrable. A split is a planning change and must be reflected in canonical documentation before implementation proceeds.
