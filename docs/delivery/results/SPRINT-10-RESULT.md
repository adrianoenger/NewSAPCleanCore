# SPRINT-10 Result — Business Rule Discovery

**Status:** Completed
**Completed at:** 2026-09-26
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Introduced the second real AI capability in the product: `business_rule_discovery` registers as a
5th stage of the existing `source_processing` durable pipeline (`PipelineRun`/`StageRun`/
`WorkItem`), running after `object_understanding`. For each `SAPObject` whose persisted
`ObjectUnderstanding` reached `COMPLETED`, it reuses that object's own evidence package (source
excerpt, correlated ATC findings, correlated supplemental evidence — unchanged from
`object_understanding`) plus the persisted understanding as prompt *context only* (ADR-008: AI
interpretation is never itself a citable evidence ref), calls the configured `AIProvider` through
a versioned prompt/schema requiring a condition/action/type/confidence/evidence structure per
candidate rule, validates the response (every rule's evidence_refs must resolve against real
evidence; a `COMPLETED` result with zero rules is a valid, non-forced outcome — ADR-012), and
persists candidate `BusinessRule` rows. A finalize step performs basic consolidation: candidates
across the assessment sharing the same `rule_type` and normalized condition+action text are
merged into one survivor (preferring an already user-validated row so validated content is never
relabeled), the duplicate's evidence is folded into the survivor rather than lost, and the
duplicate is marked `MERGED`/`consolidated_into_id` rather than deleted. A new Functional View
(`BusinessRuleBrowser`) lists discovered rules, drills down to the exact supporting `SAPObject`
(and, via the existing evidence-correlations endpoint, supplemental evidence), and exposes a
user-validation hook — a validated rule is never touched by later reprocessing or consolidation.

