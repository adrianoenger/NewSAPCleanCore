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
- `AI_INTERPRETATION` (context only; not authoritative fact)

## Provenance
Examples: `PARSER`, `ATC_IMPORT`, `DEPENDENCY_ANALYZER`, `AI_OBJECT_ANALYSIS`, `MCP_SAP_DOCS`, `MCP_ABAP`, `USER`.

## Distinction
- **Fact:** observable/retrievable information.
- **Inference:** interpretation derived from facts.
- **Recommendation:** proposed action based on evidence and inference.

AI output alone must not be treated as sufficient factual evidence for high-confidence technical conclusions.

## Traceability chain
Recommendation → Clean Core Assessment → Findings/Business Rules/SAP Guidance → Evidence → SAP Object → Source File + source range.

## UI expectation
Every recommendation/finding should support drill-down to the evidence that supports it, including source lines and SAP guidance when available.
