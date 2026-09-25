# Persistence Model

## Database
PostgreSQL + pgvector through SQLAlchemy. Schema evolution uses Alembic migrations.

## Canonical ownership

```text
client 1 ───── N assessment
assessment 1 ───── N source_scan / source_file / sap_object / atc_run / evidence_dataset / ...
```

### `client`
Minimum fields:
- `id` primary key;
- `name` required;
- `description` nullable;
- timestamps as needed.

### `assessment`
Minimum core fields:
- `id` primary key;
- `client_id` FK → `client.id`, indexed;
- `name` required;
- `sap_source_system` required for the initial workflow;
- `description` nullable;
- `status`;
- timestamps.

The canonical target model contains **no `sap_system` table**.

## Correcting the already-implemented schema
The implementation has already created an historical `sap_system` table and an `assessment.sap_system_id` relationship. Correct this through a **new forward Alembic migration**. Do not edit, delete or renumber previously applied migrations.

The corrective migration should, with the exact mechanics validated against the current schema:
1. add `assessment.client_id` if not already directly available;
2. add `assessment.sap_source_system`;
3. backfill `client_id` and `sap_source_system` from the existing `sap_system` relationship;
4. update constraints/indexes;
5. remove the obsolete `assessment.sap_system_id` FK after successful backfill;
6. drop the obsolete `sap_system` table only when no canonical runtime dependency remains.

For PoC development data, destructive handling of synthetic seed rows is acceptable only if migration safety and reproducibility remain clear. Migration history itself must remain forward-only.

## Assessment-scoped entities
Use `assessment_id` as the ownership boundary for relevant entities such as:
- `source_scan`;
- `source_file` (directly or via scan, while preserving Assessment queryability);
- `sap_object`;
- `atc_run` / `atc_finding`;
- evidence/findings;
- pipeline/stage/work items;
- AI analysis;
- business rules;
- applications;
- Clean Core assessments/recommendations;
- embeddings and aggregations.

## Stable SAP object identity
SPRINT-08 must resolve the existing reprocessing/correlation weakness before adding more external evidence links. `SAPObject.id` must not change merely because the same logical object is parsed again.

Recommended approach for the PoC:
- add a stable `canonical_key` (or equivalent unique semantic identity) scoped to `assessment_id`;
- derive it deterministically from normalized object type/name plus parent/subobject identity where required;
- parse/reprocess by upsert/reconciliation rather than unconditional delete/recreate;
- update the current source occurrence/location while retaining the stable object identity;
- mark/remove objects no longer present only after the current scan reconciliation is known complete;
- re-run exact/heuristic ATC and supplemental evidence correlation when identity-relevant attributes change.

This stable key is an internal correlation mechanism, not a globally portable SAP identifier.

## Variable ATC persistence contract
`atc_run` and `atc_finding` must not encode the reviewed Excel layout as a rigid database contract.

Recommended `atc_run` metadata includes:
- `assessment_id`;
- original filename and content hash;
- selected worksheet;
- original header snapshot (`JSONB`);
- resolved mapping snapshot (`JSONB`);
- unknown/missing known headers;
- importer/profile version;
- validation status (`ACCEPTED_FULL`, `ACCEPTED_PARTIAL`, `REJECTED` or equivalent);
- imported row count and warning/error summary;
- import timestamps and optional source execution metadata.

Recommended `atc_finding` storage combines:
- nullable canonical query columns (`priority`, `check_title`, `check_message`, object identity, SAP Note/reference/category fields, etc.);
- `source_row_number`;
- `raw_payload JSONB`;
- optional `normalized_payload JSONB`;
- row fingerprint;
- correlation status and optional linked `sap_object_id`;
- structured mapping/normalization warnings.

A missing Excel column therefore normally produces `NULL` canonical values plus run warnings rather than a migration or rejected import. Unknown columns remain in the raw payload. Catalog values such as ATC checks/packages/SAP Notes are discovered dynamically from imported data.

See `data/atc-import-contract.md` and ADR-016.

## Integrity rules
- Every Assessment belongs to exactly one Client.
- Deleting a Client may cascade to its Assessments only if the current PoC API explicitly allows destructive deletion; otherwise prefer restricted deletion.
- ATC/report data must never cross Assessment boundaries.
- Semantic retrieval is always Assessment-scoped by default.
- User validation/correction must retain provenance separate from AI-generated interpretation.

## Existing ingestion records
Existing source scan/file data remain conceptually valid. Their ownership follows the Assessment and must survive the hierarchy correction whenever reasonably possible.


## Supplemental evidence persistence
Add forward-only Alembic migrations when SPRINT-08 implements ADR-017. Recommended tables are:

### `evidence_dataset`
Assessment-scoped import run/package metadata: dataset type, filename/hash/size, importer/version, status, source-system/client hints, extraction timestamp, capability list, manifest and warnings.

### `evidence_artifact`
Dataset member metadata: logical/member name, artifact role, size/hash/media hint and optional storage/path reference. Large source bytes are not copied into PostgreSQL.

### `evidence_record`
Normalized evidence unit: record type/capability, source key/fingerprint, normalized payload, optional bounded raw payload and mandatory source locator. Add indexes only for fields needed by correlation/search in the PoC; avoid EAV-style over-modeling.

### `evidence_correlation`
Explicit relationship between an evidence record and a canonical target. Persist status, method, optional score and matched-key rationale. Heuristic matches must remain distinguishable from exact matches.

Provider-specific tables (`panaya_*`, `signavio_*`, `fue_*`) are not the default architecture. Introduce one only if a demonstrated query/performance requirement cannot be served by the canonical dataset/record model.
