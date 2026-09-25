# SPRINT-04 Result — Assessment-Centric Product Alignment

**Status:** Completed  
**Completed at:** 2026-09-24  
**Official commit:** resolve from Git history using `feat(sprint-04): complete assessment-centric product alignment`

## Delivered increment
Corrective alignment of the entire application to the canonical `Client → Assessment` hierarchy defined by ADR-015 and Baseline R3.2. The independent `SAPSystem` entity was removed; `sap_source_system` is now an Assessment attribute. The Assessments Home screen replaced ClientHub as the application entry point, and all API, ORM, seed, and frontend components were updated consistently.

## Demonstration path
1. Start the application (`npm run dev` in `frontend/`; containers up).
2. Application opens directly on **Assessments Home** — grid showing Acme Industries / Clean Core PoC Assessment and Rodobens / Assessment01; no left sidebar visible.
3. Click **Novo Assessment** or **Novo Cliente** to test creation modals.
4. Click an assessment row to open it; left sidebar appears with `Clean Core` (Ingestão, ATC, IA) and `Resultado` (Dashboard, Executive, Technical, Functional, Architecture) groups.
5. Click **Ingestão dos dados** — Source Ingestion panel opens with blank directory field and `Start Scan` disabled.
6. Click **Technical View** — ObjectBrowser displays 6 parsed SAP objects from the demo scan.

## Minimal validation executed
- [x] 35/35 pytest (backend foundation + sprint01 + sprint02 + sprint03 suites)
- [x] TypeScript typecheck clean
- [x] Alembic migration 0005_assessment_alignment at head
- [x] GET /assessments returns 2 assessments (Acme + Rodobens)
- [x] GET /assessments/{id}/objects returns 6 SAP objects for demo assessment
- [x] Assessments Home renders; assessment-only sidebar present after opening assessment
- [x] Source Ingestion: blank path, Start Scan disabled until directory selected
- [x] ObjectBrowser accessible from Technical View; no regression

## Key implementation notes
- `backend/alembic/versions/0005_assessment_centric_alignment.py` — drops `sap_system` table, adds `assessment.client_id` FK and `assessment.sap_source_system` text column.
- `backend/src/persistence/models.py` — `SAPSystem` class removed; `Assessment` updated with `client_id`/`client` relationship/`sap_source_system`.
- `backend/src/api/routes/clients.py` — new standalone `/assessments` CRUD endpoints; nested SAPSystem routes removed.
- `backend/src/api/schemas/client_system_assessment.py` — `AssessmentListItem` includes `client_name` for home grid.
- `frontend/src/renderer/src/components/home/AssessmentsHome.tsx` — new component; grid, filters, modals.
- `frontend/src/renderer/src/components/hub/ClientHub.tsx` — deleted.
- `App.tsx`, `Sidebar.tsx`, `Workspace.tsx` — orchestrate home vs. workspace; sidebar only inside assessment.
- `SourceIngestion.tsx` — blank path start, Start Scan disabled guard.
- `backend/src/seed/registry.py` — seed v6: Client → Assessment directly; no SAPSystem.

## Known limitations
- AssessmentsHome uses static mock data for demo; real API calls introduced by SPRINT-05 work items.
- ATC, AI processing, dashboards, and result views are placeholders — to be implemented in later sprints.
- ObjectBrowser shows only the demo Rodobens assessment scan.

## Deferred items
None — all planned capabilities delivered.

## Repository closure
- Sprint branch: `sprint/04-assessment-centric-product-alignment`
- Official commit message: `feat(sprint-04): complete assessment-centric product alignment`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
