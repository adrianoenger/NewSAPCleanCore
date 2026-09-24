# ATC XLSX Import Contract

**Status:** Canonical for Baseline 2026-09-24-R3.1  
**Reference sample reviewed:** `ATC_20260427_ZandY_141515.xlsx`  
**Scope:** Assessment stage `2 - Análise ATC`

## Decision

ATC Excel files are treated as **semi-structured external evidence**, not as a fixed database schema or a fixed 21-column template.

The importer must tolerate:
- columns that are absent;
- additional unknown columns;
- changed column order;
- blank cells;
- exporter-specific placeholder/sentinel values;
- minor header naming differences that can be mapped safely;
- multiple ATC report versions/runs for the same Assessment.

A new or missing optional Excel column must **not** by itself require a database migration.

## Observed reference sample — not a fixed contract

The reviewed sample contains:
- worksheet: `Data`;
- 7,899 data rows plus one header row;
- 21 observed columns;
- priorities: 2,139 Priority 1, 1,614 Priority 2 and 4,146 Priority 3;
- 12 distinct Check Titles;
- 14 distinct Object Types;
- 56 distinct Packages;
- 56 distinct SAP Note numbers when the repeated placeholder-like value `25` is excluded;
- `First Found On = 46139`, which is the Excel serial date for 2026-04-27 in the sample.

These counts describe only the reviewed file and **must never be used as acceptance criteria for arbitrary future ATC files**.

### Observed headers

The sample exposes the following headers:

1. `Priority`
2. `Check Title`
3. `Check Message`
4. `Object name`
5. `Object Type`
6. `Exemption State`
7. `Contact Person`
8. `Package`
9. `First Found On`
10. `Object Responsible`
11. `Last Changed by`
12. `SAP Note Number`
13. `Short Text`
14. `Referenced Application Component`
15. `Referenced Object Type`
16. `Referenced Object`
17. `Additional Info`
18. `Simplification Item Category`
19. `Change Category of Piecelist Items`
20. `Description of Change Category`
21. `Remarks`

The importer may recognize these fields, but it must not require all of them.

## Import philosophy

The import pipeline separates four concerns:

```text
XLSX file
   ↓
Workbook/sheet discovery
   ↓
Header discovery + mapping
   ↓
Raw row preservation
   ↓
Canonical normalization
   ↓
Object correlation + technical interpretation
```

Raw evidence is preserved before semantic normalization.

## Workbook and sheet discovery

The importer must not depend permanently on a worksheet named `Data`.

Recommended behavior:
1. enumerate worksheets;
2. ignore empty sheets;
3. identify candidate tabular sheets from a header-like first non-empty row and following data rows;
4. prefer a known sheet name such as `Data` only as a convenience, not as a requirement;
5. if multiple plausible sheets exist, show them to the user or apply a deterministic documented selection rule.

Persist the selected worksheet name in the ATC run.

## Header handling

Header matching must be case-insensitive and whitespace-normalized.

Safe aliases may be supported through a versioned mapping registry, for example:

```text
Object name    → object_name_raw
Object Type    → object_type_raw
Check Title    → check_title
Check Message  → check_message
SAP Note Number → sap_note_number
```

Do not guess aggressively. An unrecognized header must be preserved as part of the raw row payload rather than silently mapped to the wrong canonical field.

Persist for each run:
- original header list and order;
- normalized header names;
- resolved canonical mapping;
- unknown headers;
- missing known headers;
- mapping/import warnings;
- importer/mapping profile version.

## Validation levels

Validation is capability-oriented rather than based on one exact template.

### `ACCEPTED_FULL`
Enough recognized information exists to create canonical findings and correlate them to SAP objects with the normal level of functionality.

Typically this includes an identifiable object plus finding/check information.

### `ACCEPTED_PARTIAL`
The workbook is readable and rows can be preserved, but one or more useful canonical fields are unavailable.

Examples:
- no `Object Type`;
- no SAP Note columns;
- no change-category fields;
- no referenced object fields;
- no responsible/contact information.

The import succeeds with warnings. Features that require the missing information remain unavailable for that run.

### `REJECTED`
Use only for structural failures such as:
- workbook cannot be read;
- no usable worksheet;
- no usable header row;
- no data rows;
- corrupt/unsupported file;
- a condition that makes row boundaries or values unreliable.

Missing optional known columns alone is not a rejection condition.

## Canonical ATC finding fields

Canonical columns are nullable unless a stronger invariant is explicitly required by the application.

Suggested canonical projection:
- `priority`;
- `check_title`;
- `check_message`;
- `object_name_raw`;
- `object_type_raw`;
- `exemption_state`;
- `contact_person`;
- `package_name_raw`;
- `first_found_on`;
- `object_responsible`;
- `last_changed_by`;
- `sap_note_number`;
- `sap_note_short_text`;
- `referenced_application_component`;
- `referenced_object_type`;
- `referenced_object_name`;
- `additional_info`;
- `simplification_item_category`;
- `change_category`;
- `change_category_description`;
- `remarks`.

