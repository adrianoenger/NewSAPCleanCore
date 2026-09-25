# Supplemental Evidence Import Contract

## Purpose
Define the canonical contract for optional Assessment evidence packages such as Panaya ETL, SAP Signavio Process Insights, HANA Sizing Report and SAP Readiness Check. FUE 4SAP User Validation was evaluated against a real sample and dropped — see "FUE User Validation — dropped" below.

## Core rule
Imported packages are **evidence datasets**, not SAP objects. Their job is to enrich the Assessment evidence graph with technical, usage, process and organizational signals that downstream analysis can consume.

## Canonical import lifecycle

```text
package/file selection
  → fingerprint
  → adapter detection
  → manifest inspection
  → capability discovery
  → streaming/batched extraction
  → normalization
  → deterministic correlation
  → dataset summary
```

## `EvidenceDataset`
Recommended fields:
- `id`;
- `assessment_id`;
- `dataset_type` (`PANAYA_ETL`, `SIGNAVIO_PROCESS_INSIGHTS`, `HANA_SIZING_REPORT`, `SAP_READINESS_CHECK`, `OTHER`);
- `display_name`;
- `source_filename`;
- `source_sha256`;
- `source_size_bytes`;
- `importer_name` / `importer_version`;
- `status` (`INSPECTED`, `IMPORTING`, `IMPORTED_FULL`, `IMPORTED_PARTIAL`, `FAILED`);
- `source_system_hint` / `source_client_hint` when available;
- `extracted_at` when available;
- `capabilities` (`JSONB` array);
- `manifest` (`JSONB`);
- `warning_summary` (`JSONB`);
- timestamps.

Multiple datasets/runs may coexist in one Assessment. Re-importing a new version must not silently overwrite historical provenance.

## `EvidenceArtifact`
Recommended fields:
- `id`, `dataset_id`;
- `member_name` / logical path;
- media/format hint;
- size and optional hash;
- artifact role (`PRIMARY`, `METADATA`, `DATA_CHUNK`, `BINARY_PAYLOAD`, `OTHER`);
- optional storage/path reference.

For very large sources, keep the source as a referenced artifact. Do not persist the complete file bytes or complete XML as database JSON/text.

## `EvidenceRecord`
Recommended fields:
- `id`, `dataset_id`, optional `artifact_id`;
- `record_type`;
- `source_key` and `record_fingerprint`;
- `capability`;
- normalized identifiers (`object_name`, `object_type`, `package_name`, transaction/process/KPI/user/role keys as applicable);
- `normalized_payload JSONB`;
- optional bounded `raw_payload JSONB` when practical;
- `source_locator JSONB` for member/section/row/object-key provenance;
- confidence only where the source itself supplies or the normalization explicitly computes it;
- timestamps.

Raw payload persistence is optional for large/opaque formats. Provenance is mandatory.

## Correlation contract
`EvidenceCorrelation` should contain:
- `evidence_record_id`;
- `target_type`;
- `target_id` where a canonical persisted target exists;
- `status`;
- `method`;
- optional score;
- `rationale` / matched keys;
- timestamps.

No heuristic match may be represented as exact. Ambiguity is preserved.

Correlating a dataset must page through its `EvidenceRecord`s in id order rather than load all of
them as ORM objects at once — confirmed necessary: a real ~4.4M-record dataset pushed a
naive all-at-once correlation pass to ~20GB of process memory before this was fixed.

## Panaya profile
- Bare (unzipped) XML in real exports (~2.8GB confirmed); a ZIP-wrapped variant is also accepted.
- Parse with an iterative/streaming XML strategy and release processed elements.
- Sanitize illegal raw control bytes and illegal numeric XML character references before parsing — real exports are not always strictly well-formed XML (confirmed: literal control bytes and `&#0;`-style refs inside extracted source text).
- Batch commits/checkpoints are required for large files; one batch = one curated top-level section, since random access into a multi-gigabyte file isn't practical.
- Initial extraction priorities: technical object metadata, source/code sections where available, dependencies/where-used, usage signals, S/4 conversion/simplification/code-inspection signals.
- Do not make the complete Panaya schema a hard dependency of the domain model; map recognized sections into capability-specific records and preserve unknown section statistics/warnings. Given real exports can have single sections in the single-digit millions of rows, a curated section's import is capped with an explicit truncation warning rather than unbounded.

## Signavio Process Insights profile
- ZIP containing system XML metadata (ABAP-serialized `<asx:abap>`/`<item><KEY>/<VALUE>` pairs, not simple attributes) and many chunked JSON files.
- Each chunk's normalized content lives under a `"dataSet"` key (`keyFigureId`, `serviceName`/`serviceDescr`/`serviceType`, `timestamp`, `header`, `data` — the row array is `data`, not `rows`).
- Group chunks by `keyFigureId`/dataset identity without requiring a fixed list of key figures.
- Preserve service/system identity, timestamp, header and member name.
- Normalize KPI/process observations as process evidence.
- Large repeated chunks should be processed incrementally; a real export can have hundreds of chunks and millions of total rows, so persist rows via a chunked bulk `INSERT ... ON CONFLICT DO NOTHING` (never a per-row existence check) and correlate in id-ordered pages (never loading a whole dataset's records into memory at once).

## FUE User Validation — dropped
A real sample was inspected: the metadata `.txt` carries no usable structured data, and every
`.bin` payload is a proprietary, high-entropy compressed/encrypted format (~7.9 bits/byte Shannon
entropy; not zlib/gzip/bz2/lzma) with no available specification or decoder. Per this contract's
own rule ("never decode unknown binary layouts by guesswork"), there is no safe import path —
the adapter was removed rather than kept as a metadata-only stub with no real capability. See the
ADR-017 Removal amendment.

## HANA Sizing Report profile
- Plain-text `/SDF/HDB_SIZING`-style report; no ZIP wrapper.
- Recognize the report's ASCII box structure generically (rule lines, `|`-bordered rows, an inner header separator), not by hard-coded box titles.
- A box row whose first column matches a plausible SAP object name becomes a table-level `USAGE_SIGNAL` record with `object_name` set for correlation; other rows are dataset-level sizing metrics with no object correlation.
- Loose `label   value` lines outside any box populate dataset manifest metadata; `SID` becomes `source_system_hint`.

## SAP Readiness Check profile
- Official SAP-generated `.docx` report with a variable number of embedded tables.
- Classify each table by its header row text, never by table index — order/count is not guaranteed stable across report versions.
- Recognized kinds: system metadata (manifest only), Simplification Items / custom-code check summaries (`S4_CONVERSION_SIGNAL`, Assessment-level, no object correlation), table volume/sizing (`USAGE_SIGNAL`, correlatable to `SAPObject`).
- An unrecognized table is counted, never dropped silently or guessed at.

## Evidence promotion
An `EvidenceRecord` becomes support for a finding/recommendation through a canonical `Evidence` reference/projection. This keeps import storage separate from explainability while preserving traceability:

```text
Finding / Recommendation
        ↓
     Evidence
        ↓
EvidenceRecord
        ↓
EvidenceDataset / Artifact / Locator
```

## Security/privacy note
User-level evidence can contain personally identifiable information. For the PoC, ingest only fields required for usage/role correlation, avoid exposing personal user details in executive views, and keep raw user payload visibility restricted to technical evidence screens.
