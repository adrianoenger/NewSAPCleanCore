# Session Handoff

## Current state
SPRINT-08 (Supplemental Evidence Foundation) is **completed** — closed by
`/clean-core-finish-sprint`. `docs/delivery/SPRINT-08-PROGRESS.yaml` is `status: completed`,
`progress_percent: 100`, `ready_for_review: false`; the result record is
`docs/delivery/results/SPRINT-08-RESULT.md`. The sprint branch was pushed and merged into `main`
by fast-forward; the local sprint branch was deleted (the remote copy is kept as the sprint
record).

**Next sprint:** SPRINT-09 — AI Object Understanding (`docs/delivery/sprints/SPRINT-09-ai-object-understanding.md`),
not started. Per this session's own repeated finding, "3 - Processamento por IA" today is still
only the deterministic scan/parse/detect_dependencies pipeline from SPRINT-06/07 — SPRINT-09 is
where real AI (Bedrock/Azure AI Foundry) first enters the product, and per BL-003 it should
register as additional stage(s) in the same durable `PipelineRun`/`StageRun`/`WorkItem` engine
rather than a parallel mechanism.

### Post-completion: FUE dropped, dataset deletion added, SourceIngestion UI adjustments (CAP-014)
After inspecting a real FUE export (see the Panaya/Signavio bug history below for how every
"invented profile" in this sprint turned out wrong), the `.txt` member carried no usable
structured data and every `.bin` member measured ~7.9 bits/byte Shannon entropy — indistinguishable
from random noise, not decompressible by zlib/gzip/bz2/lzma, no available specification. Per
ADR-017's own rule against guessing binary layouts, the user chose to drop FUE entirely rather
than keep a metadata-only stub: removed `evidence/adapters/fue.py`, `tests/test_evidence_fue.py`,
`EvidenceDatasetType.FUE_USER_VALIDATION`, and every FUE reference in ADR-017/the import contract
doc (now documented as a "Removal amendment" instead of silently deleted). The one real lingering
FUE dataset in the dev database (id=200) and its on-disk storage were removed manually.

Also delivered in the same pass, all user-requested:
- **Dataset deletion**: `DELETE /assessments/{id}/evidence-datasets/{dataset_id}` — deletes the
  `EvidenceDataset` row (cascades to artifacts/records/correlations/pipeline_run via existing FKs)
  and removes its on-disk storage directory. Frontend: a trash icon on each row in
  `EvidenceDatasets.tsx` with an inline "Excluir? Sim/Não" confirmation (no modal). Covered by
  `test_delete_dataset_removes_record_and_storage_file` in `test_evidence_api.py`.
- **`SourceIngestion.tsx` UI**: extracted a `CollapsibleSection` component (chevron toggle,
  default collapsed). The file inventory table and the scan history block now both use it. Scan
  history was also moved to render immediately after the active-scan-status block (previously
  after the file inventory table) and its visibility gate (`scans.data.length > 1`, which hid it
  entirely for a single scan — the reported "log de importações não aparece mais" bug) was
  removed in favor of the same always-render-but-collapsed pattern as the file inventory.
- **Answered a user question** about duplicate imports: there is no automatic deduplication today
  — every upload creates a new `EvidenceDataset` regardless of a matching `source_sha256`, by
  design (ADR-017: re-importing a new version must not silently overwrite historical provenance),
  but this means an accidental true duplicate (same file twice, or two exports of the same
  provider) double-counts records/correlations with no warning. Opened `BL-012`; the new delete
  endpoint is today's manual mitigation.

110/110 backend pytest (109 after FUE removal, +1 for the new delete test); frontend typecheck
clean.

### Post-completion: reprocessing source now automatically re-correlates existing evidence datasets (CAP-015)
The user asked what happens to supplemental evidence correlations when the source is
re-scanned/reprocessed after evidence was already imported. Investigating surfaced a real gap:
`EvidenceCorrelation.target_id` is a polymorphic column with **no DB-level foreign key** (it may
point at `SAPObject` today and other entity types later), so it is never automatically nulled or
refreshed when its target changes. The stable-identity reconciliation (CAP-001) already
adds/removes `SAPObject` rows on every reparse, but nothing re-ran evidence correlation
afterward — a removed object would leave a **dangling** correlation, and a newly-added/renamed
object would never be retroactively matched against evidence imported earlier. Given the choice
between fixing now vs. backlog, the user chose to fix now.

