# Session Handoff

## Current state
SPRINT-10 (Business Rule Discovery) is **completed** — closed by `/clean-core-finish-sprint`.
`docs/delivery/SPRINT-10-PROGRESS.yaml` is `status: completed`, `progress_percent: 100`,
`ready_for_review: false`; the result record is `docs/delivery/results/SPRINT-10-RESULT.md`. The
sprint branch was pushed and merged into `main` by fast-forward; the local sprint branch was
deleted (the remote copy is kept as the sprint record).

**Next sprint:** SPRINT-11 — Application Discovery
(`docs/delivery/sprints/SPRINT-11-application-discovery.md`), not started.

## What was delivered
`business_rule_discovery` registers as a 5th stage of the existing `source_processing` durable
pipeline, running after `object_understanding`: for each `SAPObject` with a `COMPLETED`
understanding, it reuses that object's evidence package (source excerpt, correlated ATC findings,
correlated supplemental evidence) plus the persisted understanding as prompt context only (never
a citable evidence ref, per ADR-008), calls the configured `AIProvider` through a versioned
condition/action/type/confidence/evidence-bound prompt/schema, validates the response before
persistence (a `COMPLETED` result with zero rules is a valid, non-forced outcome), and persists
candidate `BusinessRule` rows. A finalize step performs basic consolidation of exact-duplicate
candidates across the assessment, preferring a user-validated survivor. A new Functional View
(`BusinessRuleBrowser`) lists discovered rules with evidence drill-down to the exact supporting
object/source or supplemental evidence, and exposes a user-validation hook that survives later
reprocessing/consolidation.

- **`backend/src/ai/business_rule_discovery/`**: `schema.py`, `evidence_package.py`,
  `__init__.py` (registers capability `business_rule_discovery` v1).
- **`persistence/models.py::BusinessRule`** (+ `BusinessRuleStatus`) — migration
  `0012_business_rule_discovery`.
- **`pipeline/stages.py`**: `business_rule_discovery` stage (prepare/process_item/finalize),
  appended to `SOURCE_PROCESSING_STAGES`.
- **API**: `api/schemas/business_rules.py`, `api/routes/business_rules.py` — `GET
  /assessments/{id}/business-rules`, `PATCH .../business-rules/{id}/validate`.
- **Frontend**: `components/functional/BusinessRuleBrowser.tsx`, wired into `Workspace.tsx`;
  exported `EvidencePanel`/`SOURCE_TYPE_LABELS` from `ObjectBrowser.tsx` for reuse; `lib/api.ts`
  additions.
- Bedrock is live-validated (real `us.anthropic.claude-sonnet-4-5-20250929-v1:0` calls, both via
  the HTTP API over `demo-source/ABAP` and via a live Playwright e2e against the electron-vite
  renderer, including the "Marcar como validado" hook end to end).
- 154/154 backend pytest (16 new tests), frontend `tsc`/`build` clean.

Full detail, demonstration path, and known limitations are in
`docs/delivery/results/SPRINT-10-RESULT.md`.

## Known deferrals / backlog
- **BL-015** (new): a stray un-cleaned-up "SPRINT09 Live Smoke Test" client noticed in the
  assessments list from a prior session — not this sprint's data, not a data-loss risk, just
  dev-database clutter. Not fixed (out of this sprint's scope).
- Consolidation is intentionally "basic" (exact rule_type + normalized text match), no
  embeddings/semantic similarity — that remains future work under the baseline's separate
  "embeddings / semantic indexing" AI Processing item.
- BL-013 (pre-existing schema/ORM autogenerate drift) and BL-014 (pre-existing sprint tests now
  making live Bedrock calls) are unrelated to this sprint and untouched.
- Azure AI Foundry live validation remains deferred (unchanged from SPRINT-09 — no credentials
  available).

## Next steps
SPRINT-10 is closed. Run `/clean-core-run-sprint` to start SPRINT-11 (Application Discovery) —
it will sync `main`, create branch `sprint/11-application-discovery`, and begin from that
sprint's first capability. SPRINT-11 groups technical objects into functional custom applications
and persists related business rules/evidence links — it builds directly on this sprint's
`BusinessRule` model and the `object_understanding`/`business_rule_discovery` stage pair.

## Restart instructions
SPRINT-10 has no unfinished work — `docs/delivery/SPRINT-10-PROGRESS.yaml` is `status: completed`
and all 7 capabilities are `done`. If resuming this session unexpectedly with no sprint branch
checked out, `main` is the correct branch to be on; the next action is `/clean-core-run-sprint`
for SPRINT-11, not a resume of SPRINT-10.
