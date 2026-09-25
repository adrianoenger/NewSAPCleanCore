# SPRINT-05 Result — Dependencies, ATC and Technical Findings

**Status:** Completed  
**Completed at:** 2026-09-24  
**Official commit:** resolve from Git history using `feat(sprint-05): complete dependencies atc and technical findings`

## Delivered increment

Schema-tolerant ATC XLSX importer (ADR-016 compliant) with Assessment-scoped correlation, ABAP dependency detection, deterministic technical findings model, and frontend panels for ATC import history and object dependency explorer. Scan processing time is now recorded and displayed in the ingestion UI.

## Demonstration path

1. Open the application; select or create a client and an assessment.
2. Navigate to **1 - Ingestão dos dados** and run a source scan on the demo ABAP directory. Observe scan duration displayed next to completion time.
3. In the same view, click **Parse** to extract SAP objects.
4. Open an object in the object browser and observe its detected dependencies (CALL_FUNCTION, INCLUDE, etc.).
5. Navigate to **2 - Análise ATC** and select an ATC `.xlsx` file.
6. Review the diagnostics card (worksheet, row count, recognized/missing/unknown columns, validation status).
7. Click **Confirmar importação**. The run appears in the history.
8. Expand the run row to see ATC findings with correlation status badges (MATCHED_EXACT, MATCHED_HEURISTIC, UNMATCHED, AMBIGUOUS).

## Minimal validation executed

- [x] 59/59 pytest pass (test_foundation + test_sprint05 + prior suites).
- [x] TypeScript typecheck clean.
- [x] All 10 ATC import-contract cases tested: full import, optional column removal, partial import, reordered columns, unknown extra column, blank optional values, sentinel preservation, malformed values, empty workbook rejection, Assessment-scoped correlation.
- [x] Alembic migration 0006 (`sap_object_dependency`, `atc_check`, `atc_run`, `atc_finding`, `technical_finding`) applies cleanly from 0005.
- [x] Backend healthy endpoint confirms migration revision `0006_dependencies_atc_findings`.
- [x] `duration_seconds` computed field added to `ScanRead` schema; frontend displays formatted duration.

## Key implementation notes

- `backend/alembic/versions/0006_dependencies_atc_findings.py` — 5 new tables with JSONB columns, FKs, indexes.
- `backend/src/parsing/dependency_detector.py` — regex + attribute-based ABAP dependency detection.
- `backend/src/atc/importer.py` — schema-tolerant workbook importer; `inspect_workbook` (preview) + `import_workbook` (persist).
- `backend/src/api/routes/atc.py` — inspect/import/list/findings endpoints; `_correlate_findings()` Assessment-scoped.
- `backend/src/api/routes/dependencies.py` — dependency detection and retrieval endpoints.
- `backend/src/api/schemas/ingestion.py` — `ScanRead.duration_seconds` computed via `model_validator`.
- `frontend/src/renderer/src/components/atc/ATCImport.tsx` — inspect → confirm → history flow.
- `frontend/src/renderer/src/components/parsing/ObjectBrowser.tsx` — `DependenciesPanel` in object detail.
- `frontend/src/renderer/src/components/ingestion/SourceIngestion.tsx` — scan duration display.
- `frontend/src/renderer/src/components/shell/Sidebar.tsx` — back-to-home navigation via logo and chevron button.

## Known limitations

- ATC findings table shows max 50 rows; pagination deferred.
- Dependency detection covers CALL_FUNCTION, INCLUDE, INHERITS_FROM, USES_TABLE; other dependency types deferred.
- Technical findings currently derived only from ATC import (PARSING source deferred to a future sprint).
- No bulk detect-dependencies trigger from the UI (API exists, no UI button).

## Deferred items

- None created during this sprint.

## Repository closure

- Sprint branch: `sprint/05-dependencies-atc-and-technical-findings`
- Official commit message: `feat(sprint-05): complete dependencies atc and technical findings`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
