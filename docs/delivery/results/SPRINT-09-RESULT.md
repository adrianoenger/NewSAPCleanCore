# SPRINT-09 Result — AI Object Understanding

**Status:** Completed
**Completed at:** 2026-09-26
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Introduced provider-agnostic, structured LLM processing (ADR-006/ADR-012) — the first real AI
capability in the product. `object_understanding` registers as a 4th stage of the existing
`source_processing` durable pipeline (`PipelineRun`/`StageRun`/`WorkItem`, BL-003), running after
`detect_dependencies`: for each `SAPObject`, it assembles a provider-agnostic evidence package
(source excerpt, correlated ATC findings, correlated supplemental evidence), calls the configured
`AIProvider` through a versioned prompt/schema, validates the schema-conformant response against
domain rules (evidence references must resolve, `COMPLETED` requires grounded purpose text and at
least one citation, `INSUFFICIENT_CONTEXT` must not assert a purpose), and persists exactly one
`ObjectUnderstanding` row per object with full provider/model/prompt/schema provenance. A provider
error or a domain-validation failure is persisted as `ObjectUnderstandingStatus.FAILED` — never a
false `COMPLETED` — without failing the pipeline WorkItem, since a per-object AI outcome is not a
pipeline processing error. The result is exposed via the object detail API and rendered in the
`ObjectBrowser` detail panel.

AWS Bedrock (Converse API, forced tool-use) is live-validated against a real model
(`us.anthropic.claude-sonnet-4-5-20250929-v1:0`). Azure AI Foundry is implemented behind the same
`AIProvider` interface and unit-tested against a mocked HTTP layer; its live validation is
explicitly deferred — no Azure credentials were available this sprint.

## Demonstration path
1. Open an Assessment → Step 1 (Ingestão) → scan a directory with ABAP source (e.g.
   `/workspace/demo-source/ABAP`).
2. Step 3 ("3 - Processamento por IA") → "Iniciar Processamento" → the durable pipeline now shows
   4 stages (Scan de Arquivos → Parsing de Objetos → Detecção de Dependências → Entendimento por
   IA), each with live progress, ending in "Concluído".
3. Open Technical View → select any parsed object (e.g. `ZCL_CUSTOM_ORDER`) → the detail panel
   shows "Entendimento por IA": functional purpose, technical purpose, concept tags, confidence
   %, a rationale citing evidence, evidence-ref badges (labelled by source type: código-fonte /
   achado ATC / evidência complementar), and a provenance line (`bedrock /
   us.anthropic.claude-sonnet-4-5-20250929-v1:0 · prompt object_understanding@v1`).
4. An object with genuinely insufficient evidence shows an explicit "Evidência insuficiente…"
   state instead of a guessed purpose; a provider/validation failure shows an explicit failure
   message — neither is silently blank.

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint (backend `/health` reports
  `migration_revision: 0011_object_understanding`; `alembic current`/`heads` both at
  `0011_object_understanding`, sole head, applied from a linear chain).
- [x] Critical contracts introduced by the sprint: `AIProvider` Protocol +
  `StructuredCompletionRequest/Result` (`ai/provider.py`); Bedrock/Azure adapters
  (`ai/providers/*.py`); prompt/schema registry (`ai/registry.py`); `ObjectUnderstandingResult` +
  `validate_result()` domain rules (`ai/object_understanding/schema.py`); evidence package
  builder (`ai/object_understanding/evidence_package.py`); structural chunking
  (`ai/chunking.py`); `ObjectUnderstanding` persistence + the `object_understanding` pipeline
  stage — each covered by dedicated tests.
- [x] Primary demonstrable user flow: reproduced live twice — (a) via the real HTTP API with real
  AWS Bedrock credentials, running the full pipeline over `demo-source/ABAP` end to end (all 4
  demo objects reached `COMPLETED` with grounded, cited purposes, confidence 0.75-0.9); (b) via
  Playwright against the real electron-vite renderer (`localhost:5173`), reproducing the exact
  demonstration path above against a disposable client/assessment. Both cleaned up from the dev
  database afterward.
- [x] Required integration checks: full backend suite `pytest` **138/138** passed (13 new tests:
  `test_ai_providers.py` for providers/registry/chunking/domain validators,
  `test_object_understanding_pipeline.py` for the full pipeline-stage integration incl.
  `COMPLETED`/`INSUFFICIENT_CONTEXT`/`FAILED` persistence, domain-validation-failure handling,
  and upsert-on-reprocess); frontend `tsc --noEmit` and `npm run build` both clean.
