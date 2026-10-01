# SPRINT-20 — Panaya Usage/Repository XLSX Import

## Position in the sequence
- Prerequisite: SPRINT-19 completed.
- Coherence rule: extends ADR-017 strictly within its existing adapter contract (`detect → inspect →
  plan_batches → import_batch`, same `EvidenceDataset`/`EvidenceArtifact`/`EvidenceRecord`/
  `EvidenceCorrelation` model, no new persistence concept). ADR-017's Panaya format-specific section
  currently documents only the bare/ZIP-wrapped multi-gigabyte XML `PANAYA_ETL` export; this sprint
  amends that section with a second, real, independently-verified Panaya export format (a flat XLSX
  usage/repository report) rather than inventing a new ADR, following the exact precedent already set
  twice in ADR-017 itself (the Panaya XML and Signavio ZIP "Amendment" sections, added once a real
  sample became available). No accepted ADR is contradicted; `evidence_package.py`'s `USAGE_SIGNAL`/
  `TECHNICAL_OBJECT_METADATA` capability whitelists already exist (used by HANA Sizing/Readiness Check
  today) and need no change.
- Origin: a real new file was received from Panaya for a T-Systems-sourced system
  (`SAP_Files/SAP Extra/export T-systems.xlsx`, gitignored, 143,086 data rows). Inspected read-only
  during planning (2026-10-01) — see confirmed findings below. The existing `panaya.py`
  adapter's `detect()` only recognizes `.xml`/`.zip` carrying the `EXPORT_TOOL_VERSION` signature, so
  this file is currently unrecognized by `evidence.adapters.detect_adapter()` and cannot be imported
  today.

## Confirmed findings this sprint builds on
Verified directly against the real file with `openpyxl` (read-only, no DB writes) — not guessed:

- Single sheet (`Sheet0`), one header row, 143,086 data rows, 10 columns: `OBJECT NAME`,
  `OBJECT DESCRIPTION`, `MODULE`, `USAGE LEVEL`, `PACKAGE`, `OBJECT TYPE`, `OBJECT SUB TYPE`, `ORIGIN`,
  `LAST USED`, `LAST CHANGED BY`. `OBJECT NAME` is populated on every row (0 blanks).
- `ORIGIN` distribution: `Customer` 112,595 / `SAP Standard` 20,663 / `3rdPartDomain` 9,828 — a
  customer/standard/third-party classification per object, not present in any currently curated XML
  section.
- `USAGE LEVEL` distribution: `Unknown` 68,300 / `Unused` 67,577 / `Normally Used` 7,200 /
  `Frequently Used` 5 / `Rarely Used` 4 — an explicit usage classification per object, which no
  currently curated Panaya XML section carries (`REPOSITORY_OBJECTS`/`PROGRAMS`/`FUNCTIONS` are
  metadata-only, no usage dimension).
- `OBJECT TYPE` top values: `Program` 69,913, `Role` 32,913, `Data Element` 17,148, `SAP Table` 7,889,
  `Screen` 6,121, `Report` 2,884, `Transaction` 2,195, plus smaller counts for `SAP Query`,
  `Table Maintenance`, `Modification`, `Remote Function Call`, `Fiori`, `Proxy`, `BAdI`, etc.
- `MODULE` is `Custom-Code` for 122,174 rows (the vast majority) or blank/an SAP functional area
  (`FI`, `MM`, `BC`, ...) for the rest.
- `LAST USED` is populated on only 165/143,086 rows (format `DD-Mon-YYYY`, e.g. `20-Jun-2026`);
  `LAST CHANGED BY` is populated on 103,693/143,086 rows. Both are optional per-row signals, not
  guaranteed.