Fixed in `pipeline/stages.py::_parse_finalize`: after reconciling stale `SAPObject` rows, it now
loops every `EvidenceDataset` of the assessment and re-runs `evidence.correlation.correlate_dataset_records`
for each — fully automatic, no extra user action. Per-dataset failures are caught and mark that
dataset `FAILED` with an error (mirrors `_evidence_import_finalize`'s established safety net,
since `_run_stage` has no try/except around its call to `finalize` — an uncaught exception here
would silently lose even the object reconciliation that just ran). ADR-017's Correlation section
was amended to document this as required, not optional. 112/112 backend pytest (2 new:
`test_reprocessing_source_recorrelates_existing_evidence_datasets` confirms both directions —
a removed object's correlation flips to `UNMATCHED`, a newly-added object's previously-`UNMATCHED`
record becomes `MATCHED_EXACT` — and `test_parse_finalize_recorrelation_failure_does_not_lose_reconciliation`
is the safety-net regression).

Deleting an `EvidenceDataset` needed no equivalent fix: confirmed the full DB-level `ON DELETE
CASCADE` chain (`evidence_dataset` → `evidence_artifact`/`evidence_record` → `evidence_correlation`,
and → `pipeline_run` → `stage_run` → `work_item`) already removes everything belonging to that
dataset, so nothing downstream can reference it afterward — no separate re-correlation needed on
delete, only on the reprocessing-source side.

### Post-completion: Signavio adapter rewritten against a real ~28MB export (same root cause as Panaya)
The user reported the Signavio ZIP "importou com sucesso, mas 0 registros" — same class of bug as
Panaya: the original profile was invented (no sample existed at SPRINT-08 completion) and did not
match reality. Real structure: system metadata is ABAP-serialized XML (`<asx:abap>` namespace,
`<HEADER_DATA><item><KEY>k</KEY><VALUE>v</VALUE></item>...`, not simple attributes), and every
chunk's JSON nests everything under a `"dataSet"` key with the row array called `data` (not
top-level `rows` as assumed). ADR-017 and the import contract doc were amended.

**A quieter, more general bug this surfaced:** `_evidence_import_finalize` marked a dataset
`IMPORTED_FULL` whenever `inspect()`'s *predicted* capabilities were non-empty, regardless of
whether any batch actually produced a record — exactly how this mismatch went unnoticed as
"successful". Fixed generally (not Signavio-specific): it now forces `IMPORTED_PARTIAL` with an
explicit warning whenever an adapter reports capabilities but zero records were extracted, for
any adapter.

**Two more real, scale-only bugs found while validating against the actual ~28MB file (494
chunks, ~4.4M total rows)** — the user then asked whether parallel imports are safe, prompting a
closer look at real timing, which surfaced these:
1. A chunked bulk `INSERT ... ON CONFLICT DO NOTHING` (the fix for Signavio's per-row
   existence-check not scaling) still crashed once a single chunk's row count (~9600) × 7
   columns exceeded PostgreSQL's 65535-bind-parameter limit — same failure class as the
   correlation crash CAP-012 fixed. Generalized the fix into
   `evidence/adapters/base.py::bulk_insert_evidence_records` (auto-chunked, counts actually-
   inserted rows via `RETURNING` since `cursor.rowcount` is unreliable for a multi-row insert).
