# ADR-017 — Supplemental Evidence Datasets and Adapter-Based Import

- **Status:** Accepted
- **Date:** 2026-09-25

## Context
The Assessment currently receives ABAP/source artifacts from the filesystem and ATC findings from a schema-tolerant XLSX import. Additional SAP landscape exports have now been validated as potentially valuable evidence sources:

- Panaya ETL export: very large XML containing technical landscape/object information, code and conversion/usage-related signals;
- SAP Signavio Process Insights discovery export: ZIP containing system metadata plus chunked process/KPI JSON datasets;
- FUE 4SAP User Validation export: ZIP containing user/role/object result binaries and a small metadata text file — validated against a real sample and dropped; see the Removal amendment below.

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
- `HANA_SIZING_REPORT` (added post-completion, same SPRINT-08 — see Amendment below)
- `SAP_READINESS_CHECK` (added post-completion, same SPRINT-08 — see Amendment below)
- `OTHER` reserved for future adapters

`FUE_USER_VALIDATION` was validated against a real sample and dropped — see the Removal amendment below.

## Amendment (2026-09-25, still within SPRINT-08)
Two more evidence sources were validated against real customer exports (unlike Panaya/Signavio,
which had no reviewed sample when this ADR was accepted):

- **HANA Sizing Report** (`/SDF/HDB_SIZING` plain-text output): SAP database-memory/disk sizing
  results plus per-table volume/record-count breakdowns. A real, stable SAP report format.
- **SAP Readiness Check for SAP S/4HANA Conversion** (`.docx`): the official SAP-generated Word
  report — Simplification Items, custom-code check summaries, table volume/sizing, and system
  metadata, each in its own table. A real, stable SAP template.

Both fit the existing adapter contract and canonical model unchanged — no new persistence, no new
pipeline mechanism, same `EvidenceDatasetAdapter.detect/inspect/plan_batches/import_batch` lifecycle
as the original three. Per-table-volume rows correlate to `SAPObject` (DDIC tables) the same way
Panaya's technical-object rows do; Simplification Items and custom-code check rows are
Assessment-level context (`NOT_APPLICABLE` correlation), matching the evidence-model principle that
"process evidence enriches business importance/context; it does not by itself prove that a specific
custom object caused a process outcome" — the same reasoning already applied to Signavio.

### Adapter contract
Each adapter must expose the same lifecycle:

```text
inspect → validate → import/stream → normalize → correlate → summarize
```

Adapters own format-specific parsing only. Domain analysis consumes canonical normalized records/capabilities, never adapter-internal parser details.

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

**Amendment (2026-09-25, validated against a real ~2.8GB customer export):** the file is a bare
(unzipped) `.xml`, not wrapped in a ZIP as originally assumed — a ZIP-wrapped variant is still
accepted for defense in depth. The real structure is one `<ROOT_ELEMENT>` with a `<HEADER .../>`
(system metadata as attributes) and ~90 sibling sections (`<REPOSITORY_OBJECTS>`, `<PROGRAMS>`,
`<WHERE_USED_TABLE>`, `<SCI_HANA_ISSUES>`, ...), several in the single-digit millions of rows.
Two real, load-bearing findings the original (invented) profile never anticipated:
1. The file is not strictly well-formed XML — raw ABAP/text content carries both literal illegal
   control bytes and escaped illegal numeric character references (confirmed: a raw `0x1C` and
   `&#0;` for a NUL byte in a garbled field). Both abort `expat` with no way to resume; a
   streaming sanitizing wrapper (`evidence.adapters.base.SanitizingXMLStream`) strips both before
   the parser ever sees them.
2. Given the scale, importing every row of every section is not a PoC-appropriate goal. Only a
   curated subset of sections with a verified, correlatable attribute shape is extracted as
   `EvidenceRecord`s, each capped with an explicit truncation warning rather than an unbounded
   import; every section — curated or not — is still counted in the dataset manifest so nothing
   is invisible. Because random access into a multi-gigabyte XML isn't practical, each import
   batch = one curated section, re-streamed from the top and stopped as soon as that section's
   closing tag is consumed.

### Signavio Process Insights
- Read package/system metadata and chunked JSON datasets.
- Preserve `keyFigureId`, dataset/service identity, timestamp, header definition and source member provenance.
- Normalize process/KPI observations without assuming a fixed catalogue of key figures.
- Process evidence enriches business importance/context; it does not by itself prove that a specific custom object caused a process outcome.

