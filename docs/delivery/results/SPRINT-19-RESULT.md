# SPRINT-19 Result — Panaya Evidence Signal Curation

**Status:** Completed
**Completed at:** 2026-10-01T00:50:00Z
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Curates two more real, verified Panaya ETL sections into
`evidence/adapters/panaya.py::_CURATED_SECTIONS` — `SCI_HANA_ISSUES`/`SCI_HANA_ISSUES_DETAILS`
(HANA/custom-code readiness issues, `S4_CONVERSION_SIGNAL`) and `WHERE_USED_TABLE` (table/include
cross-reference, `DEPENDENCY_SIGNAL`) — so they reach `SAPObject` correlation and the Clean Core
technical evidence pool, which already consumes any correlated `EvidenceRecord` generically. Both
section shapes were verified two ways before any code was written: reading the real T-Systems/Panaya
ABAP export program, then a read-only `inspect()`/attribute-sampling pass against the real customer
export (`SAP_Files/SAP Extra/Panaya/ETL_QAS_20260916_150001.xml`, 2.8GB, gitignored). This closes
`BL-009` and the actionable part of `BL-026` with certainty rather than guessing (ADR-017).

A real-data refinement was found during verification: `WHERE_USED_TABLE`'s `NAME` attribute is a
compound, `OTYPE`-dependent cross-reference token (not a plain object name) — only `INCLUDE` is used
for correlation, avoiding a false-confidence correlation ADR-017 explicitly forbids.

## Demonstration path
1. `evidence/adapters/panaya.py::_CURATED_SECTIONS` now maps 8 sections (5 pre-existing + the 3 new
   ones); `inspect()` against a Panaya export now reports `S4_CONVERSION_SIGNAL`/`DEPENDENCY_SIGNAL`
   capabilities including the new sections' real counts.
2. Importing a Panaya `EvidenceDataset` persists `EvidenceRecord`s for the new sections, correlates
   them to matching `SAPObject`s via the existing `evidence.correlation` pipeline (no new correlation
   logic), and — with zero changes to `ai/clean_core_analysis/evidence_package.py` — they appear as
   `SUPPLEMENTAL_EVIDENCE` citations in the owning Application's Clean Core technical pool.
3. **Live-validated beyond the fixture**, against real production-scale data: backfilled the
   already-imported real `PANAYA_ETL` dataset (id 389, Assessment01/Rodobens assessment id 1075) by
   creating a fresh `PipelineRun(kind=evidence_import)` over the real 2.8GB file. Real result:
   `SCI_HANA_ISSUES` 5280/5280 and `SCI_HANA_ISSUES_DETAILS` 7038/7038 fully imported,
   `WHERE_USED_TABLE` 20000/1,182,072 (correctly truncated with a warning, same cap the pre-existing
   curated sections already hit). 124 real `MATCHED_HEURISTIC` correlations to real Rodobens
   `SAPObject`s. Confirmed via `build_clean_core_evidence_package` (no AI call) that a real
   `panaya_sci_hana_issue` record (a genuine HANA/custom-code issue on customer class
   `ZCLRNIPS_ASSIST_CONF`) is cited in the technical pool for real `Application` id 2820 ("Gestão de
   Projetos e Estruturas Analíticas (PS)").

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint — backend container healthy, `alembic check`
      shows only the pre-existing `BL-013` drift (no new drift; no migration this sprint).
- [x] Critical contracts introduced by the sprint — `test_evidence_panaya.py` updated
      (`inspect`/`plan_batches`/`import_batch` for the 3 new sections, including the
      `NAME`-never-used-as-correlation-key assertion) plus a new contract test
      (`test_new_curated_sections_correlate_and_surface_in_clean_core_technical_pool`) proving
      correlation + Clean Core technical-pool surfacing end to end. 7/7 in this file.
- [x] Primary demonstrable user flow — reproduced live against the real Panaya export and the real
      Rodobens assessment (see Demonstration path step 3), not only a crafted fixture.
- [x] Required integration checks — full backend suite 265/265 passing (two full runs this sprint,
      ~987-1008s each; includes pre-existing live-Bedrock tests per `BL-014`).
- [x] Migration applicability — N/A, no schema change this sprint.

## Key implementation notes
- `backend/src/evidence/adapters/panaya.py` — `_CURATED_SECTIONS` +3 entries only; no other adapter
  logic touched.
- `backend/tests/test_evidence_panaya.py` — fixture XML extended with real-shaped sample rows for
  the 3 new sections; existing inspect/import tests updated; one new end-to-end contract test.
- `docs/data/supplemental-evidence-import-contract.md` — Panaya profile documents all 8 curated
  sections' real verified shapes and the un-curated ones' status.
- `docs/delivery/BACKLOG.md` — `BL-009` and the actionable part of `BL-026` marked Resolved with the
  confirmed root cause; `BL-028`/`BL-029` recorded.
- No change to `ai/clean_core_analysis/evidence_package.py` — `S4_CONVERSION_SIGNAL` and
  `DEPENDENCY_SIGNAL` were already in its `_TECHNICAL_CAPABILITIES` whitelist, confirmed by the new
  contract test rather than assumed.

## Known limitations
- `WHERE_USED_TABLE` real volume (1.18M rows) is truncated to the pre-existing
  `_MAX_RECORDS_PER_SECTION` cap (20,000) with an explicit warning — same bounded-import design the
  4 pre-existing curated sections already use, not a new limitation.
- The 124 real correlations found are all `MATCHED_HEURISTIC`, never `MATCHED_EXACT` — the
  pre-existing `BL-005` SAP-short-code-vs-internal-type-string gap (e.g. `CLAS` vs `class`), not a
  defect introduced by this sprint.
- Rodobens' already-persisted `CleanCoreAssessment` rows (from SPRINT-18) remain unchanged relative
  to the newly-available signals until an AI reprocessing run is executed — expected per ADR-012
  (seeding new evidence does not retroactively invalidate already-persisted AI output). A live
  `ai_reprocessing_applications` run (`PipelineRun` id 4854) was started post-review as additional
  validation and left in a safe `paused` state at 25/105 `application_discovery` items (durable,
  resumable, no orphaned `running` rows) when the environment was shut down — not required for this
  sprint's own demonstrable outcome, which was already confirmed directly via
  `build_clean_core_evidence_package`.
- `WHERE_USED_METHOD_MAP` and `SI_CHECKS` remain deliberately un-curated (`BL-028`, pre-existing
  `BL-009` note) — real shape not independently confirmed / non-flat nested structure.

## Deferred items
- `BL-028` — `WHERE_USED_METHOD_MAP`'s exact exported attribute shape not independently confirmed.
- `BL-029` — `Z_MASS_ABAP_DOWNLOAD`, filtered by the same `DEVCLASS` values, reproduces an equivalent
  source-object universe to Panaya's `REPOSITORY_OBJECTS`/`PROGRAMS`/`FUNCTIONS` (operational note).

## Repository closure
- Sprint branch: `sprint/19-panaya-evidence-signals`
- Official commit message: `feat(sprint-19): complete panaya evidence signal curation`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
