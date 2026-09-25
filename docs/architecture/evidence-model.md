# Evidence and Explainability Model

## Principle
No important Clean Core conclusion should exist without traceable supporting evidence.

## Evidence types
- `SOURCE_CODE`
- `ATC`
- `DEPENDENCY`
- `SAP_DOCUMENTATION`
- `BUSINESS_RULE`
- `METADATA`
- `USAGE`
- `BUSINESS_PROCESS`
- `USER_ROLE`
- `S4_CONVERSION`
- `AI_INTERPRETATION` (context only; not authoritative fact)

## Provenance
Examples: `PARSER`, `ATC_IMPORT`, `PANAYA_ETL_IMPORT`, `SIGNAVIO_PROCESS_INSIGHTS_IMPORT`, `FUE_USER_VALIDATION_IMPORT`, `DEPENDENCY_ANALYZER`, `AI_OBJECT_ANALYSIS`, `MCP_SAP_DOCS`, `MCP_ABAP`, `USER`.

## Distinction
- **Fact:** observable/retrievable information.
- **Inference:** interpretation derived from facts.
- **Recommendation:** proposed action based on evidence and inference.

AI output alone must not be treated as sufficient factual evidence for high-confidence technical conclusions.

## Traceability chain
Recommendation → Clean Core Assessment → Findings/Business Rules/SAP Guidance → Evidence → (`SAPObject` and/or `EvidenceRecord`) → source file/dataset/artifact + source locator.

## UI expectation
Every recommendation/finding should support drill-down to the evidence that supports it, including source lines and SAP guidance when available.

## Imported evidence datasets
`EvidenceDataset`, `EvidenceArtifact` and `EvidenceRecord` preserve imported supplemental material separately from the canonical `Evidence` used to justify findings and recommendations. A conclusion may reference selected imported records through `Evidence` without treating every imported row/element as a first-class finding.

Provider-specific records are normalized by capability and correlated explicitly to canonical entities. Correlation status must remain visible (`MATCHED_EXACT`, `MATCHED_HEURISTIC`, `UNMATCHED`, `AMBIGUOUS`, `NOT_APPLICABLE`). See ADR-017 and `docs/data/supplemental-evidence-import-contract.md`.
