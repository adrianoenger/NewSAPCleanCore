# Session Handoff

## Current state
SPRINT-05 (Dependencies, ATC and Technical Findings) is **completed** on branch `main`.

## What was delivered

### Backend
- **Alembic 0006**: new tables `sap_object_dependency`, `atc_check`, `atc_run`, `atc_finding`, `technical_finding`.
- **`parsing/dependency_detector.py`**: detects CALL_FUNCTION, INCLUDE, INHERITS_FROM, USES_TABLE from ABAP source.
- **`atc/importer.py`**: schema-tolerant ATC XLSX importer (ADR-016 compliant):
  - workbook/sheet discovery (prefers "Data", falls back to first non-empty sheet)
  - header mapping by normalized alias (case-insensitive, whitespace-tolerant)
  - raw payload + canonical normalization + row-level warnings
  - ACCEPTED_FULL / ACCEPTED_PARTIAL / REJECTED status
  - Excel serial date normalization for `First Found On`
  - Sentinel values preserved in raw_payload
- **`api/routes/dependencies.py`**: GET object dependencies, POST detect-dependencies (per object or all).
- **`api/routes/atc.py`**: POST inspect (preview), POST import (persist), GET runs, GET run findings.
- **`api/schemas/sprint05.py`**: Pydantic schemas.
- **`api/schemas/ingestion.py`**: `ScanRead` now exposes `duration_seconds` (computed from `completed_at − started_at`).
- **`pyproject.toml`**: added `openpyxl>=3.1`, `python-multipart>=0.0.9`.

### Frontend
- **`components/atc/ATCImport.tsx`**: full ATC import panel (inspect → confirm → history with findings table).
- **`components/parsing/ObjectBrowser.tsx`**: added `DependenciesPanel` in object detail view.
- **`lib/api.ts`**: ATC and dependency fetchers/types. `ScanRecord` includes `duration_seconds`.
- **`components/ingestion/SourceIngestion.tsx`**: exibe duração do scan (ex.: `3.2s`, `1m 14s`) ao lado do horário de conclusão e no histórico de scans.
- **`components/shell/Sidebar.tsx`**: logo e botão "← Todos os assessments" retornam para a lista de assessments.
- **`Workspace.tsx`**: `atc` view renderiza `ATCImport`.

## Next sprint
SPRINT-06: **Durable Pipeline Execution** — slug `durable-pipeline-execution`.

## Restart instructions
Run `/clean-core-run-sprint` to start SPRINT-06.
