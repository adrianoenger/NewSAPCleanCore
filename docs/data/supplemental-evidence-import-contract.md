# Supplemental Evidence Import Contract

## Purpose
Define the canonical contract for optional Assessment evidence packages such as Panaya ETL, SAP Signavio Process Insights and FUE 4SAP User Validation.

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
- `dataset_type` (`PANAYA_ETL`, `SIGNAVIO_PROCESS_INSIGHTS`, `FUE_USER_VALIDATION`, `OTHER`);
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

## Panaya profile
- ZIP with a primary XML artifact.
- Parse with an iterative/streaming XML strategy and release processed elements.
- Batch commits/checkpoints are required for large files.
- Initial extraction priorities: technical object metadata, source/code sections where available, dependencies/where-used, usage signals, S/4 conversion/simplification/code-inspection signals.
- Do not make the complete Panaya schema a hard dependency of the domain model; map recognized sections into capability-specific records and preserve unknown section statistics/warnings.

## Signavio Process Insights profile
- ZIP containing system XML metadata and many chunked JSON files.
- Group chunks by `keyFigureId`/dataset identity without requiring a fixed list of key figures.
- Preserve service/system identity, timestamp, header and member name.
- Normalize KPI/process observations as process evidence.
- Large repeated chunks should be processed incrementally.

## FUE User Validation profile
- ZIP containing a metadata `.txt` plus `.bin` payloads such as user, role and object result data.
- Fingerprint and register all artifacts even when binary decoding is unavailable.
- Decoder support is version/profile-specific and must fail partially, never by guessing the binary schema.
- When decoding is supported, normalize user/role/object access or usage relationships with provenance.

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
