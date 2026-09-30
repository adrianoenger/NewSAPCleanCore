# SPRINT-19 — Panaya Evidence Signal Curation

## Position in the sequence
- Prerequisite: SPRINT-18 completed.
- Coherence rule: extends the existing Panaya adapter strictly within ADR-017's accepted contract
  (same `PANAYA_ETL` dataset type, same `EvidenceDataset`/`EvidenceArtifact`/`EvidenceRecord`/
  `EvidenceCorrelation` model, no schema/migration change). Curating a new section is explicitly
  anticipated by ADR-017/BL-009 as "a one-line dict entry once its real attribute shape has been
  verified — never guessed" (`evidence/adapters/panaya.py` module docstring). Preserves evidence-first
  (ADR-008: correlation stays explicit/statused, no fabricated links) and structured/evidence-bound AI
  outputs (ADR-012: no change to any AI capability's schema or validation). No accepted ADR is
  contradicted.
- Origin: a real analysis session (2026-09-30) read the actual T-Systems/Panaya ABAP export program
  and the customer's `Z_MASS_ABAP_DOWNLOAD` extraction program (source files reviewed, not part of
  this repository) to resolve the open questions behind `BL-009` and `BL-026` with certainty instead
  of guessing.

## Goal
Persist two real, verified-correlatable Panaya sections that are currently counted in the dataset
manifest but never extracted as evidence — `SCI_HANA_ISSUES`/`SCI_HANA_ISSUES_DETAILS` (HANA/custom-
code readiness issues) and `WHERE_USED_TABLE` (table/include cross-reference) — so they reach
`SAPObject` correlation and flow into the Clean Core technical evidence pool, which already consumes
any correlated `EvidenceRecord` generically. This closes `BL-009` and the actionable part of `BL-026`.

## Confirmed findings this sprint builds on
Verified two ways: reading the real T-Systems/Panaya ABAP export program, and then — since the real
customer export turned out to still be available (see below) — an actual read-only `inspect()`/
attribute-sampling pass against it. Real section counts matched `BL-026`'s previously-recorded
numbers exactly (`SCI_HANA_ISSUES` 5,280 / `SCI_HANA_ISSUES_DETAILS` 7,038 / `WHERE_USED_TABLE`
1,182,072 / `WHERE_USED_METHOD_MAP` 32,839), confirming this is the same real file, and real sampled
rows confirmed/refined the attribute shapes:

- `SCI_HANA_ISSUES` (`TS_HANAA_SCI_CHECK`) really exports `OBJTYPE`/`OBJNAME`/`DEVCLASS` (confirmed
  live, e.g. `OBJTYPE=CLAS, OBJNAME=ZCLRNIPS_ASSIST_CONF, DEVCLASS=ZPS`) — the same shape already
  curated for `REPOSITORY_OBJECTS` — plus `SOBJTYPE`/`SOBJNAME` (sub-object/include) and a
  `DETAILS_REF` key.
- `SCI_HANA_ISSUES_DETAILS` (`TS_HANA_SCI_CHECK_DETAILS`) really exports `DETAILS_REF`, `TEXT`,
  `INCLUDE`, `LINE` (confirmed live; no `PROGRAM` attribute observed in the real sampled rows,
  contrary to the ABAP-source reading alone — the real export is authoritative, curate only the
  attributes actually observed) and joins back to its parent check by `DETAILS_REF`.
- `WHERE_USED_TABLE` (`WBCROSSGT` + `CROSS`, exported via `SELECT *`) really exports `OTYPE`,
  `NAME`, `INCLUDE`, `DIRECT`. **Important refinement from the real data:** `INCLUDE` (the
  referencing program/include) is a clean, correlatable object name — but `NAME` is **not** a plain
  object name; it is a compound cross-reference token whose structure depends on `OTYPE` (confirmed
  live, e.g. `OTYPE=DA, NAME=/EACC/CL_DMB_PROTOCOL\ME:SHOW_PROTOCOL\DA:LT_MESSAGE` — a data-object/
  variable reference path, not a bare `SAPObject` name). Only `INCLUDE` should drive correlation;
  `OTYPE`/`NAME`/`DIRECT` stay in `normalized_payload` as context, never as a second correlation key
  — treating `NAME` as an object name would silently manufacture false-confidence correlations, the
  exact failure ADR-017 forbids.
- `NOTES_HEADER` (`CWBNTHEAD`) genuinely has no object-linkage field anywhere in the export program —
  confirmed root cause, not an adapter gap and not fixable without adding a new, currently-absent
  `SELECT` to third-party vendor ABAP code. No further investigation is warranted; do not revisit
  without a fresh export or vendor source change.
- The real customer Panaya export is present at `SAP_Files/SAP Extra/Panaya/ETL_QAS_20260916_150001.xml`
  (2.8GB, gitignored) — `BL-026`'s "file no longer present" blocker no longer applies; use it for the
  live `inspect()`/import validation instead of a synthetic fixture.
