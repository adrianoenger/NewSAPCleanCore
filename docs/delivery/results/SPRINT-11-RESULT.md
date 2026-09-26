# SPRINT-11 Result — Application Discovery

**Status:** Completed
**Completed at:** 2026-09-26
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Introduced the third real AI capability in the product: `application_discovery` registers as a
6th stage of the existing `source_processing` durable pipeline (`PipelineRun`/`StageRun`/
`WorkItem`), running after `business_rule_discovery`. A deterministic clustering step
(`ai/application_discovery/clustering.py`, no AI call) first groups a scan's `SAPObject`s into
candidate clusters using dependency edges (`SAPObjectDependency.target_name/target_type`
resolved against `SAPObject.canonical_key` within the assessment — there is no FK to the target,
so resolution happens at clustering time), shared package correlations (`ATCFinding.
package_name_raw` / `EvidenceRecord.package_name`), and shared `ObjectUnderstanding.concepts`
tags (ignoring a concept shared by more than half of the scan's understood objects as too
generic to be distinguishing). An object with no signal connecting it to any other still yields
its own single-member candidate — grouping is never forced without evidence. Each candidate
cluster is persisted as an `Application` row (membership via `SAPObject.application_id`, not a
join table); the configured `AIProvider` is then called through a versioned prompt/schema to
name/describe the cluster and assign a domain/confidence/rationale, citing only ground-truth
evidence (member object identity, dependency edges, correlated ATC/supplemental evidence) —
per-object `ObjectUnderstanding`/`BusinessRule` content is prompt *context only*, never a
citable evidence ref (ADR-008, mirroring `business_rule_discovery`'s own treatment of
`ObjectUnderstanding`). A schema-valid `INSUFFICIENT_CONTEXT` result is a legitimate outcome —
the `Application` stays `CANDIDATE` with no fabricated name (ADR-012), rather than being forced
into a name it has no evidence for. Reprocessing never touches a cluster that overlaps a
`USER_RENAMED` or `MERGED` application's members, so manual curation always survives. A new
Architecture View (`ApplicationBrowser`) lists discovered applications and lets the user browse
each one's objects, discovered business rules, correlated ATC findings and the AI's confidence
rationale, plus simple manual rename/move-object/merge actions (merge mirrors `BusinessRule`'s
own consolidation pattern: the source is marked `MERGED` with `consolidated_into_id` rather than
deleted, and its evidence is folded into the survivor).

AWS Bedrock is live-validated against a real model (`us.anthropic.claude-sonnet-4-5-20250929-v1:0`),
including a run where it correctly reported `INSUFFICIENT_CONTEXT` for genuinely unrelated demo
objects rather than fabricating a grouping.

## Demonstration path
1. Open an Assessment, ingest a source directory, run Step 3 processing — the durable pipeline
   now shows 6 stages, ending in "application_discovery" → Concluído.
2. Open **Architecture View** → the application list shows every discovered candidate
   (name/status badge/domain/member count); an AI-named cluster shows e.g. "Custom Order
   Processing" (domain "Order Management"), while a cluster with no grouping evidence shows as
   an unnamed "Candidata" rather than a fabricated name.
3. Select an application → the detail panel shows its rationale, the deterministic clustering
   signals that formed it, evidence-ref badges, member objects (each with a "mover para…"
   dropdown), its discovered business rules, correlated ATC findings, and the
   provider/model/prompt provenance line.
4. Click "Renomear" to manually rename/describe it (→ `USER_RENAMED`, survives later
   reprocessing); use a member's dropdown to move it to another application or ungroup it; use
   the "Mesclar com…" selector to merge one application into another (source → `MERGED` +
   `consolidated_into_id`).

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint (backend `/health` reports
  `migration_revision: 0013_application_discovery`; `alembic current` at
  `0013_application_discovery (head)`, applied from a linear chain from `0012`).
- [x] Critical contracts introduced by the sprint: deterministic clustering
  (`ai/application_discovery/clustering.py`); `ApplicationDiscoveryResult` +
  `validate_result()` domain rules (`ai/application_discovery/schema.py`); evidence package
  builder (`ai/application_discovery/evidence_package.py`); prompt/schema registered as
  `application_discovery` v1 (`ai/registry.py`); `Application` persistence + the
  `application_discovery` pipeline stage incl. its reprocessing-reconciliation logic; `GET/PATCH
  /assessments/{id}/applications[/{id}]`, `POST .../move-object`, `POST .../merge` — each covered
  by dedicated tests.