**Amendment (2026-09-25, validated against a real ~28MB customer export):** the original profile
(`<SignavioSystem>`-rooted metadata, `keyFigureId`/`header`/`rows` as top-level JSON keys) did not
match reality in any particular — invented, like Panaya's, with no sample available at the time.
The real structure: system metadata is standard ABAP-serialized XML (`<asx:abap>` namespace,
`<HEADER_DATA><item><KEY>k</KEY><VALUE>v</VALUE></item>...>`), and every chunk's JSON lives under
a single `"dataSet"` key (`serviceName`/`serviceDescr`/`serviceType`/`keyFigureId`/`timestamp`/
`header`/`data` — the row array is `data`, not `rows`). Reading the invented shape against the
real one always found nothing, silently, under a non-failing status — which is why
`_evidence_import_finalize` now separately forces `IMPORTED_PARTIAL` (never `IMPORTED_FULL`) with
an explicit warning whenever an adapter reports capabilities but zero records were actually
extracted, a general safety net beyond this one adapter.

Scale findings from the real file (494 chunks, ~4.4M total rows, confirmed by full end-to-end
import): a per-row SELECT-then-INSERT existence check does not scale — fixed with a bulk
`INSERT ... ON CONFLICT DO NOTHING` (chunked to stay under PostgreSQL's 65535-bind-parameter
limit — a single real chunk alone can carry ~9600 rows). Correlating that many records also does
not scale if every `EvidenceRecord` for a dataset is loaded as an ORM object at once (confirmed:
pushed the backend container to ~20GB RSS) — `evidence.correlation.correlate_dataset_records` was
changed to page through records in id order (5000 at a time), never holding more than one page's
worth in memory. The full real file now imports and correlates end to end in ~15 minutes with
memory staying under ~350MB.

### FUE User Validation — dropped (Removal amendment, 2026-09-25, still within SPRINT-08)
Validated against a real customer export: the `.txt` member carries no usable structured data,
and every `.bin` member is a proprietary, high-entropy compressed/encrypted format (confirmed
~7.9 bits/byte Shannon entropy — indistinguishable from random noise; ruled out against
zlib/gzip/bz2/lzma, none decompress it) sharing one common unexplained header
(`\xff\x06\x02\x01\x02\x02\x80\x004103\x00\x00\x00\x00`) across all sampled files. No specification
or decoder is available. Per this ADR's own principle — "never fabricate correlations or decode
unknown binary layouts by guesswork" — there is no safe partial-import path left to implement:
decoding the `.bin` payload would mean guessing an undocumented binary schema. The adapter,
`EvidenceDatasetType.FUE_USER_VALIDATION`, and its tests were removed rather than kept as a
metadata-only stub with no real capability. If a specification or an official decoder becomes
available, FUE support can be reintroduced as a new adapter following the same contract.

### HANA Sizing Report
- Recognize the report's ASCII box structure generically (rule lines, `|`-bordered rows, an inner header separator) rather than hard-coding each box's title — box titles vary across SAP releases.
- Classify each data row structurally: a first column matching a plausible SAP object-name pattern becomes a table-level `USAGE_SIGNAL` record correlatable to a `SAPObject`; everything else becomes a dataset-level sizing metric with no object correlation.
- Loose `label   value` lines outside any box populate dataset manifest metadata (SID, NW release, DB type/version, ...); `SID` becomes `source_system_hint`.

### SAP Readiness Check
- Classify each embedded table by its header row text, never by table index — the table count/order is not guaranteed stable across SAP Readiness Check versions or customer configurations.
- Recognized kinds: system metadata (manifest/`source_system_hint` only, not persisted as records), Simplification Items and custom-code check summaries (`S4_CONVERSION_SIGNAL`, Assessment-level context, no object correlation), table volume/sizing (`USAGE_SIGNAL`, correlatable to `SAPObject` the same way the standalone HANA Sizing Report is).
- An unrecognized table is counted (`manifest.unrecognized_tables`), never dropped silently or guessed at.

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

**Amendment (2026-09-25, still within SPRINT-08):** `EvidenceCorrelation.target_id` is a
polymorphic column with no DB-level foreign key (it points at `SAPObject` today, and may point at
other canonical entity types once they exist), so it is never automatically nulled or refreshed by
the database when its target changes. Re-scanning/reprocessing source (Step 1 + Step 3) can add,
rename or remove `SAPObject` rows via the stable-identity reconciliation (CAP-001); without an
explicit re-correlation step, a removed object would leave a **dangling** correlation, and a
newly-added/renamed object would never be retroactively matched against evidence imported earlier.
`pipeline/stages.py::_parse_finalize` therefore re-runs `evidence.correlation.correlate_dataset_records`
for every `EvidenceDataset` of the assessment immediately after reconciling `SAPObject` rows —
automatic, not a separate user action. Deleting an `EvidenceDataset` needs no equivalent step:
its `EvidenceRecord`/`EvidenceCorrelation` rows are removed in the same DB-level cascade as the
dataset itself (see the delete endpoint), so nothing downstream can reference them afterward.

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
- A provider whose export turns out to be an undocumented binary format with no available decoder
  (FUE User Validation) may have no safe import path at all, not just a partial one.

## Delivery impact
A new **SPRINT-08 — Supplemental Evidence Foundation** is inserted before AI Object Understanding. Previous future sprints 08–16 are shifted to 09–17. Completed sprints 00–07 are not renumbered or rewritten historically.
