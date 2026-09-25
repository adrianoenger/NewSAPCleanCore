# SPRINT-08 — Supplemental Evidence Foundation

## Position in the sequence
- Prerequisite: SPRINT-07 completed.
- Coherence rule: This sprint extends the Assessment evidence model and durable pipeline; it does not implement AI Object Understanding yet.
- Architecture source: ADR-017 and `docs/data/supplemental-evidence-import-contract.md`.

## Goal
Introduce a provider-independent foundation for optional SAP landscape/process/usage evidence packages so downstream AI and Clean Core analysis can consume normalized, traceable evidence without coupling to Panaya, Signavio or FUE schemas.

## Planned capabilities
- Implement canonical persistence for `EvidenceDataset`, `EvidenceArtifact`, `EvidenceRecord` and `EvidenceCorrelation` with a forward Alembic migration.
- Implement `EvidenceDatasetAdapter` contract: inspect, validate, import/stream, normalize, correlate and summarize.
- Register supplemental evidence import/correlation in the existing durable pipeline engine; do not create a parallel job system.
- Add **Fontes complementares / Evidências adicionais** inside Step 1 — Ingestão dos dados, with dataset list, import status, detected capabilities, warnings and correlation summary.
- Implement Panaya ETL adapter foundation using bounded-memory streaming XML and checkpointable batches. Prioritize technical object metadata, source/code references, dependency/where-used, S/4 conversion/code-inspection and usage signals when present.
- Implement SAP Signavio Process Insights adapter for package metadata and chunked JSON, preserving `keyFigureId`, source member and header/system/timestamp provenance.
- Implement FUE User Validation package/manifest registration and capability-gated binary adapter. Decode only profiles that can be proven reliable; otherwise finish as partial with explicit unsupported-payload warnings.
- Stabilize Assessment-scoped `SAPObject` identity across reprocessing (canonical key + upsert/reconciliation or an equivalent proven mechanism) so ATC and supplemental evidence links do not silently break.
- Re-correlate existing ATC findings as required after the identity migration/reconciliation.
- Implement deterministic object-correlation service with `MATCHED_EXACT`, `MATCHED_HEURISTIC`, `UNMATCHED`, `AMBIGUOUS`, `NOT_APPLICABLE` states.
- Provide API/read models that let later stages query evidence by capability and target entity without knowing provider-specific schemas.
- Add compact dataset-level KPIs: records imported, capabilities found, exact/heuristic/unmatched/ambiguous correlations, warnings and importer version.

## Explicit constraints
- Do not load the full Panaya XML into memory.
- Do not persist full multi-gigabyte source contents in PostgreSQL.
- Do not model Panaya/Signavio/FUE records as `SAPObject` subclasses.
- Do not infer relationships from opaque FUE binary bytes.
- Do not make supplemental datasets mandatory for an Assessment.
- Direct SAP/PyRFC remains the preferred target path for canonical SAP source acquisition.
- ATC remains the dedicated Step 2 and keeps ADR-016 semantics.

## Demonstrable outcome
Open an Assessment → Step 1 → import a supported supplemental package → see its detected type/capabilities and durable import progress → inspect normalized evidence records and correlation summary → open a correlated SAP object and see supplemental evidence provenance linked to it.

For the FUE sample, a valid demonstration may be a `PARTIAL` import that registers package metadata/artifacts and explicitly reports unsupported binary decoding if a reliable decoder is not implemented in this sprint.

## Minimal validation
- Import one representative Panaya logical subset/fixture through the streaming path without unbounded memory growth.
- Import representative Signavio package/chunks and preserve key-figure/source provenance.
- FUE package inspection/partial-import behavior is deterministic and never guesses the binary schema.
- Persistence migration, stable SAPObject identity/reprocessing, dataset lifecycle and object-correlation contracts have focused tests.
- Existing Step 1 source ingestion, Step 2 ATC and Step 3 processing remain runnable.
- Do not add broad test coverage unrelated to these contracts.

## Completion criteria
- Canonical evidence-dataset model is persisted and documented.
- At least Panaya and Signavio adapters demonstrate normalized records with provenance.
- FUE adapter behavior is explicit and safe, whether full or partial.
- Existing durable engine executes supplemental import/correlation work.
- UI exposes optional evidence datasets without adding a fourth top-level Clean Core step.
- Progress/state files updated.
- Application remains runnable for SPRINT-09 AI Object Understanding.
