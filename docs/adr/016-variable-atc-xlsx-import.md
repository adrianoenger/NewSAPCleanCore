# ADR-016 — Variable ATC XLSX Import Contract

**Status:** Accepted  
**Date:** 2026-09-24

## Context
The PoC imports SAP ATC results from Excel during Assessment stage `2 - Análise ATC`. A real sample (`ATC_20260427_ZandY_141515.xlsx`) contains 7,899 findings and 21 columns, but future ATC exports may omit fields, add fields, reorder columns or encode unavailable values differently.

The reviewed sample also contains repeated placeholder-like values such as `25` in fields that otherwise carry optional metadata. A rigid `21 columns == valid report` contract would therefore be fragile and would confuse physical cell presence with semantic data quality.

## Decision
Treat ATC XLSX input as a **semi-structured external evidence source**.

The importer must:
- discover workbook/sheet/header structure at runtime;
- map known headers by normalized name/explicit aliases rather than column position;
- accept missing optional columns and unknown extra columns;
- support full and partial successful imports with warnings;
- preserve original row/header data before normalization;
- persist the mapping/header snapshot and importer version per ATC run;
- keep canonical ATC fields nullable when their source column/value is absent;
- use field/profile-aware sentinel normalization rather than global magic values;
- dynamically discover checks/catalog values instead of assuming the sample's 12 checks, 56 packages or other counts;
- keep multiple ATC runs without overwriting historical imports.

Canonical details are defined in `docs/data/atc-import-contract.md`.

## Consequences
### Positive
- Future ATC export variants do not require immediate schema changes.
- Raw evidence remains auditable and reprocessable.
- Partial reports still provide value.
- Unknown columns are not lost.
- Sample-specific artifacts do not become product invariants.

### Trade-offs
- Import code needs explicit mapping/warning semantics.
- Canonical fields cannot all be `NOT NULL`.
- UI must expose import quality/warnings.
- Downstream capabilities must tolerate missing ATC attributes.

## Rejected alternatives
### Require the exact observed 21-column layout
Rejected because the user explicitly expects variable ATC structures and SAP/export variants can evolve.

### Store only raw JSON without canonical columns
Rejected because technical views, filters, correlation and Clean Core analysis need efficient normalized fields.

### Normalize unknown/sentinel values destructively
Rejected because evidence-first traceability requires preservation of the original source value.
