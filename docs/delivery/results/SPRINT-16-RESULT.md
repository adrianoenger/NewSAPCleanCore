# SPRINT-16 Result — AI Copilot

**Status:** Completed
**Completed at:** 2026-09-26
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
The permanent right-side Copilot (previously a disabled placeholder, ADR-010) is now a real chat.
It publishes the current UI view and selected entity (SAPObject/BusinessRule/Application) as
context, routes each question through the Baseline's five channels (structured summary, semantic
retrieval, source/supplemental-evidence retrieval via already-validated evidence packages, and
read-only reuse of already-retrieved SAP Knowledge guidance), returns an evidence-bound answer
with citable references and an optional single navigation target, and never mutates assessment
state. The conversation persists across view switches because the panel is never unmounted.

## Demonstration path
1. Open a processed assessment (e.g. Acme Industries) and select an SAP object in Technical View.
2. Ask the Copilot "O que este objeto faz?" — receive a grounded answer citing the object's
   selection detail and its AI-derived understanding, with a "Ver objeto SAP" navigation button.
3. Follow the navigation button, then switch to Functional View and select a business rule — the
   prior Q&A stays visible in the same Copilot panel; the context label updates to the new view.
4. Ask "Por que essa regra existe? Qual a evidência?" — receive a grounded answer citing the
   rule's own resolved evidence plus semantic-search hits, with a working "Ver regra de negócio"
   navigation button.
5. Selecting nothing and asking a general question (e.g. about counts) is answered from the
   structured dashboard-summary channel alone.

## Minimal validation executed
- [x] Backend: 224/224 pytest (215 pre-existing + 9 new in `backend/tests/test_copilot.py`).
- [x] Frontend: `tsc --noEmit` (both tsconfigs) and `electron-vite build` clean.
- [x] Primary demonstrable user flow: live Playwright session against the electron-vite renderer
      with real Bedrock calls over the persisted Acme Industries assessment (id 1074) — selection,
      grounded answer with citations, navigation follow-through, and conversation continuity across
      a view switch, all confirmed live.
- [x] Domain-validation contract: `ai.copilot.schema.validate_result` rejects any `evidence_refs`/
      `navigation_ref` not present in the context package — covered by unit tests and confirmed live
      (see Key implementation notes: a live bug was found and fixed here).
- [x] No schema change — `alembic` head unchanged at `0016_embeddings`; `alembic check` shows only
      the pre-existing BL-013 drift, no new drift; no migration to apply.

## Key implementation notes
- `backend/src/ai/copilot/schema.py` + `__init__.py` — `CopilotAnswerResult` (status/answer/
  evidence_refs/navigation_ref) registered as `copilot/v1` in `ai.registry` (ADR-012);
  `validate_result` enforces evidence-binding and that any navigation target is a ref_id actually
  present in context.
- `backend/src/ai/copilot/context.py` — assembles a bounded, citable `CopilotContext` per question:
  a structured summary (`pipeline/dashboard_summary.py`, extracted from `api/routes/dashboard.py`
  so both share one definition), the current selection's own already-persisted evidence-bound
  detail (`ObjectUnderstanding`/`BusinessRule`/`CleanCoreAssessment`, reusing their existing
  `evidence_refs`), `semantic_search` hits for the question text, and already-retrieved
  `SapKnowledgeReference` rows via `ai.knowledge_service.list_guidance` (read-only — chat never
  triggers a new MCP query, per ADR-007).
- `backend/src/api/routes/copilot.py` + `api/schemas/copilot.py` — `POST
  /assessments/{id}/copilot/ask`; a provider/domain-validation failure returns `status: "FAILED"`
  with a message, never a 500 (ADR-012).
- `backend/src/pipeline/dashboard_summary.py` — `compute_dashboard_summary` extracted out of
  `api/routes/dashboard.py` (now a thin wrapper) so the Copilot's structured-query channel and the
  existing dashboard endpoint share one definition.
- Frontend: a plain in-view "selection" concept (reusing `resultNav.ts::ResultFocus`) lifted from
  `ObjectBrowser`/`BusinessRuleBrowser`/`ApplicationBrowser` up to `App.tsx` via a new
  `onSelectEntity` prop threaded through `Workspace.tsx`, distinct from cross-view drill-down
  `focus`. `components/shell/CopilotPanel.tsx` rewritten as a real chat (message list, reference
  chips, a navigation button reusing `onNavigate`/`ResultFocus`) — message state lives in the
  component itself, which is never unmounted while an assessment is open.
- Live bug found and fixed during validation: the first live Bedrock call returned
  `status: FAILED` because the model copied the prompt's `[navigable: kind#id]` annotation text
  into `navigation_ref` instead of the item's real `ref_id`. Fixed by rewording the annotation and
  tightening the `copilot/v1` system prompt to state `evidence_refs`/`navigation_ref` may only ever
  be a `ref_id` copied verbatim; reverified live immediately after.

## Known limitations
- Reference chips for `TECHNICAL_FINDING`/`SUPPLEMENTAL_EVIDENCE`/`SAP_KNOWLEDGE` citations are
  informational only (ref_id + source_type tooltip) — they are not click-through, because
  `resultNav.ts::ResultFocus` only supports `sap_object`/`business_rule`/`application` as navigable
  kinds today. Only the AI-chosen `navigation_ref` is clickable, and only when it resolves to one
  of those three kinds. Deferred as BL-023.
- No Monaco/source-code viewer exists yet in the frontend, so the sprint's "select code" outcome is
  satisfied by selecting a SAPObject in Technical View (the closest existing selection primitive),
  not a literal code-range highlight — pre-existing gap, not introduced by this sprint.
- The Copilot's conversation is not persisted to the database; it lives in `CopilotPanel`'s
  component state, which already survives view switches because the panel is permanently mounted.
  It does not survive an app restart — not required by ADR-010, and avoids a migration for a PoC
  chat history.

## Deferred items
- BL-023 — Copilot reference chips for finding/dataset/guidance citations are not click-through.

## Repository closure
- Sprint branch: `sprint/16-ai-copilot`
- Official commit message: `feat(sprint-16): complete ai copilot`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
