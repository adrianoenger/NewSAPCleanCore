# SPRINT-05 — Dependencies, ATC and Technical Findings

## Goal
Build objective technical analysis before AI interpretation, including a schema-tolerant ATC XLSX importer.

## Planned capabilities
- Detect deterministic relations such as CALL/INCLUDE/READS/USES where supported.
- Implement Assessment stage `2 - Análise ATC`.
- Select/upload `.xlsx` and discover usable worksheet/header structure.
- Map recognized ATC columns by normalized header/explicit aliases, never by fixed column position.
- Accept missing optional columns and additional unknown columns.
- Preserve run-level header/mapping provenance and raw source rows.
- Normalize recognized fields into nullable canonical ATC finding attributes.
- Surface `FULL` vs `PARTIAL` successful import states and warnings.
- Handle exporter-specific placeholder/sentinel candidates without a global magic-null rule.
- Dynamically discover/upsert checks and related catalog values from imported data.
- Persist multiple ATC runs per Assessment without overwriting history.
- Correlate findings to parsed SAP objects when possible; preserve `UNMATCHED`/`AMBIGUOUS` state otherwise.
- Create deterministic technical finding model.
- Add dependency explorer and ATC/finding list.

The canonical ATC contract is `docs/data/atc-import-contract.md` and ADR-016.

## Reference sample
The reviewed file `ATC_20260427_ZandY_141515.xlsx` is a regression/reference case, **not the schema definition**. It has 7,899 data rows and 21 observed columns. Future files may omit or add fields.

## UI behavior
Before/following import, show useful import diagnostics such as:
- selected worksheet;
- detected row/column count;
- recognized fields;
- missing known fields;
- unknown fields;
- import quality (`Full` / `Partial` / `Rejected`);
- warnings;
- imported findings and correlation summary.

## Demonstrable outcome
Import the reference ATC `.xlsx` for an Assessment, inspect the detected mapping, complete the import, then open an object and see its dependencies, ATC findings and deterministic technical findings. Demonstrate at least one partial-layout variant that still imports successfully with warnings.

## Minimal validation
- Reference 21-column sample imports successfully.
- Removing one optional column does not reject the report.
- Removing several optional columns results in partial import rather than total failure.
- Reordered columns still map correctly.
- Unknown extra column is retained in raw evidence and does not fail import.
- Blank optional values are accepted.
- Placeholder/sentinel-like source values preserve the original raw value.
- Malformed optional values produce bounded warnings, not a full-run failure.
- Empty/unreadable workbook is rejected cleanly.
- Correlation is Assessment-scoped and ambiguous matches remain unresolved.
- Relevant dependency/technical-finding smoke tests pass.
- Do not add broad spreadsheet-framework or enterprise ETL coverage unrelated to the PoC.

## Completion criteria
- Planned capabilities implemented or explicitly deferred with rationale.
- Demonstrable outcome reproduced successfully.
- Progress/state files updated.
- Application remains runnable for the next sprint.
