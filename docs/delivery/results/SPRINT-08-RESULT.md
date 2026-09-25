# SPRINT-08 Result — Supplemental Evidence Foundation

**Status:** Completed
**Completed at:** 2026-09-25
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Introduced ADR-017's Supplemental Evidence Dataset model with adapter-based import: an Assessment can now optionally import Panaya ETL, SAP Signavio Process Insights, HANA Sizing Report, and SAP Readiness Check packages inside Step 1 ("Fontes Complementares"), each normalized into `EvidenceRecord`s and deterministically correlated to existing `SAPObject`s (`MATCHED_EXACT`/`MATCHED_HEURISTIC`/`UNMATCHED`/`AMBIGUOUS`), with drill-down from the Technical View. Import runs on the same durable `PipelineRun`/`StageRun`/`WorkItem` engine SPRINT-06 built for source processing (`PipelineRun.kind`), so pause/resume/retry/crash-recovery apply uniformly.

A prerequisite defect (BL-004) was fixed first: `SAPObject` identity is now stable across reprocessing (`canonical_key` upsert + reconciliation, migration 0008) instead of delete/recreate, so ATC and evidence correlations to an object survive a re-scan.

Post-completion, real user testing against actual customer exports (not synthetic fixtures) found and fixed several real defects invisible to synthetic data: the Panaya and Signavio adapters' originally-invented profiles did not match real export structure at all and were rewritten; two more real, stable SAP formats (HANA Sizing Report, SAP Readiness Check) were added; the FUE User Validation adapter was dropped entirely after a real sample proved its `.bin` payloads an undecodable proprietary format (~7.9 bits/byte Shannon entropy, no available decoder); dataset deletion (`DELETE /evidence-datasets/{id}`) was added so an accidental duplicate import can be removed; and reprocessing the source now automatically re-correlates every existing evidence dataset (closing a dangling-correlation gap in the original correlation model, since `EvidenceCorrelation.target_id` has no DB-level FK). The file inventory and scan-history sections of Step 1 were also made collapsible (default collapsed) per user feedback on information density.

## Demonstration path
1. Open an Assessment → Step 1 (Ingestão) → scan a directory with ABAP source (e.g. `/workspace/demo-source/ABAP`) → objects are parsed once Step 3 runs.
2. In Step 1's "Fontes Complementares" section, upload a Panaya ETL / Signavio / HANA Sizing / Readiness Check package → dataset appears with status `Importando…` → polls to `Importado` (or `Importado (parcial)` with an explicit warning if capabilities were detected but nothing matched) → shows records count and correlation summary (e.g. `MATCHED_EXACT: 2`).
3. Open an object in Technical View that the imported package references by name → "Evidência Suplementar (N)" panel lists the correlated records with provenance.
4. Click the trash icon on a dataset row → inline "Excluir? Sim/Não" confirmation → confirming removes the dataset (and its artifacts/records/correlations/pipeline run) from the list and from disk.
5. Re-scan/reprocess the same source directory after removing or renaming an object referenced by evidence → the existing evidence dataset's correlations update automatically (no re-import needed) to reflect the new object set.
6. The file inventory and scan-history blocks render collapsed by default, right after the active-scan-status section; clicking either expands it in place.

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint (backend `/health` reports `migration_revision: 0010_pipeline_run_kind`; DB confirmed at Alembic head via `alembic current`).
- [x] Critical contracts introduced by the sprint: adapter contract (`detect`/`inspect`/`plan_batches`/`import_batch`), `EvidenceDataset`/`Artifact`/`Record`/`Correlation` models, evidence-import pipeline stage, full evidence API (`inspect`/create/list/detail/delete/object-correlation drill-down) — covered by dedicated test modules per concern.
- [x] Primary demonstrable user flow: reproduced live via Playwright against the electron-vite renderer dev server (`localhost:5173`) against the real `Assessment01`/Rodobens assessment (read-only expand/collapse of both new collapsible sections, confirmed real scan-history and file-inventory content renders) and against a disposable throwaway assessment for the delete flow (upload → visible in list → trash icon → "Sim" → list returns to "Nenhuma evidência complementar importada ainda.", confirmed end-to-end against the real backend). Throwaway client/assessment/dataset removed afterward.
- [x] Required integration checks: full backend suite `pytest` **112/112** passed; frontend `tsc --noEmit` and `npm run build` both clean.
- [x] Migration applicability: `0008_stable_sap_object_identity` → `0009_evidence_foundation` → `0010_pipeline_run_kind` applied in sequence; `alembic current`/`heads` both at `0010_pipeline_run_kind`.

