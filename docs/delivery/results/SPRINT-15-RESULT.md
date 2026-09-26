# SPRINT-15 Result — Result Navigation Perspectives

**Status:** Completed
**Completed at:** 2026-09-26
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Dashboard Geral and Executive View are now real pages (previously `PlaceholderView` stubs) built
on a new backend results-summary aggregation endpoint. All five result views (Dashboard Geral,
Executive, Technical, Functional, Architecture) share a lifted navigation/drill-down state
(`ResultFocus`) so clicking a business rule, finding, or source object in one view opens the
right entity pre-selected in another, while the Assessment/Client breadcrumb and the permanent
right-side Copilot stay mounted and context-aware throughout (ADR-009/ADR-010/ADR-015).

## Demonstration path
1. Open the "Clean Core PoC Assessment" (Acme Industries) — a fully processed assessment with
   discovered applications, business rules and Clean Core assessments.
2. Open **Dashboard Geral**: see real KPI cards (objects analyzed, customizations identified,
   critical findings, high-impact objects, business rules identified) and click the "Executive
   View" quick-nav card.
3. In **Executive View**, click a top technical risk or roadmap item — lands in **Architecture
   View** with that Application pre-selected and its Clean Core panel expanded.
4. Click one of the Application's business rules — lands in **Functional View** with that rule
   pre-selected.
5. Click the rule's "Objeto de origem" — lands in **Technical View** with that SAPObject
   pre-selected, showing its AI understanding and a "Proposta de Remediação" panel sourced from the
   owning Application's Clean Core recommendation.
6. Click the remediation panel — lands back in **Architecture View** on that Application.
   Throughout steps 2–6, the Assessment/Client breadcrumb and the Copilot panel/context label
   (`assessment: <name> · <view>`) never disappear or reset.
7. Click a Resultado nav item directly in the sidebar (not a drill-down) — the target view opens
   with no stale selection (confirms sidebar navigation clears drill-down focus correctly).

## Minimal validation executed
- [x] Backend: 215/215 pytest (213 pre-existing + 2 new for `GET /dashboard-summary`), run twice
      (once before and once after exposing `SAPObjectRead.application_id`).
- [x] Frontend: `tsc --noEmit` (both tsconfigs) and `electron-vite build` clean.
- [x] Primary demonstrable user flow: live Playwright session against the electron-vite renderer,
      driving the full drill-down chain described above over a live-Bedrock-reprocessed Acme
      Industries assessment (real applications/business rules/Clean Core data, not mocked).
- [x] Context-preservation contract: Assessment/Client breadcrumb and Copilot panel/context label
      verified present and correct after every navigation in the chain above.
- [x] No schema change — `alembic` head unchanged at `0016_embeddings`; no migration to apply.

## Key implementation notes
- `frontend/src/renderer/src/lib/resultNav.ts` — `ResultFocus` union + `FOCUS_VIEW` mapping; lifted
  into `App.tsx` (`selectView` vs. `navigateToFocus`) and threaded through `Workspace.tsx`.
- `backend/src/api/routes/dashboard.py` + `api/schemas/dashboard.py` — `GET
  /assessments/{id}/dashboard-summary`, server-side aggregation reused by Dashboard Geral.
- `backend/src/api/schemas/parsing.py` — `SAPObjectRead` gained `application_id` (existing ORM
  column, not previously exposed).
- `components/dashboard/DashboardGeral.tsx` and `components/dashboard/ExecutiveView.tsx` — new,
  replace the two `PlaceholderView` stubs.
- `components/shared/cleanCoreDisplay.tsx` — `RecommendationChip`/`LevelBadge`/
  `countByRecommendation` extracted from `ApplicationBrowser.tsx` so `ObjectBrowser.tsx` doesn't
  import from it (would have been a circular import once Technical View needed the same chips for
  its remediation panel).
- `components/parsing/ObjectBrowser.tsx` — `RemediationPanel` (Technical View's "remediation
  proposal", sourced from the owning Application's existing Clean Core recommendation/rationale
  rather than a new AI field) + `focusObjectId`/`onNavigate` props.
- `components/architecture/ApplicationBrowser.tsx` — business-rule/finding lists in
  `ApplicationDetail` became clickable drill-down buttons; `focusApplicationId`/`onNavigate` props.
- `components/functional/BusinessRuleBrowser.tsx` — `RuleObjectContext` became a clickable
  drill-down button; `focusRuleId`/`onNavigate` props.
- `backend/tests/test_dashboard.py` — 2 tests for the new aggregation endpoint.

## Known limitations
- Architecture View's "coupling patterns" (cross-application dependency graph) was not
  implemented — `SAPObjectDependency.target_name` is free text, never resolved to a target
  `SAPObject.id`, so there is no existing signal for whether a dependency edge crosses an
  Application boundary. Deferred as BL-022.
- The Baseline's "customisation identification" AI step (distinct from `application_discovery`)
  has no dedicated capability; Dashboard Geral's "Customizações identificadas" KPI maps to the
  discovered-`Application` count instead. Deferred as BL-021.
- Functional View's "validation/correction of AI interpretation" is satisfied by the
  `BusinessRule.user_validated`/`user_notes` hook already shipped in SPRINT-10 — this sprint added
  drill-down on top of it, not a new validation mechanism. No equivalent validation exists yet for
  `Application`/`CleanCoreAssessment` (pre-existing gap, BL-019).
- No dedicated code/source viewer (Monaco) exists yet in the app, so drill-down continuity stops at
  the object's evidence chips rather than opening raw source — pre-existing gap, not introduced or
  closed by this sprint.

## Deferred items
- BL-021 — Baseline's "customisation identification" AI step has no dedicated capability.
- BL-022 — No application-to-application coupling/dependency graph for Architecture View.

## Repository closure
- Sprint branch: `sprint/15-navigation-perspectives`
- Official commit message: `feat(sprint-15): complete result navigation perspectives`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
