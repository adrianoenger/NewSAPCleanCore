# Domain Model

## Aggregate hierarchy
- `Client`
  - `Assessment`
    - `PipelineRun`
    - `SourceScan`
    - `SourceFile`
    - `SAPObject`
    - `ATCRun` / `ATCFinding`
    - `EvidenceDataset` / `EvidenceArtifact` / `EvidenceRecord` / `EvidenceCorrelation`
    - `Evidence`
    - `Finding`
    - `BusinessRule`
    - `Application`
    - `CleanCoreAssessment`
    - `Recommendation`
    - `Embedding`

## Client
Minimal PoC entity:
- `id` — generated internal identifier;
- `name`;
- `description`.

A Client can own multiple Assessments.

## Assessment
Primary unit of work and persistence context. Suggested core fields:
- `id`;
- `client_id`;
- `name`;
- `sap_source_system` — descriptive identifier/name of the SAP source landscape used for this assessment;
- `description`;
- `status`;
- timestamps.

`SAPSystem` is **not** a separate target aggregate. Existing implementations that created such an entity are historical and must be migrated toward this model.

Suggested lightweight status semantics may cover `DRAFT`, `INGESTING`, `INGESTED`, `ATC_IMPORTED`, `AI_PROCESSING`, `READY`, `FAILED`. Exact persisted enum values may be refined during implementation without adding an enterprise workflow engine.

## Key distinctions
### SourceFile vs SAPObject
A file is a physical source. It may contain one or multiple SAP objects or subobjects. `SAPObject` references source location/range; file and object are never assumed to be equivalent.

### ATC
ATC import is an Assessment-scoped source of authoritative technical findings. An `ATCRun` identifies an imported report/version and owns `ATCFinding` records that may correlate to `SAPObject`.

The XLSX layout is variable. `ATCRun` therefore also owns import provenance such as source filename/hash, selected worksheet, original header snapshot, resolved header mapping, importer/profile version, validation status and warning summary. Multiple runs may coexist.

`ATCFinding` uses nullable canonical fields plus raw evidence. Recommended import-provenance fields include `source_row_number`, `raw_payload` (`JSONB`), optional `normalized_payload`, `row_fingerprint` and structured mapping warnings. Unknown source columns are preserved rather than discarded. Missing optional ATC columns do not invalidate the whole run.

Object correlation must remain explicit (`MATCHED_EXACT`, `MATCHED_HEURISTIC`, `UNMATCHED`, `AMBIGUOUS`) and Assessment-scoped.

### Supplemental evidence datasets
Optional landscape exports are modeled separately from `SourceFile` and `SAPObject`:
- `EvidenceDataset` identifies one imported package/version and its adapter, source hash, status, source-system hints, capabilities, manifest and warnings.
- `EvidenceArtifact` identifies physical members/files belonging to the dataset.
- `EvidenceRecord` stores normalized technical/process/usage/user-role signals plus mandatory source provenance.
- `EvidenceCorrelation` explicitly links a record to canonical entities with a correlation status/method; ambiguity is preserved.

Initial dataset types are `PANAYA_ETL`, `SIGNAVIO_PROCESS_INSIGHTS`, `FUE_USER_VALIDATION`, and `OTHER`. Provider-specific structure is confined to adapters and normalized payloads. No new Panaya/Signavio/FUE-specific aggregate is introduced.

`EvidenceRecord` is imported material; `Evidence` remains the explainability object referenced by findings, rules and recommendations. A selected `EvidenceRecord` can be referenced/promoted through `Evidence` while retaining dataset/artifact/locator provenance.

Process and usage evidence may inform `business_importance`, application discovery and retirement/modernization rationale, but it must not be treated as proof of causality between a custom object and a business KPI without a valid correlation chain.

### BusinessRule
Suggested fields:
- name, description, domain, rule type;
- condition, action, exception;
- confidence;
- validation state / user correction where applicable;
- related applications and SAP objects;
- supporting evidence.

Rule types: `VALIDATION`, `CALCULATION`, `DECISION`, `WORKFLOW`, `ELIGIBILITY`, `DERIVATION`, `COMPLIANCE`, `INTEGRATION`, `OTHER`.

### Application
Functional cluster of related SAP custom objects. Suggested fields:
- name, description, domain;
- parent application (optional);
- confidence and discovery rationale;
- member objects, transactions, business rules and findings.

### CleanCoreAssessment
Must separate:
- `technical_risk`: LOW/MEDIUM/HIGH/CRITICAL;
- `business_importance`: LOW/MEDIUM/HIGH/CRITICAL/UNKNOWN;
- `recommendation`: KEEP/REMEDIATE/MODERNIZE/REPLACE_WITH_STANDARD/REIMPLEMENT_AS_EXTENSION/RETIRE/REVIEW;
- confidence, rationale and evidence references.

## Ownership invariant
All source, processing, findings, AI interpretations, embeddings, result aggregates and user validations belong to an Assessment. Results must not be owned by a separately managed SAP System.