2. **Critical**: even after (1), `correlate_dataset_records` still loaded every `EvidenceRecord`
   of a dataset as an ORM object before correlating. Live-tested at 4.4M records, this pushed the
   backend container to **~20GB RSS and 100% CPU** — killed manually before risking an OOM crash
   of the shared container. Fixed with id-ordered pagination (5000 records/page,
   `evidence/correlation.py::_PAGE_SIZE`) plus an executemany-style `insert()` for the
   correlation rows themselves. While fixing this, caught a second footgun in the fix's first
   draft: it called `session.expunge_all()` per page, which would have silently detached
   whatever *other* ORM object the caller (`_evidence_import_finalize`'s own `dataset`) held in
   the same session — any attribute changes set on it after that point would never be
   flushed/committed, reproducing yet another "stuck forever" variant. Fixed to expunge only
   that page's own `EvidenceRecord` objects.

**Validated end-to-end against the real file three times** as each fix landed — the final,
fully-fixed run: 494 chunks, 4,375,818 records, `IMPORTED_FULL`, `capabilities=['PROCESS_KPI']`,
913.6s total, backend container memory never exceeded ~350MB (monitored live via `docker stats`
throughout). All validation runs' data were removed from the dev database afterward.

112/112 backend pytest (`test_evidence_signavio.py` rewritten with a real-shaped fixture plus a
10k-row bind-parameter-limit regression test; `test_evidence_correlation.py` gained a pagination
+ caller-object-survives-detachment regression test using a monkeypatched tiny page size). BL-010
resolved (the concern was confirmed for real, not just theoretical); BL-011 opened noting Panaya/
HANA-sizing/Readiness-Check still use the slower per-row pattern, not yet proven necessary to fix
at their much smaller confirmed real-world scale.

### Post-completion: Panaya adapter rewritten against a real ~2.8GB export
The user provided a real Panaya ETL export (`ETL_QAS_20260916_150001.xml`, 2.8GB) — the first
real sample seen for any of the three original SPRINT-08 formats (Panaya/Signavio/FUE all
shipped with an invented profile since no sample existed at the time). The original
`<PanayaExport>` profile did not match reality at all; the adapter was rewritten from scratch.

**Real structure** (verified by streaming the entire file once): a bare, unzipped `.xml` (not
wrapped in a ZIP as assumed) — one `<ROOT_ELEMENT>` with `<HEADER .../>` (system metadata as
attributes) and ~90 sibling sections (`<REPOSITORY_OBJECTS>` 64k rows, `<PROGRAMS>` 68k,
`<WHERE_USED_TABLE>` 1.18M, `<SCI_HANA_PERFORMANCE_ISSUES_DETAILS>` ~5M, ...). ADR-017 and
`docs/data/supplemental-evidence-import-contract.md` were amended with the real profile.

**Two real, load-bearing problems the invented profile never anticipated:**
1. **Not strictly well-formed XML.** Raw ABAP/text content carried a literal illegal control
   byte (`0x1C`) and an escaped illegal numeric character reference (`&#0;` for a NUL byte in a
   garbled field) — both forbidden by the XML 1.0 `Char` production, both abort `expat` with no
   way to resume. `evidence/adapters/base.py::SanitizingXMLStream` strips both in a streaming
   wrapper before the parser ever sees them.
2. **Scale.** Importing every row of every section (single-digit millions in the largest) is not
   a PoC-appropriate goal. `evidence/adapters/panaya.py::_CURATED_SECTIONS` extracts only 5
   sections with a verified, correlatable attribute shape (`REPOSITORY_OBJECTS`, `PROGRAMS`,
   `FUNCTIONS`, `MODIFICATIONS`, `NOTES_HEADER`), each capped at 20k records with an explicit
   truncation warning; every one of the ~90 sections is still counted in `inspect()`'s manifest.
   Each import batch = one curated section, re-streamed from the top and stopped as soon as that
   section closes (random access into a multi-gigabyte file isn't practical).

**Three more real bugs found and fixed while validating against the actual file** (none a
synthetic fixture would have caught — all only manifest at real scale/content):
1. `SanitizingXMLStream.read()` could return `b""` before the source was truly exhausted (an
   artifact of the tail-buffering logic) — violates the file-like `read()` contract; a real
   caller (expat) is entitled to treat that as EOF and would have silently truncated the parse.
2. The illegal-char-ref regex ran on the *emitted* slice instead of the full carry+raw buffer,
   so a reference like `&#0;` could be split exactly at a read-boundary and leak through
   unstripped — caught by a test using a deliberately tiny read size to force the split.
3. `evidence.correlation.correlate_dataset_records` deleted prior correlations via
   `EvidenceCorrelation.evidence_record_id.in_([r.id for r in records])` — a real ~180k-record
   import crashed with `psycopg.OperationalError: number of parameters must be between 0 and
   65535` (PostgreSQL's bind-parameter ceiling). Fixed with a subquery instead of a materialized
   id list. This also exposed that `_run_stage` has no `try`/`except` around its call to
   `finalize` — the crash left `dataset.status` uncommitted, reproducing the exact "stuck
   forever" failure mode already fixed for `prepare`; `_evidence_import_finalize` now catches a
   correlation failure the same way.

**Validated end-to-end against the real 2.8GB file three ways**: (a) `inspect()` alone — 98s,
correctly counted all 90 sections; (b) direct pipeline script — 226.5s, `IMPORTED_PARTIAL`,
84,189 records (4 of 5 curated sections hit the cap); (c) the real HTTP upload endpoint — 42.75s
to upload+hash, background processing to the same `IMPORTED_PARTIAL`/84,189 outcome, confirmed via
polling. All three validation runs' data were removed from the dev database afterward (real
customer file, `SAP_Files/` gitignored, never committed).

109/109 backend pytest (rewrote `test_evidence_panaya.py` entirely against the real schema,
updated the old-schema fixtures in `test_evidence_pipeline.py`/`test_evidence_api.py`, added a
finalize-safety-net regression test). BL-006 resolved (superseded by this rewrite); BL-009
(extend curated sections — `WHERE_USED_*`/`SCI_HANA_ISSUES*` are known-valuable, not yet mapped)
and BL-010 (correlation pass has no upper bound on records loaded) opened for follow-up.

### Post-completion scope extension: two more evidence formats (user-requested, ADR-017 amended)
The user asked to add two more real files as evidence sources: a HANA Sizing Report
(`/SDF/HDB_SIZING` plain-text output) and the SAP Readiness Check for SAP S/4HANA Conversion
(`.docx`). This expands ADR-017's originally-enumerated 3 dataset types — explicitly authorized
by the user (asked first: implement now vs. backlog for a future sprint; chose now, since it
reuses the exact same adapter architecture ADR-017 already built for extensibility). ADR-017 and
`docs/data/supplemental-evidence-import-contract.md` were amended with the new profiles.

- **`evidence/adapters/hana_sizing.py`**: parses the report's ASCII-box structure generically (no
  hard-coded box titles — recognizes rule lines / `|`-bordered rows / inner header separator).
  A box row whose first column looks like a plausible SAP object name (`^[A-Z0-9_/]{2,30}$`)
  becomes a table-level `USAGE_SIGNAL` record correlatable to `SAPObject`; everything else is a
  dataset-level sizing metric. Loose `label   value` lines outside any box become manifest
  metadata (SID, NW release, DB type/version, ...).
- **`evidence/adapters/readiness_check.py`**: parses the official SAP `.docx` template via
  `python-docx` (new dependency). Classifies each of the document's ~40+ tables by **header row
  text**, never by index (table count/order isn't guaranteed stable across report
  versions/customers) — Simplification Items and custom-code check summaries become
  `S4_CONVERSION_SIGNAL` (Assessment-level, no object correlation); table volume/sizing tables
  become `USAGE_SIGNAL` (correlatable), same as the standalone HANA sizing report; system-metadata
  tables feed the manifest only. Unrecognized tables are counted, never dropped silently.
- Both registered in `evidence/adapters/__init__.py`'s `ADAPTERS` dict; `EvidenceDatasetType`
  gained `HANA_SIZING_REPORT`/`SAP_READINESS_CHECK` (plain `String(50)` column — no migration).
- **Validated against the user's actual real files** (not just synthetic fixtures — a first for
  this sprint, since no real Panaya/Signavio/FUE samples ever existed): a manual script ran both
  through the real durable pipeline end to end. The 40KB real HANA sizing file produced 325
  records (20 recognized boxes); the 241KB real Readiness Check produced 337 records (46 tables,
  4 simplification-item tables + 2 custom-code-check tables + 2 table-volume tables recognized,
  35 correctly left unrecognized/uncounted-as-error). Both reached `IMPORTED_FULL`. The script and
  its test assessment were not committed/persisted (real customer data; `SAP_Files/` is
  gitignored) — cleaned up from the dev database afterward.
