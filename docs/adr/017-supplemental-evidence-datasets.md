# ADR-017 — Supplemental Evidence Datasets and Adapter-Based Import

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
The Assessment currently receives ABAP/source artifacts from the filesystem and ATC findings from a schema-tolerant XLSX import. Additional SAP landscape exports have now been validated as potentially valuable evidence sources:

- Panaya ETL export: very large XML containing technical landscape/object information, code and conversion/usage-related signals;
- SAP Signavio Process Insights discovery export: ZIP containing system metadata plus chunked process/KPI JSON datasets;
- FUE 4SAP User Validation export: ZIP containing user/role/object result binaries and a small metadata text file.

These inputs are not all SAP source code and must not be modeled as `SAPObject`. They also should not each introduce an isolated persistence model or a separate analysis pipeline.

## Decision
Introduce an Assessment-scoped **Supplemental Evidence Dataset** model with adapter-based import.

### Canonical concepts
1. `EvidenceDataset` — one imported supplemental evidence package/version.
2. `EvidenceArtifact` — physical artifact/member belonging to the dataset (ZIP, XML, JSON, BIN, metadata file).
3. `EvidenceRecord` — a normalized evidence unit extracted by an adapter, with provenance and optional raw payload.
4. `EvidenceCorrelation` — explicit relationship from an evidence record to a canonical entity such as `SAPObject`, `Application`, `BusinessRule`, or a process/usage entity introduced later.

The existing `Evidence` entity remains the explainability/proof object used by findings and recommendations. `EvidenceDataset`/`EvidenceRecord` describe imported evidence material; selected records can be promoted/referenced as `Evidence` when they support a conclusion.

### Supported dataset types for the PoC
- `PANAYA_ETL`
- `SIGNAVIO_PROCESS_INSIGHTS`
- `FUE_USER_VALIDATION`
- `OTHER` reserved for future adapters

### Adapter contract
Each adapter must expose the same lifecycle:

```text
inspect → validate → import/stream → normalize → correlate → summarize
```

Adapters own format-specific parsing only. Domain analysis consumes canonical normalized records/capabilities, never Panaya/Signavio/FUE parser internals.

### Capability-oriented normalization
A dataset advertises discovered capabilities rather than forcing all sources into one rigid row schema. Initial capability names include:

- `TECHNICAL_OBJECT_METADATA`
- `SOURCE_CODE`
- `DEPENDENCY_SIGNAL`
- `S4_CONVERSION_SIGNAL`
- `USAGE_SIGNAL`
- `PROCESS_KPI`
- `BUSINESS_PROCESS_SIGNAL`
- `USER_SIGNAL`
- `ROLE_SIGNAL`
- `AUTHORIZATION_SIGNAL`

Missing capabilities are valid and must not fail an otherwise readable dataset.

## Format-specific decisions
### Panaya ETL
- Must use streaming XML parsing; loading the complete XML into memory is prohibited.
- The original package/artifact is fingerprinted and retained by reference; the application does not duplicate the full 2.8 GB XML in PostgreSQL.
- Persist normalized records and compact provenance locators such as XML section, object key, member name and source hash.
- Import may be incremental/resumable by logical section/batch.
- Panaya-derived code may enrich/corroborate source collection, but direct SAP/PyRFC collection remains the preferred target ingestion path for canonical source acquisition.

### Signavio Process Insights
- Read package/system metadata and chunked JSON datasets.
- Preserve `keyFigureId`, dataset/service identity, timestamp, header definition and source member provenance.
- Normalize process/KPI observations without assuming a fixed catalogue of key figures.
- Process evidence enriches business importance/context; it does not by itself prove that a specific custom object caused a process outcome.

### FUE User Validation
- Treat the package as supported evidence input, but binary decoding is adapter-specific and must be capability-gated.
- Metadata/manifest import must succeed even if one or more `.bin` payloads cannot yet be decoded safely.
- Do not infer user/object relationships from opaque binary bytes.
- Once a reliable decoder/profile is available, normalize user/role/object relationships into usage/access signals with provenance.

## Stable SAP object identity
The existing parse behavior that deletes/recreates `SAPObject` rows is no longer acceptable once ATC and multiple supplemental datasets correlate to those rows. Before external evidence correlations are relied upon, SPRINT-08 must establish stable Assessment-scoped object identity (deterministic canonical key + upsert/reconciliation) or an equivalently deterministic re-correlation mechanism. The preferred PoC direction is stable identity with re-correlation only when matching attributes materially change.

## Correlation
Correlation is explicit and scored/statused. Initial statuses:
- `MATCHED_EXACT`
- `MATCHED_HEURISTIC`
- `UNMATCHED`
- `AMBIGUOUS`
- `NOT_APPLICABLE`

Correlations may use object name/type/package, transaction, program/include relationships, technical keys or other adapter-provided canonical identifiers. AI may assist with interpretation after deterministic candidates exist, but AI must not fabricate correlations.

## Pipeline decision
Supplemental evidence import occurs after canonical source parsing is available and before downstream AI intelligence consumes evidence. It is implemented as durable import/correlation work and feeds the same Assessment evidence graph.

The target flow becomes:

```text
Source acquisition/parsing
        + ATC
        + Supplemental evidence datasets
                  ↓
       correlation / evidence graph
                  ↓
 Object Understanding → Business Rules → Applications
                  ↓
 SAP Knowledge → Clean Core → Recommendations
```

## UI decision
Do not add a fourth top-level Clean Core step. Supplemental evidence is managed inside **1 - Ingestão dos dados** as an optional section named **Fontes complementares / Evidências adicionais**. ATC remains the dedicated Step 2 because it already has a specialized user journey and domain contract.

## Consequences
### Positive
- New evidence providers can be added without changing `SAPObject` or the core AI stages.
- Business/process/usage context can influence business importance and retirement/modernization analysis.
- Provenance and correlation remain explicit.
- Existing completed sprints and current source/ATC implementation remain valid.

### Trade-offs
- Adds generic evidence-dataset persistence and adapter contracts.
- Large files require streaming, resumability and bounded raw-data persistence.
- Some providers, especially FUE binary payloads, may initially provide only partial capabilities.

## Delivery impact
A new **SPRINT-08 — Supplemental Evidence Foundation** is inserted before AI Object Understanding. Previous future sprints 08–16 are shifted to 09–17. Completed sprints 00–07 are not renumbered or rewritten historically.
