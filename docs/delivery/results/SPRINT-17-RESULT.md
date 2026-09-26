# SPRINT-17 Result — Demo Readiness

**Status:** Completed
**Completed at:** 2026-09-26
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Demo-hardening polish across the full PoC journey — no new domain capability, no schema change.
The three-panel shell (Sidebar/Workspace/Copilot) is now drag-resizable with persisted widths;
Technical View gained a real Monaco source-code viewer (backed by a new bounded backend
source-snippet endpoint) and a React Flow graph replacing the flat object-dependency list; every
primary result/list view now distinguishes a genuine fetch error from an empty result instead of
silently rendering a misleading empty state; and the persistent Acme demo assessment gained a
compact, reproducible ATC run and supplemental-evidence dataset (imported through the same real
adapter/durable-pipeline paths a live upload uses) so a fresh demo no longer starts from an
evidence-free assessment.

## Demonstration path
1. Open the Acme Industries "Clean Core PoC Assessment" from Assessments Home.
2. In "1 - Ingestão dos dados", see the completed scan and the "HANA_SIZING_ACME.TXT" supplemental
   evidence dataset (imported, 4 records) already present.
3. In "2 - Análise ATC", see the seeded `atc_demo_sample.xlsx` run (4 findings, all correlated to
   demo-source objects) — expand it to see per-finding correlation status.
4. In Technical View, select `ZPROGRAM_REPORT` — see its ABAP source rendered in Monaco with the
   object's own line range highlighted, its AI-derived understanding, and its dependency graph
   (React Flow: `ZPROGRAM_REPORT` → `USES TABLE` → `MARA`/`MARC`).
5. Drag the sidebar/Copilot resize handles — both panels resize live and keep their width after a
   full app reload (persisted via `localStorage`).
6. Browse Dashboard Geral (KPIs now reflect the seeded ATC findings), Executive View, Functional
   View and Architecture View — no regressions.
7. Ask the Copilot "Quantos objetos foram analisados nesta assessment?" — receive a grounded
   answer citing the structured summary; ask an ATC-detail question the current context package
   cannot ground — receive a graceful "sem evidência suficiente" refusal rather than a fabrication.

## Minimal validation executed
- [x] Backend: 229/229 pytest (224 pre-existing + 5 new in `test_source_snippet.py`, including 2
      path-traversal contract tests added for a security fix found during this sprint).
- [x] Frontend: `tsc --noEmit` (both tsconfigs) and `electron-vite build` clean.
- [x] Primary demonstrable user flow: live Playwright session against the electron-vite renderer
      over the persisted Acme Industries assessment (id 1074) covering the full path above,
      confirmed live end to end.
- [x] Critical contract introduced by this sprint: `GET /assessments/{id}/objects/{object_id}/source`
      bounded-read + path-containment behavior, covered by 5 backend tests.
- [x] No schema change — `alembic` head unchanged at `0016_embeddings`; `alembic check` shows only
      the pre-existing BL-013 drift, no new drift; no migration to apply.

## Key implementation notes
- `frontend/src/renderer/src/lib/useResizableWidth.ts` + `components/shell/ResizeHandle.tsx` —
  drag-resize with `localStorage` persistence, no new dependency; wired into `App.tsx` between
  Sidebar/Workspace and Workspace/Copilot. `Sidebar`/`CopilotPanel` take a `width` prop instead of
  a fixed Tailwind width class.
- `backend/src/api/routes/parsing.py::get_object_source` + `api/schemas/parsing.py::SourceSnippetRead`
  — bounded (512 KB) read straight from the scan's source directory (same `scan.source_path`+
  `rel_path` lookup pipeline stages already use), with `realpath`+`commonpath` path-containment
  verification and an absolute-path rejection (added after an automated security review flagged
  the initial version as a path-traversal gap — MEDIUM). `frontend/src/renderer/src/lib/monacoSetup.ts`
  bundles Monaco locally (`loader.config({monaco})`, no CDN — ADR-002 offline desktop) and relies
  on monaco-editor's own built-in `abap` Monarch language. `components/parsing/SourceViewer.tsx`
  renders it with the object's own line range highlighted.
- `frontend/src/renderer/src/components/parsing/DependencyGraph.tsx` (new `@xyflow/react`
  dependency) replaces Technical View's flat dependency list with a small graph centered on the
  selected object; target nodes stay plain labels (never navigable) since
  `SAPObjectDependency.target_name` is unresolved free text (BL-022/BL-016, untouched).
- `frontend/src/renderer/src/components/shared/ErrorState.tsx` wired into every primary
  list/summary query that previously only branched on `isLoading` — `DashboardGeral`,
  `ExecutiveView`, `ApplicationBrowser`, `BusinessRuleBrowser`, `ObjectBrowser`, `ATCImport` (runs
  list), `EvidenceDatasets`, `PipelineRunner`.
- `backend/src/atc/persistence.py::persist_atc_import` extracted out of
  `api/routes/atc.py::import_atc_file` (now shared by the route and the seed, no duplicated
  logic). `backend/src/seed/registry.py` (v6→v8): `_seed_demo_atc_import` (compact 4-finding ATC
  run) and `_seed_demo_evidence_dataset` (compact real-format HANA Sizing Report `.txt`, imported
  through the real adapter/durable-pipeline path) for the persistent Acme demo assessment.
- Live-found-and-fixed defects: React Flow's internal worker was blocked by `index.html`'s CSP
  (`script-src 'self'`, no `worker-src`) — added `worker-src 'self' blob:`; and the path-traversal
  fix above.

## Known limitations
- Monaco's own editor web worker cannot be wired up under electron-vite's Rollup build (neither
  the `?worker` suffix import nor `new URL(..., import.meta.url)` resolves) — Monaco falls back to
  running on the main thread, which is functionally fine for this read-only viewer but logs one
  console error per opened file. Deferred as BL-024.
- The dependency graph is scoped to Technical View's existing object-level dependencies only; a
  cross-application coupling graph in Architecture View remains blocked by the pre-existing
  `SAPObjectDependency.target_name` resolution gap (BL-022/BL-016), not introduced or fixed here.
- The same unguarded `scan.source_path`+`rel_path` join pattern the security fix addressed for the
  new source endpoint pre-exists (lower severity — no raw content returned over HTTP) in
  `api/routes/dependencies.py` and `pipeline/stages.py`. Deferred as BL-025.
- The persistent Acme assessment's existing Clean Core/Executive View AI analysis predates this
  sprint's new ATC run + evidence dataset, so its risk narratives currently read "no ATC
  findings/evidence reported" until "3 - Processamento por IA" is re-run — not a defect (ADR-012:
  seeding new evidence does not retroactively invalidate already-persisted AI output).

## Deferred items
- BL-024 — Monaco's editor web worker cannot be wired up under electron-vite's Rollup build.
- BL-025 — Pre-existing `scan.source_path`+`rel_path` joins elsewhere have no containment check.

## Repository closure
- Sprint branch: `sprint/17-demo-readiness`
- Official commit message: `feat(sprint-17): complete demo readiness`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