- `Z_MASS_ABAP_DOWNLOAD`, run once per object type (`PROG`/`FUGR`/`CLAS`/`XSLT`) filtered by the same
  `DEVCLASS` values Panaya's `REPOSITORY_OBJECTS.DEVCLASS` attribute reports, reproduces an equivalent
  object universe to Panaya's `REPOSITORY_OBJECTS`/`PROGRAMS`/`FUNCTIONS` sections (both key off
  `TADIR.object`/`TADIR.devclass`). It extracts source code only — it cannot substitute for
  `NOTES_HEADER`/`SCI_HANA_ISSUES`/`WHERE_USED_TABLE`, which are metadata/signal sections, not source.
  This is an operational note for source re-acquisition, not an application capability.

## Planned capabilities
- CAP-001 — Curate `SCI_HANA_ISSUES` and `SCI_HANA_ISSUES_DETAILS` in
  `evidence/adapters/panaya.py::_CURATED_SECTIONS` (`object_name_attr="OBJNAME"`,
  `object_type_attr="OBJTYPE"`, `package_attr="DEVCLASS"`; sub-object `SOBJTYPE`/`SOBJNAME` and the
  `_DETAILS` rows' `DETAILS_REF`/`PROGRAM`/`INCLUDE` preserved in `normalized_payload`/
  `source_locator`), under the existing `S4_CONVERSION_SIGNAL` capability.
- CAP-002 — Curate `WHERE_USED_TABLE` (`WBCROSSGT`+`CROSS`) with `object_name_attr="INCLUDE"` only
  (never `NAME` — see the real-data refinement above), under the `DEPENDENCY_SIGNAL` capability
  (already declared in ADR-017, unused by any adapter until now).
- CAP-003 — Contract test proving the new `EvidenceRecord`s correlate to a matching `SAPObject` via
  the existing `evidence.correlation` pipeline (no new correlation logic expected) and are picked up
  unmodified by `ai.clean_core_analysis.evidence_package`'s technical pool.
- CAP-004 — Documentation closure: update `docs/data/supplemental-evidence-import-contract.md`'s
  Panaya profile with both newly verified section shapes; resolve `BL-009` and close the actionable
  part of `BL-026` in `BACKLOG.md` with the confirmed root cause; add two new low-priority backlog
  notes — `WHERE_USED_METHOD_MAP`'s exact exported attribute shape is not yet independently confirmed
  (defer curation, do not guess), and the `Z_MASS_ABAP_DOWNLOAD` DEVCLASS-alignment finding above.

## Demonstrable outcome
**Update (2026-09-30): the real customer export is available again** — found at
`SAP_Files/SAP Extra/Panaya/ETL_QAS_20260916_150001.xml` (2,797,696,676 bytes, matching the ~2.8GB
real export already referenced throughout ADR-017/`panaya.py`; gitignored via the existing
`SAP_Files/` rule, never to be committed). `BL-026`'s stated blocker ("the original raw Panaya `.xml`
export is no longer present in this environment") no longer holds. This upgrades validation from a
crafted fixture to the real file:

Run `inspect()` against the real file first (read-only, no DB writes) to confirm actual real-world
counts for `SCI_HANA_ISSUES`/`SCI_HANA_ISSUES_DETAILS`/`WHERE_USED_TABLE` before writing the curated-
section entries — this is the authoritative check ADR-017 requires ("never guess") and is stronger
than the ABAP-source read alone. Then import a Panaya `EvidenceDataset` from this real file through
the existing Evidence Datasets UI/API (curated-section batches only, per the adapter's existing
`_MAX_RECORDS_PER_SECTION` cap and per-batch re-stream design — full-file import already runs in
~230s per prior sprint validation) → the new `EvidenceRecord`s persist and correlate to matching real
`SAPObject`s from the same customer assessment → reprocessing the pipeline shows the owning
Application's Clean Core technical evidence citing at least one of the new records, visible through
the existing evidence citation UI (no new UI required).

If the real file's actual data turns out to diverge from the ABAP-source-verified shape in some way
not yet anticipated (e.g. an unexpected empty section, an attribute present in the program but never
populated in this specific export), treat the real file as authoritative and adjust the curated-
section mapping accordingly — do not force the plan's assumption over observed reality.

## Minimal validation
- ~~`inspect()` dry run against the real file confirms non-zero counts for both new sections~~ —
  **done during planning (2026-09-30)**: a read-only `inspect()` pass (no DB writes) against
  `SAP_Files/SAP Extra/Panaya/ETL_QAS_20260916_150001.xml` confirmed the counts above and an
  attribute-sampling pass confirmed the real shapes documented in "Confirmed findings". Re-run only
  if the curated-section implementation's own parsing disagrees with these already-observed samples.
- Adapter unit tests for the 2 new curated sections (`inspect`/`plan_batches`/`import_batch`) against
  a small crafted fixture using the real-observed attribute names above (fast, deterministic — the
  real 2.8GB file is for the one-time live import validation pass, not the repeatable test suite).
- One correlation contract test: the new records reach a `MATCHED_*` status against a matching
  `SAPObject`.
- One `clean_core_analysis` evidence-package test confirming the new capability surfaces in the
  technical pool.
- Full existing backend pytest suite stays green. Do not add broad coverage beyond this.

## Completion criteria
- Planned capabilities implemented or explicitly deferred with rationale.
- Demonstrable outcome reproduced successfully.
- Progress/state files updated.
- Application remains runnable for the next sprint.
