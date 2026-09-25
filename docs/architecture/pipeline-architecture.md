# Assessment Pipeline Architecture

## Canonical stages
1. `SOURCE_SCAN`
2. `SOURCE_CLASSIFICATION`
3. `SAP_OBJECT_PARSING`
4. `DEPENDENCY_ANALYSIS`
5. `ATC_IMPORT`
6. `SUPPLEMENTAL_EVIDENCE_IMPORT`
7. `EVIDENCE_CORRELATION`
8. `TECHNICAL_FINDINGS`
9. `OBJECT_UNDERSTANDING`
10. `BUSINESS_RULE_DISCOVERY`
11. `APPLICATION_DISCOVERY`
12. `SAP_KNOWLEDGE_ENRICHMENT`
13. `CLEAN_CORE_ANALYSIS`
14. `RECOMMENDATIONS`
15. `EMBEDDINGS`
16. `AGGREGATIONS`

## Principle
Facts are extracted deterministically first. AI interprets facts later. SAP MCPs provide external guidance only where relevant.

## Work granularity examples
| Stage | Work item |
|---|---|
| Scan | directory batch |
| Classification | source file |
| Parsing | source file |
| Dependencies | SAP object |
| ATC | workbook/sheet/import row batch |
| Supplemental evidence | dataset artifact / logical section / record batch |
| Evidence correlation | evidence-record batch or target entity |
| Technical findings | SAP object |
| Object understanding | SAP object or structural chunk |
| Business rules | object/cluster |
| Application discovery | candidate cluster |
| SAP knowledge | finding/application query |
| Clean Core | object/application |
| Embeddings | semantic entity |

## Incrementality
Each source file and supplemental evidence package records stable provenance/fingerprint information. Unchanged inputs should be reused. Changed inputs invalidate dependent derived outputs and enqueue only affected work when feasible. Large supplemental files must support bounded-memory parsing and checkpointable batches.


## ATC import sub-pipeline
`ATC_IMPORT` is internally evidence-first and schema-tolerant:

```text
XLSX → sheet/header discovery → mapping snapshot → raw row preservation → canonical normalization → object correlation
```

Missing optional columns and unknown extra columns do not fail a readable report. Downstream ATC-dependent stages must branch on available normalized attributes and import warnings rather than assume every field exists. See `docs/data/atc-import-contract.md`.


## Supplemental evidence sub-pipeline
Optional evidence packages follow a provider-independent contract:

```text
package/file → fingerprint → adapter detection → inspect/validate → streaming/batched normalize → correlate → summarize
```

Initial adapters: `PANAYA_ETL`, `SIGNAVIO_PROCESS_INSIGHTS`, `FUE_USER_VALIDATION`. Adapters emit capability-oriented `EvidenceRecord` data; downstream AI stages consume canonical evidence/correlations and must not branch on provider-specific schemas. Panaya XML must be streamed; Signavio JSON chunks are processed incrementally; FUE binary decoding is version/profile-gated and may complete partially without fabricated data.

The durable execution engine from ADR-005 remains the execution mechanism. Supplemental evidence import/correlation must register as stages/work rather than introduce a parallel job system.
