# Functional Capabilities

## Core entities
Client → Assessment → Source Files → SAP Objects + Supplemental Evidence Datasets → Evidence → ATC/Technical Findings → Business Rules → Applications → Clean Core Assessments → Recommendations.

`SAP source system` is Assessment metadata, not an independently managed entity.

## Main capabilities
1. Manage multiple clients and assessments.
2. List/filter all assessments from the application home.
3. Create a simple Client and create an Assessment linked to a Client.
4. Store SAP source system as Assessment metadata.
5. Explicitly select and scan a large local source directory; no default source path.
6. Classify and fingerprint files for incremental reprocessing.
7. Parse SAP artifacts into a normalized object catalog.
8. Import variable-layout `.xlsx` ATC reports, preserve raw evidence, map available fields dynamically and link findings to Assessment objects when possible.
9. Import optional supplemental evidence packages through adapter-based, provenance-preserving ingestion (initially Panaya ETL, SAP Signavio Process Insights and FUE User Validation).
10. Correlate technical, process, usage and user/role evidence to canonical Assessment entities without fabricating ambiguous relationships.
11. Discover deterministic object dependencies and technical findings.
12. Run provider-agnostic AI processing using Bedrock or Azure AI Foundry adapters.
13. Discover and consolidate business rules.
14. Discover functional applications from object clusters.
15. Retrieve SAP/ABAP guidance from MCP providers.
16. Produce evidence-based Clean Core risk and recommendation outputs.
17. Create embeddings for semantically meaningful entities.
18. Show a preliminary KPI summary after processing.
19. Expose Dashboard Geral plus Executive, Technical, Functional and Architecture result views.
20. Allow contextual AI questions over SQL facts, semantic knowledge, source evidence, supplemental evidence and SAP MCP guidance.
21. Pause, resume, retry and recover long-running processing.
22. Keep the AI Copilot available on the right across the entire application.
