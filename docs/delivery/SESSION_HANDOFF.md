# Session Handoff

## Current state
SPRINT-11 (Application Discovery) is **completed** — closed by `/clean-core-finish-sprint`.
`docs/delivery/SPRINT-11-PROGRESS.yaml` is `status: completed`, `progress_percent: 100`,
`ready_for_review: false`; the result record is `docs/delivery/results/SPRINT-11-RESULT.md`. The
sprint branch was pushed and merged into `main` by fast-forward; the local sprint branch was
deleted (the remote copy is kept as the sprint record).

**Next sprint:** SPRINT-12 — SAP Knowledge MCP
(`docs/delivery/sprints/SPRINT-12-sap-knowledge-mcp.md`), not started.

## What was delivered
`application_discovery` registers as a 6th stage of the existing `source_processing` durable
pipeline, running after `business_rule_discovery`: a deterministic clustering step (no AI call)
groups a scan's `SAPObject`s into candidate clusters using dependency edges (resolved against
`canonical_key`), shared package correlations (via correlated ATC/supplemental evidence) and
shared `ObjectUnderstanding` concept tags (ignoring overly generic ones); each candidate is
persisted as an `Application` row (membership via `SAPObject.application_id`), then named/
described by the configured `AIProvider` through a versioned evidence-bound prompt/schema —
citing only ground-truth evidence, never a prior AI stage's own output, and never fabricating a
name when the result is genuinely `INSUFFICIENT_CONTEXT`. Reprocessing never touches a cluster
overlapping a `USER_RENAMED`/`MERGED` application's members, so manual curation always
survives. A new Architecture View (`ApplicationBrowser`) lets the user browse each discovered
application's objects, business rules, ATC findings and confidence rationale, and exposes
manual rename/move-object/merge actions (merge mirrors `BusinessRule`'s own consolidation
pattern).

- **`backend/src/ai/application_discovery/`**: `clustering.py`, `schema.py`,
  `evidence_package.py`, `__init__.py` (registers capability `application_discovery` v1).
- **`persistence/models.py::Application`** (+ `ApplicationStatus`) +
  `SAPObject.application_id` — migration `0013_application_discovery`.
- **`pipeline/stages.py`**: `application_discovery` stage (prepare/process_item), appended to
  `SOURCE_PROCESSING_STAGES`.
- **API**: `api/schemas/applications.py`, `api/routes/applications.py` — `GET`/`PATCH
  /assessments/{id}/applications[/{id}]`, `POST .../move-object`, `POST .../merge`.
- **Frontend**: `components/architecture/ApplicationBrowser.tsx`, wired into `Workspace.tsx`;
  extended `ObjectBrowser.tsx`'s exported `SOURCE_TYPE_LABELS`; `lib/api.ts` additions.
- Bedrock is live-validated (real `us.anthropic.claude-sonnet-4-5-20250929-v1:0` calls), both via
  the HTTP API over `demo-source/ABAP` (incl. rename/move-object/merge and a reprocessing run
  that confirmed user curation survives) and via a live Playwright e2e against the electron-vite
  renderer.
- 173/173 backend pytest (37 new tests), frontend `tsc`/`build` clean.

Full detail, demonstration path, and known limitations are in
`docs/delivery/results/SPRINT-11-RESULT.md`.

## Known deferrals / backlog
- **BL-016** (new): application clustering does not use a process/usage-correlation signal —
  `EvidenceRecord`/`EvidenceCorrelation` has no generic cross-object join key for it beyond
  `package_name` (already used), and inventing one would mean guessing a provider-specific
  payload shape (forbidden by ADR-017). Revisit once a real adapter exposes one.
- BL-013 (pre-existing schema/ORM autogenerate drift), BL-014 (pre-existing sprint tests now
  making live Bedrock calls) and BL-015 (pre-existing stray dev-database client) are unrelated to
  this sprint and untouched.
- Azure AI Foundry live validation remains deferred (unchanged from SPRINT-09/10 — no credentials
  available).

## Next steps
SPRINT-11 is closed. Run `/clean-core-run-sprint` to start SPRINT-12 (SAP Knowledge MCP) — it
will sync `main`, create branch `sprint/12-sap-knowledge-mcp`, and begin from that sprint's first
capability. SPRINT-12 introduces a `SAPKnowledgeProvider` abstraction connecting configurable
`mcp-sap-docs`/`mcp-abap` endpoints, persists retrieved SAP documentation evidence with
provider/reference provenance, and renders "SAP Guidance" in finding/application detail — it can
enrich the `Application`/`BusinessRule`/`ATCFinding` detail views this sprint just built or
extended.

## Restart instructions
SPRINT-11 has no unfinished work — `docs/delivery/SPRINT-11-PROGRESS.yaml` is `status: completed`
and all 7 capabilities are `done`. If resuming this session unexpectedly with no sprint branch
checked out, `main` is the correct branch to be on; the next action is `/clean-core-run-sprint`
for SPRINT-12, not a resume of SPRINT-11.
