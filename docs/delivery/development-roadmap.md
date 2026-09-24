# Development Roadmap

The PoC is built through sequential, cumulative sprints. Each sprint leaves an executable and demonstrable product increment. The canonical lifecycle is defined in `sprint-execution-model.md`.

The 2026-09-24 product correction inserts a new Sprint 04 before further analysis work. Sprints that had not started were shifted by one number. Sprints 00–03 retain their historical numbers.

| Sprint | Theme | Demonstrable outcome |
|---|---|---|
| 00 | Engineering Foundation | Dev Container, services, backend/frontend shell, migration foundation and health path run |
| 01 | Historical Client/System/Assessment increment | Historical implementation record; hierarchy is superseded by ADR-015 |
| 02 | Source Ingestion | Select/scan directory and persist fingerprinted files; UI default-path behavior corrected in Sprint 04 |
| 03 | SAP Object Parsing | Build and browse normalized SAP object catalog |
| 04 | Assessment-Centric Product Alignment | Migrate to Client → Assessment, new Assessments Home, conditional sidebar, blank Source Ingestion selection and staged navigation |
| 05 | Dependencies & ATC | Import ATC `.xlsx`, browse dependencies and deterministic findings |
| 06 | Durable Pipeline | Pause/resume/recover/retry stage processing |
| 07 | Object Understanding | AI produces validated functional/technical object understanding |
| 08 | Business Rule Discovery | Browse rules with confidence and source evidence |
| 09 | Application Discovery | Browse functional applications composed of related objects/rules |
| 10 | SAP Knowledge MCP | Findings/applications show contextual SAP/ABAP guidance |
| 11 | Clean Core Intelligence | Risk, business importance and recommendation with evidence |
| 12 | Embeddings & Semantic Retrieval | Semantic search works within Assessment boundaries |
| 13 | Navigation Perspectives | Dashboard Geral + Executive/Technical/Functional/Architecture views over the same Assessment |
| 14 | AI Copilot | Permanent contextual chat routes across facts, semantic data, source and MCP |
| 15 | Demo Readiness | Refined UX, graphs, code explorer, reference Assessment and end-to-end journey |

## Delivery invariant
`run/resume → review → validate as needed → finish → one commit on main → branch removed`

A sprint may be split only if the increment becomes too large to remain testable and demonstrable. A split is a planning change and must be reflected in canonical documentation before implementation proceeds.