## Key implementation notes
- **`backend/src/persistence/models.py`**: `SAPObject.canonical_key`/`last_seen_stage_run_id` (migration 0008); `EvidenceDataset`/`EvidenceArtifact`/`EvidenceRecord`/`EvidenceCorrelation` (migration 0009); `PipelineRun.kind`/`evidence_dataset_id` (migration 0010).
- **`backend/src/evidence/adapters/`**: `base.py` (adapter contract, `SanitizingXMLStream`, `bulk_insert_evidence_records`), `panaya.py`, `signavio.py`, `hana_sizing.py`, `readiness_check.py` — each rewritten or written directly against a real customer export, documented per-adapter in its own module docstring. `fue.py` was implemented, then removed (see Known limitations).
- **`backend/src/evidence/correlation.py`**: `correlate_dataset_records` — deterministic exact/heuristic/unmatched/ambiguous matching, id-ordered pagination (5000/page) to stay bounded-memory at multi-million-record scale.
- **`backend/src/pipeline/stages.py`**: `_parse_process_item`/`_parse_finalize` upsert + reconcile `SAPObject` by `canonical_key`, then re-run `correlate_dataset_records` for every evidence dataset of the assessment (post-completion fix); `EVIDENCE_IMPORT_STAGES` registered under `STAGES_BY_KIND["evidence_import"]`.
- **`backend/src/api/routes/evidence.py`** / **`schemas/evidence.py`**: inspect/create/list/detail/delete + object-correlation drill-down; `_safe_basename`/`_resolve_under` guard against path traversal in the uploaded filename.
- **`frontend/.../evidence/EvidenceDatasets.tsx`**: "Fontes Complementares" section embedded in Step 1 (no fourth top-level step, per ADR-017); `DatasetRow` adds inline delete with confirmation.
- **`frontend/.../ingestion/SourceIngestion.tsx`**: new `CollapsibleSection` component; file inventory and scan history both collapsed by default; scan history repositioned to render immediately after the active-scan-status block and unconditionally (previously gated on `scans.length > 1`).
- **`backend/tests/`**: `test_sprint08.py` (stable identity), `test_evidence_correlation.py`, `test_evidence_panaya.py`, `test_evidence_signavio.py`, `test_evidence_hana_sizing.py`, `test_evidence_readiness_check.py`, `test_evidence_pipeline.py`, `test_evidence_api.py` — 112 tests total for this sprint's scope.

## Known limitations
- **FUE User Validation is not supported**, by decision, not oversight: a real sample's `.bin` payloads measured ~7.9 bits/byte Shannon entropy (indistinguishable from random/encrypted data), didn't decompress under zlib/gzip/bz2/lzma, and no specification is available — decoding it would mean guessing an undocumented binary schema, which ADR-017 explicitly prohibits. If a specification or decoder becomes available later, it can be added as a new adapter under the same contract.
- No automatic deduplication of re-imported evidence packages (BL-012) — importing the same file twice, or two different exports from the same provider, creates two independent datasets with no warning. The delete endpoint is today's manual mitigation.
- Panaya's curated-section list covers 5 of ~90 real top-level sections (BL-009); `WHERE_USED_*`/`SCI_HANA_ISSUES*` are known-valuable and not yet mapped to records (still counted in the manifest, not silently dropped).
- SAP short type codes (`CLAS`/`FUGR`/...) vs. internal long-form `object_type` strings degrade a genuinely exact correlation to `MATCHED_HEURISTIC` (BL-005) — low priority, deterministic fix available later.
- ATC import remains a standalone action (ADR-016/BL-002), not wrapped as a pipeline stage — untouched by this sprint.
- No AI/LLM processing exists yet anywhere in the product. "3 - Processamento por IA" is still only the deterministic scan/parse/detect_dependencies pipeline from SPRINT-06/07; real AI (Bedrock/Azure AI Foundry) is SPRINT-09+.

## Deferred items
- BL-005, BL-007, BL-008, BL-009, BL-011, BL-012 (all `Open`, low/medium priority, none blocking).
- BL-004, BL-006, BL-010 were opened and resolved within this same sprint.
- BL-002, BL-003 carried over from earlier sprints, unaffected by this one.

## Repository closure
- Sprint branch: `sprint/08-supplemental-evidence-foundation`
- Official commit message: `feat(sprint-08): complete supplemental evidence foundation`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