Additional source columns remain available through the preserved raw/normalized payload even if no first-class canonical column exists yet.

## Raw row preservation

Every imported source row must preserve enough information to reproduce and audit the mapping.

Recommended fields on `ATCFinding` or an associated import-row entity:
- `source_row_number`;
- `raw_payload` (`JSONB`) — original header/value representation;
- `normalized_payload` (`JSONB`, optional) — normalized values keyed by normalized source header;
- `row_fingerprint` — stable hash useful for duplicate detection;
- `mapping_warnings` (`JSONB` or structured equivalent);
- canonical nullable columns used by application queries.

Do not discard an unknown source column.

## Placeholder and sentinel values

The reviewed file demonstrates that a source cell can be populated even when it does not appear to carry meaningful business information.

For example, the value `25` appears repeatedly in optional-looking columns, including:
- 100% of `Exemption State` rows;
- 100% of `Remarks` rows;
- about 74% of SAP Note / Short Text / referenced-object-related rows;
- about 89% of `Additional Info` rows.

Therefore:

**Presence of a cell value does not imply semantic presence of the field.**

Rules:
1. always preserve the original value in `raw_payload`;
2. normalization may produce `null` while retaining the raw value and reason;
3. never define `25` as a universal null token across all columns/files;
4. sentinel handling must be field-aware and importer-profile-aware;
5. if semantic validity is uncertain, keep the canonical value nullable/unknown and add a warning instead of inventing meaning;
6. `Not specified` may remain a legitimate normalized categorical/text value where the exporter intentionally emits it.

## Type normalization

Normalize values only after raw preservation.

Examples:
- `Priority`: integer when valid, otherwise preserve raw and warn;
- `First Found On`: accept a real spreadsheet date or Excel serial date and normalize to a date when unambiguous;
- `SAP Note Number`: preserve as text to avoid losing leading zeros or format information;
- names/types/packages/components: trimmed text;
- categories: validated text/code when recognized, otherwise preserve as unknown/raw.

Do not fail the full run because a single row contains a malformed optional value. Prefer row-level warnings unless integrity is compromised.

## Dynamic catalogs

Do not pre-seed ATC checks, SAP Notes, packages, simplification categories or change categories based solely on the reviewed sample.

During import:
- upsert recognized `ATCCheck` values dynamically;
- create/link SAP Notes dynamically when a valid note number is available;
- keep package/component/category values data-driven;
- treat sample counts such as 12 checks and 56 packages as observations only.

## Correlation with parsed SAP objects

Correlation must be progressive and evidence-based.

Preferred match inputs when available:
1. `object_name_raw`;
2. `object_type_raw`;
3. Assessment ownership.

If object type is absent, a unique name match inside the Assessment may be proposed with reduced confidence, but ambiguous matches must remain unresolved.

Persist correlation status such as:
- `MATCHED_EXACT`;
- `MATCHED_HEURISTIC`;
- `UNMATCHED`;
- `AMBIGUOUS`.

Do not invent a SAP object merely to satisfy an ATC row.

## Multiple ATC runs

An Assessment may import more than one ATC report over time.

Each `ATCRun` must preserve its own:
- source filename;
- file fingerprint/hash;
- selected worksheet;
- detected headers/mapping snapshot;
- import profile/version;
- imported row count;
- warning/error summary;
- validation status;
- import timestamp;
- optional ATC execution metadata if available from source/context.

A new ATC run must not overwrite the historical rows of an older run.

## UI requirements

The `2 - Análise ATC` page should show at least:
- XLSX selection/upload;
- detected worksheet;
- detected column count;
- recognized columns;
- missing known columns;
- unknown/new columns;
- row count;
- validation result (`Full`, `Partial`, `Rejected`);
- warnings before final import where relevant;
- import progress/status;
- imported findings count and correlation summary.

A partial import should be visibly identified without being presented as a failure.

## Minimal Sprint 05 validation

Use the reviewed sample as one regression fixture/reference case, but also test variability explicitly.

Minimum cases:
1. current 21-column sample imports successfully;
2. same data with one optional column removed imports successfully with warning;
3. several optional columns removed imports successfully;
4. column order changed still maps correctly;
5. unknown extra column is preserved and does not fail import;
6. blank optional cells do not fail import;
7. placeholder/sentinel-like source values preserve their raw representation;
8. malformed optional value produces a row/run warning rather than total failure;
9. unreadable/empty workbook is rejected cleanly;
10. object correlation is Assessment-scoped and leaves ambiguous rows unresolved.

Do not build an exhaustive spreadsheet ETL framework. Implement the smallest robust mechanism that satisfies these rules for the PoC.