AWS Bedrock is live-validated against a real model (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`)
producing genuinely grounded, cited business rules from real ABAP source.

## Demonstration path
1. Open an Assessment with a completed Step 3 run (Scan → Parsing → Dependências → Entendimento
   por IA already `COMPLETED`) → run/resume Step 3 again → the durable pipeline now shows 5 stages,
   ending in "Descoberta de Regras de Negócio" → Concluído.
2. Open **Functional View** → the rule list shows every discovered candidate rule with its type
   badge (Validação / Cálculo / Autorização / Workflow / Integridade de Dados / Outro).
3. Select a rule → the detail panel shows Condição, Ação, rationale, confidence %, evidence-ref
   badges, the exact supporting source object ("Objeto de origem": name/type/line range) and, when
   applicable, correlated supplemental evidence, plus a provenance line
   (`bedrock / us.anthropic.claude-sonnet-4-5-20250929-v1:0 · prompt business_rule_discovery@v1`).
4. Click "Marcar como validado" (optionally with notes) → the rule is flagged
   `user_validated`/`user_validated_at` and is never overwritten by a later reprocessing or
   consolidation run.

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint (backend `/health` reports
  `migration_revision: 0012_business_rule_discovery`; `alembic current`/`heads` both at
  `0012_business_rule_discovery`, sole head, applied from a linear chain from `0011`).
- [x] Critical contracts introduced by the sprint: `BusinessRuleDiscoveryResult` +
  `validate_result()` domain rules (`ai/business_rule_discovery/schema.py`); evidence package
  wrapper (`ai/business_rule_discovery/evidence_package.py`); prompt/schema registered as
  `business_rule_discovery` v1 (`ai/registry.py`); `BusinessRule` persistence + the
  `business_rule_discovery` pipeline stage incl. its consolidation finalize; `GET
  /assessments/{id}/business-rules` and `PATCH .../business-rules/{id}/validate` — each covered
  by dedicated tests.
- [x] Primary demonstrable user flow: reproduced live twice — (a) via the real HTTP API with real
  AWS Bedrock credentials, running the full pipeline over `demo-source/ABAP` end to end (3 real
  grounded, evidence-cited business rules persisted for `ZFM_PROCESS_ORDER`/`ZPROGRAM_REPORT`,
  confidence 0.95); (b) via Playwright against the real electron-vite renderer
  (`localhost:5173`), reproducing the exact demonstration path above against a disposable
  client/assessment, including exercising the "Marcar como validado" hook end to end. Both
  disposable clients deleted afterward (scoped `DELETE FROM client WHERE id=:cid`).
- [x] Required integration checks: full backend suite `pytest` **154/154** passed (16 new tests:
  `test_business_rule_discovery.py` for the registry/domain-validator unit tests,
  `test_business_rule_discovery_pipeline.py` for the full pipeline-stage integration incl.
  `COMPLETED`-with-rules/`COMPLETED`-with-zero-rules, provider-error and domain-validation
  failures never persisting without failing the stage, reprocessing replacing non-validated
  candidates, cross-object consolidation, the user-validated-row-wins-consolidation case, and
  both API endpoints); 2 pre-existing hardcoded assertions fixed (`migration_revision`, stage
  count 4→5) in `test_foundation.py`/`test_sprint06.py`. Frontend `tsc --noEmit` and `npm run
  build` both clean.
- [x] Migration applicability: `0011_object_understanding` → `0012_business_rule_discovery`
  applied; `alembic current`/`heads` both at `0012_business_rule_discovery`.

## Key implementation notes
- **`backend/src/ai/business_rule_discovery/`** (new): `schema.py`
  (`BusinessRuleDiscoveryResult`, `BusinessRuleCandidate`, `BusinessRuleType`,
  `validate_result`), `evidence_package.py` (`BusinessRuleEvidencePackage` wrapping
  `ai.object_understanding`'s own evidence package plus the persisted understanding as prompt
  context), `__init__.py` (registers capability `business_rule_discovery` v1).
- **`backend/src/persistence/models.py`**: `BusinessRule` (+ `BusinessRuleStatus`) — one or more
  rows per `SAPObject`, `consolidated_into_id` self-FK for merge handling,
  `user_validated`/`user_validated_at`/`user_notes` validation-hook fields — migration
  `0012_business_rule_discovery`.
- **`backend/src/pipeline/stages.py`**: `business_rule_discovery` stage
  (`_business_rule_discovery_prepare`/`_process_item`/`_finalize`), appended to
  `SOURCE_PROCESSING_STAGES` with `depends_on=("object_understanding",)`. A provider/domain
  failure is recorded on `WorkItem.last_error` (not a dedicated persisted row, unlike
  `ObjectUnderstanding` — there is no single canonical row to mark for a list-shaped result) while
  leaving that object's already-persisted non-validated candidates untouched.
- **`backend/src/api/`**: `schemas/business_rules.py`, `routes/business_rules.py` — `GET
  /assessments/{id}/business-rules` (excludes `MERGED` by default, `object_id`/`include_merged`
  filters), `PATCH .../business-rules/{id}/validate`.
- **Frontend**: `components/functional/BusinessRuleBrowser.tsx`, wired into `Workspace.tsx` for
  `activeView === 'functional'`; exported `EvidencePanel`/`SOURCE_TYPE_LABELS` from
  `ObjectBrowser.tsx` for reuse rather than duplicating; `lib/api.ts` additions
  (`BusinessRuleRecord`, `fetchBusinessRules`, `validateBusinessRule`); `PipelineRunner.tsx` stage
  label.
- **Design fix found via testing:** `ref_id` (e.g. `"SRC-1"`) is only unique within one object's
  own evidence package, not across objects — the cross-object consolidation test caught this;
  fixed by keying evidence-ref dedup on `(ref_id, source_type, entity_id)` rather than `ref_id`
  alone (`pipeline/stages.py::_evidence_ref_key`).

## Known limitations
- Consolidation is intentionally "basic" (exact `rule_type` + normalized condition/action text
  match) per the sprint's own scope — no embeddings/semantic similarity; that remains explicit
  future work under the baseline's separate "embeddings / semantic indexing" AI Processing item.
- A business rule's `ATC_FINDING`-type evidence ref gets the same badge-only treatment
  `ObjectUnderstanding` already uses (ref_id + source-type tooltip, no dedicated ATC finding
  detail endpoint) — consistent with the existing UI convention, not a regression introduced here.
- Azure AI Foundry live validation remains deferred (unchanged from SPRINT-09 — no credentials
  available).

## Deferred items
- **BL-015** (new): a stray un-cleaned-up "SPRINT09 Live Smoke Test" client was noticed in the
  assessments list from a prior session — not this sprint's data, not a data-loss risk, just
  dev-database clutter. Recorded, not fixed (out of this sprint's scope).
- BL-013 (pre-existing schema/ORM autogenerate drift) and BL-014 (pre-existing sprint tests now
  making live Bedrock calls) are unrelated to this sprint and untouched.

## Repository closure
- Sprint branch: `sprint/10-business-rule-discovery`
- Official commit message: `feat(sprint-10): complete business rule discovery`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