- [x] Primary demonstrable user flow: reproduced live twice — (a) via the real HTTP API with real
  AWS Bedrock credentials, running the full 6-stage pipeline over `demo-source/ABAP` end to end
  (4 real objects correctly returned as 4 honest `INSUFFICIENT_CONTEXT` singletons on a bare run,
  since the demo files have no dependency/package signal between them), then exercising rename,
  move-object and merge against the real persisted rows and confirming a second full
  reprocessing left the renamed application's name/status/membership untouched; (b) via
  Playwright against the real electron-vite renderer (`localhost:5173`), reproducing the
  demonstration path above against a disposable client/assessment — 3 discovered applications
  including one genuinely AI-named "Custom Order Processing" with real evidence badges and a
  real discovered business rule, and a live rename immediately re-rendering as "Renomeada pelo
  usuário". Both disposable clients deleted afterward (scoped `DELETE FROM client WHERE
  id=:cid`).
- [x] Required integration checks: full backend suite `pytest` **173/173** passed (37 new tests
  across `test_application_discovery_clustering.py` (11, deterministic signals),
  `test_application_discovery.py` (6, domain-validator unit tests),
  `test_application_discovery_pipeline.py` (16, pipeline integration incl.
  `INSUFFICIENT_CONTEXT`-is-valid, provider-error-never-fails-the-stage, and
  reprocessing-preserves-`USER_RENAMED`, plus 4 API tests), and 2 pre-existing hardcoded
  assertions fixed (`migration_revision`, stage count 5→6) in
  `test_foundation.py`/`test_sprint06.py`; `test_business_rule_discovery_pipeline.py`'s own
  pre-existing tests still pass given the new stage's safe default fake-provider output).
  Frontend `tsc --noEmit` and `npm run build` both clean.
- [x] Migration applicability: `0012_business_rule_discovery` → `0013_application_discovery`
  applied; `alembic current` at `0013_application_discovery (head)`.

## Key implementation notes
- **`backend/src/ai/application_discovery/`** (new): `clustering.py` (`CandidateCluster`,
  `ClusterSignal`, `build_candidate_clusters` — dependency/shared_package/shared_concept
  signals, pure/deterministic), `schema.py` (`ApplicationDiscoveryResult`, `validate_result`),
  `evidence_package.py` (`ApplicationEvidencePackage` aggregating member identity/dependency/ATC/
  supplemental-evidence as citable refs, member understanding/rules as context only),
  `__init__.py` (registers capability `application_discovery` v1).
- **`backend/src/persistence/models.py`**: `Application` (+ `ApplicationStatus`:
  `CANDIDATE`/`AI_NAMED`/`USER_RENAMED`/`MERGED`), `consolidated_into_id` self-FK for merge
  handling, `clustering_signals` JSONB provenance; `SAPObject.application_id` nullable FK —
  migration `0013_application_discovery`.
- **`backend/src/pipeline/stages.py`**: `application_discovery` stage
  (`_application_discovery_prepare`/`_process_item`), appended to `SOURCE_PROCESSING_STAGES` with
  `depends_on=("business_rule_discovery",)`. `prepare` resets non-preserved membership, runs
  clustering, reuses a non-preserved existing `Application` by majority-member-overlap or creates
  a new `CANDIDATE` one, and never touches a cluster overlapping a `USER_RENAMED`/`MERGED`
  application's members. `process_item` only sets `AI_NAMED` on a genuinely `COMPLETED` result;
  a provider/domain-validation failure is recorded on `Application.error` without changing its
  status, mirroring `object_understanding`'s "never a false success" discipline more closely than
  `business_rule_discovery`'s WorkItem-only error recording (there is a natural single row here).
- **`backend/src/api/`**: `schemas/applications.py`, `routes/applications.py` — `GET
  /assessments/{id}/applications` (excludes `MERGED`/zero-member by default,
  `include_merged` bypasses both), `GET .../applications/{id}` (detail incl. derived business
  rules/ATC findings), `PATCH .../applications/{id}`, `POST .../applications/move-object`, `POST
  .../applications/merge`.
- **Frontend**: `components/architecture/ApplicationBrowser.tsx`, wired into `Workspace.tsx` for
  `activeView === 'architecture'`; `lib/api.ts` additions (`ApplicationRecord`,
  `fetchApplications`/`fetchApplication`/`renameApplication`/`moveApplicationObject`/
  `mergeApplications`); `ObjectBrowser.tsx`'s exported `SOURCE_TYPE_LABELS` extended with
  `SAP_OBJECT`/`DEPENDENCY` entries for reuse rather than duplication.
- **Design decision:** related business rules/evidence are derived via member `SAPObject`s
  (`SAPObject.application_id`) at query time rather than duplicated into a new join table — they
  are already evidence-bound at the object level (ADR-008), so grouping by application never
  needs its own persisted link.

## Known limitations
- Clustering does not use "transactions" or "process/usage correlations" as signals (Baseline:
  "packages/transactions/semantic signals plus reliable process/usage correlations when
  available") — `EvidenceRecord`/`EvidenceCorrelation` has no generic, provider-agnostic
  cross-object join key for either beyond `package_name` (already used), and inventing one would
  mean guessing a provider-specific payload shape, forbidden by ADR-017. Recorded as **BL-016**.
- Azure AI Foundry live validation remains deferred (unchanged from SPRINT-09/10 — no credentials
  available).

## Deferred items
- **BL-016** (new): application clustering does not yet use a process/usage-correlation signal —
  see Known limitations above.
- BL-013 (pre-existing schema/ORM autogenerate drift), BL-014 (pre-existing sprint tests now
  making live Bedrock calls) and BL-015 (pre-existing stray dev-database client) are unrelated to
  this sprint and untouched.

## Repository closure
- Sprint branch: `sprint/11-application-discovery`
- Official commit message: `feat(sprint-11): complete application discovery`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
