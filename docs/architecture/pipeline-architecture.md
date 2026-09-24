# Assessment Pipeline Architecture

## Canonical stages
1. `SOURCE_SCAN`
2. `SOURCE_CLASSIFICATION`
3. `SAP_OBJECT_PARSING`
4. `DEPENDENCY_ANALYSIS`
5. `ATC_IMPORT`
6. `TECHNICAL_FINDINGS`
7. `OBJECT_UNDERSTANDING`
8. `BUSINESS_RULE_DISCOVERY`
9. `APPLICATION_DISCOVERY`
10. `SAP_KNOWLEDGE_ENRICHMENT`
11. `CLEAN_CORE_ANALYSIS`
12. `RECOMMENDATIONS`
13. `EMBEDDINGS`
14. `AGGREGATIONS`

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
| Technical findings | SAP object |
| Object understanding | SAP object or structural chunk |
| Business rules | object/cluster |
| Application discovery | candidate cluster |
| SAP knowledge | finding/application query |
| Clean Core | object/application |
| Embeddings | semantic entity |

## Incrementality
Each source file records path, size, modified timestamp and SHA-256. Unchanged inputs should be reused. Changed inputs invalidate dependent derived outputs and enqueue only affected work when feasible.


## ATC import sub-pipeline
`ATC_IMPORT` is internally evidence-first and schema-tolerant:

```text
XLSX → sheet/header discovery → mapping snapshot → raw row preservation → canonical normalization → object correlation
```

Missing optional columns and unknown extra columns do not fail a readable report. Downstream ATC-dependent stages must branch on available normalized attributes and import warnings rather than assume every field exists. See `docs/data/atc-import-contract.md`.