- Frontend: added the two new types to `DATASET_TYPE_LABELS` in `EvidenceDatasets.tsx` and
  `ObjectBrowser.tsx`; upload `accept` widened to `.zip,.txt,.docx`.
- 106/106 backend pytest (7 new: `test_evidence_hana_sizing.py` ×4, `test_evidence_readiness_check.py` ×3, both with synthetic fixtures since the real files can't be committed); frontend typecheck+build clean.

### Post-completion user validation found and fixed two more real bugs
After the sprint reached `ready_for_review`, the user tried the feature for real and hit two
issues, both fixed on this same branch:

1. **Detection was filename-only.** `adapter.detect(filename)` only matched a filename literally
   containing "panaya"/"signavio"/"fue" — a real export's filename essentially never does, so
   every real upload was rejected as "Unrecognized". Fixed: `detect(filename, file_path)` now
   sniffs actual content (Panaya's XML root tag `PanayaExport`, Signavio's `system.xml` root tag
   `SignavioSystem` + chunked JSON, FUE's `.txt`+`.bin` pair) via
   `evidence/adapters/base.py::peek_xml_root_tag`; the filename is now only a fast-path hint. Both
   `inspect_evidence_package` and `create_evidence_dataset` now stream the upload to disk *before*
   calling `detect_adapter`, since detection needs real bytes.
2. **A real 151MB Panaya.zip appeared stuck "processing forever".** Root cause:
   `zipfile` raised `NotImplementedError`/`RuntimeError` for an unsupported compression method
   (a real-world export limitation, e.g. WinZip AES) while reading inside `adapter.inspect()`,
   called from `_evidence_import_prepare`. `_run_stage` handles a `prepare`-time exception by
   returning `"failed"` *without* ever calling `finalize` — so `dataset.status` stayed stuck at
   `INSPECTED` forever even though the `PipelineRun`/`StageRun` correctly showed `"failed"`.
   Fixed at two layers: (a) `panaya.py`/`signavio.py`/`fue.py`'s `inspect()` now catch
   `NotImplementedError`/`RuntimeError` and return a clean `IMPORTED_PARTIAL`-bound warning
   instead of crashing; (b) `_evidence_import_prepare` itself now marks `dataset.status = FAILED`
   + commits before re-raising, as a safety net for anything an adapter doesn't catch. Covered by
   `test_evidence_import_prepare_failure_marks_dataset_failed_not_stuck` and
   `test_evidence_import_prepare_exception_marks_dataset_failed` in `test_evidence_pipeline.py`.

### Critical incident: the backend test suite was destroying real dev-database data
While investigating bug #2 above, discovered that **every** `backend/tests/*.py::_cleanup`
function ran unscoped `DELETE FROM {table}` statements (client, assessment, sap_object,
evidence_dataset, ...) against the shared dev Postgres database — there is no separate test
database. Running `pytest -q` to validate the bug fixes above destroyed the user's real client,
assessment, and all three evidence datasets they had just imported (Panaya, Signavio, FUE) — the
"stuck" dataset wasn't stuck, it (and everything else) had been deleted out from under them.

**Fixed across all 13 affected test files** (`test_sprint01/02/03/05/06/07/08.py`,
`test_evidence_api/correlation/fue/panaya/pipeline/signavio.py`): every `_cleanup` now takes the
specific `assessment_id`(s) (or `client_id`) that test itself created and deletes only
`client WHERE id = (SELECT client_id FROM assessment WHERE id = :aid)` — cascading correctly
through the existing FK `ON DELETE CASCADE` chain without touching any other assessment's data,
and never touching shared catalogs like `atc_check`. Verified empirically: created a marker
client ("REAL USER DATA - DO NOT DELETE"), ran the full 99-test suite, confirmed the marker
survived, then deleted it manually. See the `project-test-isolation` memory for full detail and
BL-007/BL-008 in `BACKLOG.md` for residual risk (no dedicated test database yet; `recover_orphans`
is still called with global, unscoped effect from one test).

Before this sprint's branch was created, pre-existing uncommitted documentation/architecture
work from a previous session (ADR-017 acceptance, baseline bump to R3.3, sprint renumbering
08→17) was committed directly to `main` (commit `4711ab0`), per explicit user decision — it
was bookkeeping, not sprint implementation, so it did not belong inside the sprint branch/commit.

## Why this sprint existed
ADR-017 introduced optional supplemental evidence packages (Panaya ETL, SAP Signavio Process
Insights, FUE 4SAP User Validation) as an Assessment evidence layer, and required fixing a
pre-existing weakness (BL-004): the parse stage deleted and recreated `SAPObject` rows on every
reprocess, which would have silently broken ATC and future evidence correlations.

## What was delivered

### CAP-001 — Stable SAPObject identity
- `sap_object.canonical_key` (deterministic `f"{object_type.upper()}::{object_name.upper()}"`,
  unique per assessment) and `sap_object.last_seen_stage_run_id` (migration
  `0008_stable_sap_object_identity`, with dedup of pre-existing duplicate rows and FK repoint
  of `atc_finding.correlated_object_id`/`technical_finding.sap_object_id` to the survivor).
- `pipeline/stages.py::_parse_process_item` now upserts by `canonical_key` instead of
  delete/recreate; `_parse_finalize` reconciles (removes) objects no longer produced by any
  file in the current scan once the stage completes.

### CAP-002 — Evidence persistence
`EvidenceDataset`, `EvidenceArtifact`, `EvidenceRecord`, `EvidenceCorrelation` ORM models +
migration `0009_evidence_foundation` (revision id shortened from the natural
`supplemental_evidence_foundation` — Alembic's `alembic_version.version_num` is `VARCHAR(32)`).

### CAP-003 — Adapter contract + correlation service
- `evidence/adapters/base.py`: `InspectionResult`/`ImportBatchPlan`/`ImportBatchOutcome` +
  the `EvidenceDatasetAdapter` Protocol (`detect`/`inspect`/`plan_batches`/`import_batch`).
- `evidence/correlation.py::correlate_dataset_records`: exact/heuristic/unmatched/ambiguous/
  not-applicable matching against `SAPObject`, mirroring ATC's `_correlate_findings` semantics.

### CAP-004/005/006 — Panaya / Signavio / FUE adapters
No reviewed sample existed for any of these three formats at the time (unlike ATC's reviewed
XLSX) — each adapter's recognized structure is documented in its own module docstring. Panaya and
Signavio were later rewritten against real samples (see the post-completion sections above); FUE
was later dropped entirely once a real sample proved its `.bin` payloads undecodable (CAP-014).
- **Panaya** (`evidence/adapters/panaya.py`): ZIP + streaming XML (`defusedxml.ElementTree.iterparse`,
  bounded memory), `[start,end)`-index batches re-streamed per call (documented PoC trade-off —
  see BL-006 for the production-scale alternative).
- **Signavio** (`evidence/adapters/signavio.py`): ZIP + system XML + chunked JSON, one chunk = one
  batch, preserves `keyFigureId`/system/timestamp/member provenance.
- **FUE**: removed (CAP-014) — see the post-completion section above.
- `evidence/adapters/__init__.py`: `ADAPTERS` registry + `detect_adapter(filename)`.
- `defusedxml` added as a dependency (XXE hardening for untrusted uploaded XML — flagged by the
  security-guidance hook, not originally planned).

### CAP-007 — Durable pipeline engine generalization
`PipelineRun.kind` (`source_processing` | `evidence_import`) + `PipelineRun.evidence_dataset_id`
(migration `0010_pipeline_run_kind`). `pipeline/stages.py::STAGES_BY_KIND` registers the existing
scan/parse/detect_dependencies stages under `source_processing` and a new `import_evidence` stage
(prepare→plan_batches, process→import_batch, finalize→set dataset status + run
`correlate_dataset_records`) under `evidence_import`. `pipeline/engine.py::create_pipeline_run`
now takes `kind`/`evidence_dataset_id`; the run loop itself is unchanged — same durable
WorkItem-level pause/resume/retry as SPRINT-06.

### CAP-008 — API
`api/routes/evidence.py` + `api/schemas/evidence.py`, registered in `main.py`:
- `POST /assessments/{id}/evidence-datasets/inspect` — preview, no persistence.
- `POST /assessments/{id}/evidence-datasets` — streams the upload to
  `settings.evidence_storage_path` (never buffers it fully in memory), fingerprints it, creates
  the `EvidenceDataset` + a `PRIMARY` `EvidenceArtifact`, and starts a background
  `evidence_import` `PipelineRun`.
- `GET /assessments/{id}/evidence-datasets` / `/{dataset_id}` — KPIs (records_count,
  correlation_summary, latest pipeline run status).
- `GET /assessments/{id}/objects/{object_id}/evidence-correlations` — drill-down from a
  `SAPObject` to every correlated `EvidenceRecord`.

### CAP-009 — Frontend
- `components/evidence/EvidenceDatasets.tsx`: upload + list, embedded inside
  `SourceIngestion.tsx` (Step 1) as "Fontes Complementares" — **not** a fourth top-level step,
  per ADR-017's UI decision. Polls while any dataset is `INSPECTED`/`IMPORTING`.
- `components/parsing/ObjectBrowser.tsx`: `EvidencePanel` inside the object detail view shows
  correlated evidence records ("Evidência Suplementar (N)").
- `lib/api.ts`: `EvidenceDatasetRecord`/`EvidenceCorrelationRecord` types + fetchers.

### CAP-010 — Validation
- **Security fix**: a background security review flagged a HIGH path-traversal/arbitrary-file-write
  in `api/routes/evidence.py` — the raw upload `filename` was joined into a filesystem path
  unsanitized. Fixed with `_safe_basename()` (strips directory components, rejects literal
  backslashes/degenerate names) and `_resolve_under()` (defense-in-depth root-containment check)
  in both `inspect_evidence_package` and `create_evidence_dataset`; covered by
  `test_safe_basename_strips_traversal_and_rejects_degenerate_names` and
  `test_path_traversal_filename_never_escapes_storage_root`.
- **User-reported bug fix**: manual testing hit "Unrecognized evidence package format" for
  every upload. Root cause — `adapter.detect()` only matched a filename literally containing
  "panaya"/"signavio"/"fue", which a real export's filename essentially never does. Fixed by
  changing the contract to `detect(filename, file_path)`: content is now sniffed (Panaya's
  primary-XML root tag `PanayaExport`, Signavio's `system.xml` root tag `SignavioSystem` +
  chunked JSON, FUE's `.txt`+`.bin` member pair) via `evidence/adapters/base.py::peek_xml_root_tag`;
  the filename hint is now only a fast-path shortcut. Both `inspect_evidence_package` and
  `create_evidence_dataset` now stream the upload to disk *before* calling `detect_adapter`, since
  detection needs real content. Verified live via curl: a ZIP named `generic_export.zip` (no
  provider name anywhere) with Panaya-shaped content now detects as `PANAYA_ETL` and reaches
  `IMPORTED_FULL`.
- **Backend**: 97/97 pytest (`test_sprint08.py`, `test_evidence_correlation.py`,
  `test_evidence_panaya.py`, `test_evidence_signavio.py`, `test_evidence_fue.py`,
  `test_evidence_pipeline.py`, `test_evidence_api.py`, plus all pre-existing suites still green).
- **Frontend**: `npm run typecheck` and `npm run build` both clean.
- **Live browser E2E** (Playwright against the electron-vite renderer, `localhost:5173`):
  created client/assessment → ingested `demo-source/ABAP` → processed via Step 3 → uploaded a
  synthetic Panaya ZIP through Step 1's "Fontes Complementares" → dataset reached "Importado"
  with 5 records and capabilities `TECHNICAL_OBJECT_METADATA`/`USAGE_SIGNAL` → correlation
  summary showed 3 `UNMATCHED` + 2 `MATCHED_HEURISTIC` (heuristic, not exact, because the
  fixture's SAP short type code `CLAS` doesn't literally equal the internal `class` string —
  see BL-005) → opened `ZCL_UTILITY_HELPER` in Technical View and confirmed "Evidência
  Suplementar (2)" listing both correlated Panaya records. Test data cleaned up afterward.

## Known deferrals / backlog
- **BL-004 resolved** by CAP-001 (see above).
- **BL-005** (new): SAP short type codes (`CLAS`/`FUGR`/`PROG`/...) vs internal
  `object_type` strings degrade what should be exact matches to heuristic, in both the new
  evidence correlator and ATC's existing one. Low priority, deterministic fix, not required now.
- **BL-006** (new): Panaya's per-batch re-streaming is bounded-memory but O(n_batches × skipped
  elements) I/O — fine for the PoC's small fixtures, would want a byte-offset checkpoint for a
  real multi-GB Panaya export.
- **BL-012** (new): no automatic deduplication of re-imported evidence packages — see CAP-014
  above.
- ATC import remains standalone (ADR-016, BL-002) — untouched by this sprint.
- No AI/LLM processing yet. SPRINT-09 (AI Object Understanding) will need Bedrock/Azure Foundry
  credentials for end-to-end validation, and per BL-003 should register with the same
  `StageDefinition`/`PipelineRun` engine this sprint generalized (`STAGES_BY_KIND`).

## Next steps
SPRINT-08 is closed. Run `/clean-core-run-sprint` to start SPRINT-09 (AI Object Understanding) —
it will sync `main`, create branch `sprint/09-ai-object-understanding`, and begin from that
sprint's first capability. SPRINT-09 will need Bedrock/Azure AI Foundry credentials configured for
end-to-end validation (see `docs/delivery/sprints/SPRINT-09-ai-object-understanding.md`).

## Restart instructions
SPRINT-08 has no unfinished work — `docs/delivery/SPRINT-08-PROGRESS.yaml` is `status: completed`
and all 15 capabilities are `done`. If resuming this session unexpectedly with no sprint branch
checked out, `main` is the correct branch to be on; the next action is `/clean-core-run-sprint`
for SPRINT-09, not a resume of SPRINT-08.
