# Persistence Model

## Database
PostgreSQL + pgvector through SQLAlchemy. Schema evolution uses Alembic migrations.

## Canonical ownership

```text
client 1 ───── N assessment
assessment 1 ───── N source_scan / source_file / sap_object / atc_run / ...
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
