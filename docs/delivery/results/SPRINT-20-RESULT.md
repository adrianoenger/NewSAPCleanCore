# SPRINT-20 Result — Panaya Usage/Repository XLSX Import

**Status:** Completed
**Completed at:** 2026-10-01T16:30:00Z
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Extends `evidence/adapters/panaya.py` (same `PANAYA_ETL` dataset_type, same adapter module) to
recognize and import a second, real, independently-verified Panaya export format: a flat XLSX
"usage/repository" report (`export T-systems.xlsx`, 143,086 rows) — structurally unrelated to the
already-curated multi-gigabyte XML ETL dump, but still Panaya-sourced landscape data about the same
kind of SAP objects. Detection is by header-row *signature* (`OBJECT NAME`/`OBJECT TYPE`/
`USAGE LEVEL`/`ORIGIN`, tolerant of column reordering/extra columns), never by filename or an
exact-match requirement. Each row becomes one `EvidenceRecord` (`capability="USAGE_SIGNAL"`,
`record_type="panaya_usage_object"`), streamed via `openpyxl` `read_only` mode in 20,000-row batches,
imported in full (no truncation at this row count). `ADR-017` and the supplemental evidence import
contract were amended to document this second real format.

User follow-up during planning ("evaluate the best way to demonstrate the usage data, adjust the
dashboard if needed") added **CAP-005**: Dashboard Geral gained a dedicated, additive surface for
this previously-invisible usage dimension — a new "Utilização de Objetos (Panaya)" panel and a 6th
KPI "Objetos customizados sem uso", backed by a `usage_signal_by_level`/`unused_custom_objects`
aggregation that queries `EvidenceRecord.normalized_payload` directly (no new column/migration) and
a `usage_level` filter/column on the existing object drill-down list.

## Demonstration path
1. Upload `export T-systems.xlsx` through the existing Evidence Datasets UI/API (Step 1 —
   `POST /assessments/{id}/evidence-datasets/inspect` then `.../evidence-datasets`) — `inspect()`
   reports 143,086 rows and `TECHNICAL_OBJECT_METADATA`/`USAGE_SIGNAL` capabilities, with
   `USAGE LEVEL`/`ORIGIN`/`OBJECT TYPE`/`MODULE` distribution stats in the manifest.
2. Background import reaches `IMPORTED_FULL` (8 batches, `records_count=143086`); correlation runs
   automatically against the Assessment's `SAPObject`s via the existing generic
   `evidence.correlation` pipeline (no new correlation logic).
3. Dashboard Geral's new panel/KPI reflect the real correlation outcome: a non-zero
   `usage_signal_by_level`/`unused_custom_objects` and object-list filtering by `usage_level` when
   correlations exist, or an explicit, honest zero state when they don't — never a fabricated
   number.
4. **Live-validated end to end** via the real HTTP API against the persistent Acme Industries
   assessment (id 75): steps 1–2 reproduced exactly (143,086/143,086 rows imported, manifest
   matching planning-time counts precisely); correlation resolved to `143086 UNMATCHED` — expected
   and documented, since this real T-Systems export's object names have zero overlap with Acme's 6
   tiny demo objects; `/dashboard-overview` correctly rendered `usage_signal_by_level: {}` and
   `unused_custom_objects: 0` (genuine zero state, not a placeholder), and the pre-existing HANA
   Sizing Report dataset's own `USAGE_SIGNAL` rows (no `USAGE LEVEL` key) were correctly excluded
   from the aggregation, confirming the capability-oriented filter generalizes correctly rather than
   hard-coding provider identity. The validation dataset was deleted afterward (cascade verified —
   zero orphaned `EvidenceRecord` rows) to leave the persistent demo assessment unchanged. The
   positive-match (non-zero correlation) path is covered by the automated test suite instead (see
   below), since no persisted assessment in this environment shares object names with this
   specific real file.

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint — backend container healthy, `alembic check`
      shows only the pre-existing `BL-013` drift (verified twice; no new drift, no migration this
      sprint — no model/schema change).
- [x] Critical contracts introduced by the sprint — `test_evidence_panaya.py` gained 6 new tests
      (header-signature detection incl. filename-independence and column-reorder/extra-column
      tolerance, rejection of an unrelated XLSX, row/distribution counting, idempotent persistence,
      correlation + Clean Core business-pool surfacing). `test_dashboard.py` gained
      `test_usage_signal_overview_and_object_list_filter` (positive match + genuine zero-state case
      for the new aggregation/filter).
- [x] Primary demonstrable user flow — reproduced live against the real file and a real persisted
      assessment via the actual HTTP API (see Demonstration path step 4), not only a crafted
      fixture.
- [x] Required integration checks — full backend suite **272/272** passing (265 baseline + 7 new),
      re-run twice independently to confirm. Frontend `tsc --noEmit` clean after the
      `UsagePanel`/KPI/column additions (full `electron-vite build` also run clean once).
- [x] Migration applicability — N/A, no schema change this sprint.

## Key implementation notes
- `backend/src/evidence/adapters/panaya.py` — `detect()`/`inspect()`/`plan_batches()`/
  `import_batch()` each dispatch internally between the pre-existing XML path and the new XLSX
  usage-report path (`_usage_xlsx_header`, `_inspect_usage_xlsx`, `_import_usage_xlsx_batch`); no
  existing XML-path logic was touched.
- `backend/src/pipeline/dashboard_summary.py` — `usage_signal_object_ids_by_level`/
  `usage_level_correlation_subquery` (shared base query `_usage_signal_correlation_rows`); both
  filter on the `normalized_payload` JSONB key actually being present rather than on any
  provider-specific `record_type`, so a differently-shaped `USAGE_SIGNAL` row from another adapter
  (e.g. HANA Sizing Report's per-table metrics) is excluded without hard-coding provider identity.
- `backend/src/api/routes/dashboard.py` / `api/schemas/dashboard.py` — `usage_level` filter/field on
  `/object-list`; `usage_signal_by_level`/`unused_custom_objects` on `/dashboard-overview`.
- `frontend/.../components/dashboard/charts.tsx` — new `UsagePanel` (same `Panel`/`Row` pattern as
  `InventoryPanel`/`AtcPanel`); `DashboardGeral.tsx` — 6th KPI card; `EntityList.tsx` — `usage_level`
  filter dropdown + column; `lib/api.ts` — matching type additions.
- `docs/adr/017-supplemental-evidence-datasets.md` / `docs/data/supplemental-evidence-import-contract.md`
  — both amended with the new XLSX usage/repository profile.

## Known limitations
- `LAST USED`/`LAST CHANGED BY` are imported and preserved in `normalized_payload` (visible via the
  generic evidence-citation drill-down) but not surfaced in the new dashboard panel — the real
  sample has `LAST USED` populated on only 165/143,086 rows, too sparse to justify a dedicated
  surface this sprint (`BL-030`).
- No real persisted assessment in this environment shares object names with the real
  `export T-systems.xlsx` file, so the live validation's correlation outcome is `UNMATCHED` rather
  than a real positive match — expected per the sprint plan's own stated caveat; the positive-match
  path is proven by the automated test suite instead.
- Correlation against this profile realistically resolves to `MATCHED_HEURISTIC` (name-only), since
  its `OBJECT TYPE` values are Panaya's own human-readable vocabulary rather than this
  application's internal `SAPObject.object_type` vocabulary — same situation every other curated
  Panaya section already faces, not a new gap.
- One full-suite pytest run mid-sprint showed 7 transient failures, all in
  `test_sprint06.py`/`test_sprint07.py`/`test_object_understanding_pipeline.py` (pipeline
  pause/resume/retry, unrelated to this sprint's files). Confirmed pre-existing `BL-008`-style
  shared-dev-DB flakiness, not a regression — isolated re-run was 25/25, and two subsequent full
  clean runs (one during implementation, one independently during review) were both 272/272.

## Deferred items
- `BL-030` — Panaya usage-report `LAST USED`/`LAST CHANGED BY` imported but not surfaced in any UI.

## Repository closure
- Sprint branch: `sprint/20-panaya-usage-xlsx-import`
- Official commit message: `feat(sprint-20): complete panaya usage xlsx import`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
