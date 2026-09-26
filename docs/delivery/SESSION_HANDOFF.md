# Session Handoff

## Current state
SPRINT-09 (AI Object Understanding) is **completed** — closed by `/clean-core-finish-sprint`.
`docs/delivery/SPRINT-09-PROGRESS.yaml` is `status: completed`, `progress_percent: 100`,
`ready_for_review: false`; the result record is `docs/delivery/results/SPRINT-09-RESULT.md`. The
sprint branch was pushed and merged into `main` by fast-forward; the local sprint branch was
deleted (the remote copy is kept as the sprint record).

**Next sprint:** SPRINT-10 — Business Rule Discovery
(`docs/delivery/sprints/SPRINT-10-business-rule-discovery.md`), not started.

## What was delivered
Provider-agnostic structured LLM processing (ADR-006/ADR-012) entered the product for the first
time. `object_understanding` registers as a 4th stage of the existing `source_processing` durable
pipeline (BL-003), running after `detect_dependencies`: for each `SAPObject` it assembles a
provider-agnostic evidence package (source excerpt + correlated ATC findings + correlated
supplemental evidence), calls the configured `AIProvider` through a versioned prompt/schema,
validates the response against domain rules before persistence, and upserts one
`ObjectUnderstanding` row per object with full provider/model/prompt/schema provenance. A provider
error or a domain-validation failure persists as `ObjectUnderstandingStatus.FAILED` — never a
false `COMPLETED` — without failing the pipeline WorkItem.

- **`backend/src/ai/`**: `provider.py` (`AIProvider` Protocol), `providers/{bedrock,azure_foundry}.py`,
  `providers/__init__.py::get_provider`, `registry.py` (versioned prompt/schema), `chunking.py`
  (ABAP boundary-aware chunking), `object_understanding/{schema,evidence_package,__init__}.py`.
- **`persistence/models.py::ObjectUnderstanding`** + migration `0011_object_understanding`.
- **`pipeline/stages.py`**: `object_understanding` stage registered in `SOURCE_PROCESSING_STAGES`.
- **API**: `SAPObjectDetailRead.understanding` (`api/schemas/parsing.py`).
- **Frontend**: `ObjectBrowser.tsx::UnderstandingPanel`, `PipelineRunner.tsx` stage label.
- Bedrock is live-validated (real `us.anthropic.claude-sonnet-4-5-20250929-v1:0` calls, both via
  the HTTP API over `demo-source/ABAP` and via a live Playwright e2e against the electron-vite
  renderer). Azure AI Foundry is implemented and unit-tested against a mocked HTTP layer; its live
  validation remains deferred — no credentials were available this sprint.
- 138/138 backend pytest (13 new tests), frontend `tsc`/`build` clean.

Full detail, demonstration path, and known limitations are in
`docs/delivery/results/SPRINT-09-RESULT.md`.

## Known deferrals / backlog
- **BL-014** (new): pre-existing SPRINT-06/07/08 tests that run the full pipeline without mocking
  the AI provider now transitively make real Bedrock calls (intended per BL-003, not a defect;
  tripled full-suite runtime ~7s → ~132s). Not fixed this sprint — recorded for future
  consideration.
- Azure AI Foundry live validation remains deferred — no credentials available this sprint.
- BL-013 (pre-existing schema/ORM autogenerate drift) is unrelated to this sprint and untouched.
- ATC import remains a standalone action (ADR-016/BL-002) — untouched by this sprint.
- The rest of the baseline's "AI Processing" list (customisation identification, ATC
  interpretation, dependency/application discovery, business-rule discovery, Clean Core analysis,
  embeddings, aggregation) is out of this sprint's scope — SPRINT-10+ builds on the
  `AIProvider`/registry/pipeline-stage foundation this sprint established.

## Next steps
SPRINT-09 is closed. Run `/clean-core-run-sprint` to start SPRINT-10 (Business Rule Discovery) —
it will sync `main`, create branch `sprint/10-business-rule-discovery`, and begin from that
sprint's first capability.

## Restart instructions
SPRINT-09 has no unfinished work — `docs/delivery/SPRINT-09-PROGRESS.yaml` is `status: completed`
and all 12 capabilities are `done`. If resuming this session unexpectedly with no sprint branch
checked out, `main` is the correct branch to be on; the next action is `/clean-core-run-sprint`
for SPRINT-10, not a resume of SPRINT-09.