- No system/client header metadata exists in this file format (unlike the XML export's `<HEADER
  SYSTEM_ID=... CLIENT=... />`) — `source_system_hint`/`source_client_hint` will be `None` for this
  profile; this is a real limitation of the format, not an adapter gap, and must not be guessed from
  the filename.
- This is a genuinely different Panaya export *format* (flat row-per-object XLSX "usage/repository"
  report) from the already-curated multi-gigabyte XML ETL dump, but is still Panaya-sourced landscape
  data about the same kind of SAP objects — kept under the same `PANAYA_ETL` dataset_type and the same
  `panaya.py` adapter module (one `detect()` recognizing either real format by content, not filename),
  rather than introducing a second Panaya dataset_type/adapter pair purely for registry plumbing.
- Only one real sample has been reviewed. Per ADR-016/ADR-017's shared "never hard-code the one
  reviewed sample as the only valid schema" principle (already applied to the ATC importer),
  detection must key off a header-row *signature* (the known column name set, order-tolerant) rather
  than an exact byte-for-byte match, and any column beyond the 10 observed must be tolerated, not
  rejected.

## Planned capabilities
- CAP-001 — `panaya.py::detect()` also recognizes this XLSX profile by sniffing the header row for
  the known column-name signature (`OBJECT NAME`, `OBJECT TYPE`, `USAGE LEVEL`, `ORIGIN` at minimum —
  tolerant of extra/reordered columns, never an exact-match requirement), independent of filename.
  `inspect()` streams the sheet read-only (`openpyxl` `read_only=True`, same streaming discipline as
  the XML path and as `atc/importer.py`'s existing schema-tolerant XLSX reading) to produce row count,
  `ORIGIN`/`USAGE LEVEL`/`OBJECT TYPE`/`MODULE` distribution stats in the manifest, and capabilities
  `TECHNICAL_OBJECT_METADATA` + `USAGE_SIGNAL`.
- CAP-002 — `plan_batches()`/`import_batch()` stream the sheet in bounded row-range batches (e.g.
  20,000 rows per batch, mirroring the existing `_MAX_RECORDS_PER_SECTION` chunking discipline) rather
  than loading all 143k rows into memory at once; each row becomes one `EvidenceRecord`
  (`record_type="panaya_usage_object"`, `capability="USAGE_SIGNAL"`, `object_name`=`OBJECT NAME`,
  `object_type`=`OBJECT TYPE`, `package_name`=`PACKAGE`, full row preserved in `normalized_payload`,
  `source_locator`={row index}). Unlike the XML path's per-section truncation cap, this format's
  realistic row counts (low hundreds of thousands) are imported in full — no silent truncation unless
  a future real file proves otherwise.
- CAP-003 — Correlation + evidence-package contract tests: new records reach a `MATCHED_*` status
  against a matching `SAPObject` via the existing generic `evidence.correlation` pipeline (object
  name/type match — no new correlation logic expected), and surface in
  `ai.clean_core_analysis.evidence_package`'s business pool (`PROCESS_USAGE_EVIDENCE`, `USAGE_SIGNAL`
  is already whitelisted — no code change expected there, only a confirming test).
- CAP-004 — Documentation closure: amend ADR-017's Panaya format-specific section with this second
  real format (XLSX usage/repository report, schema-tolerant header-signature detection, no
  system/client hint available), update `docs/data/supplemental-evidence-import-contract.md`'s Panaya
  profile accordingly, and record a BACKLOG note for `LAST USED`/`LAST CHANGED BY` not yet being
  surfaced in any UI (counted/stored, not yet shown) if that remains true after CAP-001/002.
- CAP-005 — Dashboard Geral usage-signal demonstration (user-requested during planning, 2026-10-01):
  the imported `USAGE_SIGNAL` data (per-object usage level, correlated to `SAPObject`) is otherwise
  invisible outside the raw evidence-citation drill-down, so it gets a dedicated, additive surface on
  the single results screen (ADR-019), reusing the existing `objects` drill-down entity — no new
  entity/list type.
  - **Backend** (`pipeline/dashboard_summary.py::compute_dashboard_overview`): add
    `usage_signal_by_level: dict[str, int]` — current-scan `SAPObject`s joined to a `MATCHED_*`
    `EvidenceCorrelation` → `EvidenceRecord` where `capability="USAGE_SIGNAL"`, grouped by
    `normalized_payload->>'USAGE LEVEL'` (no new column — queries the existing JSONB payload, same as
    every other capability-specific attribute in this codebase); and `unused_custom_objects: int` —
    distinct count of custom (`Z`/`Y`/namespaced) objects with at least one such correlated record
    whose level is `Unused`. Both added to `DashboardOverview`/`DashboardOverviewRead`.
  - **Backend** (`api/routes/dashboard.py::list_objects_for_drilldown` / `/object-list`): new optional
    `usage_level` filter (same join pattern as the existing `atc_counts` subquery) and a `usage_level`
    field on `ObjectListItem` (the object's own correlated level, `None` if no `USAGE_SIGNAL` record
    correlates to it) so the drill-down list can show and filter by it.
  - **Frontend**: a new `UsagePanel` in `components/dashboard/charts.tsx` (same `Panel`/`Row` pattern
    as `InventoryPanel`/`AtcPanel`) showing the level breakdown, each row opening the `objects` list
    filtered by `usage_level`; a 6th KPI card "Objetos customizados sem uso" (`unused_custom_objects`)
    opening the list pre-filtered to `{ usage_level: 'Unused', custom_only: true }`; `usage_level`
    added to `ObjectListFilter`/`ObjectListItemRecord` (`lib/api.ts`) and as a column in
    `EntityList.tsx`'s `OBJECT_COLUMNS`. No new ADR/schema impact — purely a read-model/UI addition
    over data CAP-001..003 already persist and correlate.
  - If the demonstrable outcome's chosen Assessment has no real `MATCHED_*` `USAGE_SIGNAL`
    correlations (see CAP-003's own caveat), the panel/KPI must render a genuine zero state, never a
    placeholder/fabricated number.

## Demonstrable outcome
Upload the real file (`SAP_Files/SAP Extra/export T-systems.xlsx`) as a new supplemental evidence
dataset through the existing Evidence Datasets UI/API against a real or disposable Assessment →
`inspect()` reports ~143,086 rows and the `TECHNICAL_OBJECT_METADATA`/`USAGE_SIGNAL` capabilities →
import completes (`IMPORTED_FULL`, batched) → at least some resulting `EvidenceRecord`s correlate
(`MATCHED_*`) to real `SAPObject`s already present in that Assessment (if the target Assessment's
objects overlap this file's object names) → reprocessing shows at least one `USAGE_SIGNAL` evidence
item in an owning Application's Clean Core business-evidence pool, visible through the existing
evidence citation UI (no new UI required for that part). If the chosen Assessment's objects do not
overlap this specific file's object names closely enough to produce real matches, state that plainly
rather than forcing/fabricating a match — the dataset-level import/inspect behavior is still fully
demonstrable on its own. In addition (CAP-005): Dashboard Geral shows the new "Objetos customizados
sem uso" KPI and "Utilização de Objetos" panel with real, non-zero counts (when correlations exist)
or an explicit, honest zero/empty state (when they don't); clicking a usage-level row/the KPI opens
the existing object drill-down list pre-filtered and showing each object's usage level.

## Minimal validation
- Adapter unit tests for `detect`/`inspect`/`plan_batches`/`import_batch` against a small crafted XLSX
  fixture using the real observed header/column names (fast, deterministic — the real 143k-row file is
  for the one-time live import validation pass, not the repeatable test suite).
- A header-signature detection test confirming tolerance to column reordering/extra columns (never an
  exact-match-only check), consistent with ADR-016's established schema-tolerance principle.
- One correlation contract test and one `clean_core_analysis` evidence-package pool test (per CAP-003).
- `dashboard_summary`/`object-list` tests covering `usage_signal_by_level`/`unused_custom_objects`
  and the new `usage_level` filter (per CAP-005), including the genuine-zero-state case.
- Frontend `tsc`/`build` clean after the `UsagePanel`/KPI/column additions.
- Full existing backend pytest suite stays green. Do not add broad coverage beyond this.

## Completion criteria
- Planned capabilities implemented or explicitly deferred with rationale.
- Demonstrable outcome reproduced successfully (or its stated real-data caveat applies and is
  recorded).
- ADR-017 and the supplemental evidence import contract updated to reflect the real verified format.
- Progress/state files updated.
- Application remains runnable for the next sprint.