- [x] Migration applicability: `0010_pipeline_run_kind` → `0011_object_understanding` applied;
  `alembic current`/`heads` both at `0011_object_understanding`.

## Key implementation notes
- **`backend/src/ai/`** (new): `provider.py` (Protocol + dataclasses), `providers/bedrock.py`
  (Converse API forced tool-use), `providers/azure_foundry.py` (JSON-Schema `response_format`
  over the OpenAI-compatible chat-completions shape), `providers/__init__.py::get_provider`
  (dispatch), `registry.py` (capability → version → prompt/schema), `chunking.py` (ABAP
  METHOD/FORM-boundary-aware splitting), `object_understanding/{schema,evidence_package,__init__}.py`.
- **`backend/src/persistence/models.py`**: `ObjectUnderstanding` (one row per `SAPObject`, unique
  index on `sap_object_id`) — migration `0011_object_understanding`.
- **`backend/src/pipeline/stages.py`**: `object_understanding` registered in
  `SOURCE_PROCESSING_STAGES`, `depends_on=("detect_dependencies",)`; per-item build evidence
  package → call provider → validate schema + domain rules → upsert `ObjectUnderstanding`.
- **`backend/src/api/schemas/parsing.py`** / **`routes/parsing.py`**: `ObjectUnderstandingRead`
  embedded as `SAPObjectDetailRead.understanding`.
- **`frontend/.../parsing/ObjectBrowser.tsx`**: `UnderstandingPanel` — purpose/concepts/
  confidence/rationale/evidence-refs/provenance, with distinct not-yet-processed /
  `INSUFFICIENT_CONTEXT` / `FAILED` states. **`frontend/.../pipeline/PipelineRunner.tsx`**:
  `object_understanding` stage label ("Entendimento por IA").
- **`backend/tests/`**: `test_ai_providers.py`, `test_object_understanding_pipeline.py` (new);
  fixed two pre-existing stale assertions this sprint's change legitimately invalidated —
  `test_foundation.py`'s hardcoded `migration_revision` and
  `test_sprint06.py::test_start_pipeline_run_endpoint`'s hardcoded 3-stage count/set.
- Credentials: read-only bind mount of the host's `~/.aws` into the backend container
  (`compose.yml`) plus `AWS_PROFILE`/`AWS_REGION`/`CCA_BEDROCK_MODEL_ID` via the gitignored root
  `.env` — no static secret in any tracked file.

## Known limitations
- Azure AI Foundry has no live validation this sprint — no credentials were available; it is
  implemented behind the same `AIProvider` interface and unit-tested against a mocked HTTP layer
  only.
- **BL-014** (new): every pre-existing SPRINT-06/07/08 test that runs the full pipeline without
  mocking `pipeline.stages.get_provider` now transitively makes a real Bedrock call, since this
  dev environment has real AWS credentials mounted. Confirmed harmless (all still pass) but it
  roughly tripled the full suite's runtime (~7s → ~132s) and couples unrelated scan/parse/
  dependency-detection tests to Bedrock reachability. Intended per BL-003, not a defect; left for
  future consideration.
- No UI provider switcher — the active provider (`bedrock` by default) is selected via backend
  settings, not per-request from the frontend; not required by this sprint's planned capabilities.
- ATC import remains a standalone action (ADR-016/BL-002); "customisation identification", "ATC
  interpretation", "business-rule discovery" and the remaining `AI Processing` bullets in the
  baseline are future sprints, not this one.

## Deferred items
- BL-013 (pre-existing schema/ORM autogenerate drift), BL-005, BL-007, BL-008, BL-009, BL-011,
  BL-012 (all `Open`, low/medium priority, none blocking, unrelated to this sprint).
- BL-014 (new this sprint, `Open`, low priority, non-blocking — see Known limitations).
- BL-002, BL-003 (BL-003 is the design this sprint implements — see above); both carried over,
  BL-003 effectively resolved by this sprint's integration though left open as a general engine
  principle rather than a one-off item.

## Repository closure
- Sprint branch: `sprint/09-ai-object-understanding`
- Official commit message: `feat(sprint-09): complete ai object understanding`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
