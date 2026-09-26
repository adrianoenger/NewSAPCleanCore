# SPRINT-14 Result — Embeddings and Semantic Retrieval

**Status:** Completed
**Completed at:** 2026-09-26
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
`embeddings` registers as an 8th `source_processing` pipeline stage, after
`clean_core_analysis`. For every Assessment, `ai/embeddings/source_builder.py::collect_embeddable_entities`
builds embeddable text/metadata for meaningful semantic entities (Baseline core rule 14) —
deliberately scoped to exactly what the sprint's demonstrable outcome names, no more:

- `SAP_OBJECT` — only objects with a `COMPLETED` `ObjectUnderstanding`; the AI-understood
  functional/technical purpose plus concepts is embedded, never the raw ABAP source (an
  opaque/raw bulk payload).
- `APPLICATION` — name/description/domain of every non-`MERGED` Application.
- `BUSINESS_RULE` — condition/action of every `CANDIDATE` BusinessRule.
- `EVIDENCE_RECORD` — quality-gated process/usage/user/role supplemental signals only, the same
  `MATCHED_EXACT`/`MATCHED_HEURISTIC`-correlated, business-capability-tagged pool
  `ai.clean_core_analysis.evidence_package` already trusts as business evidence.

Each entity is embedded through a new `EmbeddingProvider` abstraction (`ai/embedding_provider.py`,
mirrors `AIProvider`/ADR-006 — a different API shape, text-to-vector rather than structured
completion, so a separate abstraction rather than overloading `AIProvider`) and upserted into one
`Embedding` row per `(assessment_id, entity_type, entity_id)` (migration `0016_embeddings`,
`pgvector.sqlalchemy.Vector(1024)` + an HNSW cosine-ops index declared in the ORM model's
`__table_args__` so `alembic check` sees zero new drift). `content_hash` gates re-embedding:
unchanged rebuilt text is never re-sent to the provider (pipeline-architecture.md's Incrementality
principle) — confirmed live that `SAP_OBJECT`/`APPLICATION` rows are reused in place across a
second reprocessing run, while `BUSINESS_RULE` is the one exception (that stage deletes and
reinserts its rows every run, a pre-existing design choice unrelated to this sprint — **BL-020**).

`ai/embeddings/search.py::semantic_search` ranks `Embedding` rows by pgvector cosine distance,
always filtered by `assessment_id` (persistence-model.md: "Semantic retrieval is always
Assessment-scoped by default") with an optional `entity_types` filter. Exposed as a debug-only
`GET /assessments/{id}/semantic-search?q=...&entity_types=...` endpoint (never mutates state,
never returns raw vectors) and a minimal `SemanticSearchPanel` frontend component, wired into a
new sidebar "Debug" nav group deliberately separate from the canonical Dashboard Geral +
4-perspective result views (Baseline core rule 15) — this is the sprint's own "simple semantic
search UI/debug endpoint" capability, not a 5th perspective.

Embeddings are not run through the ADR-012 versioned-prompt-schema/domain-validation framework
the other `ai.*` capabilities use: unlike Object Understanding/Business Rules/Clean Core Analysis,
an embedding is a derived numeric index artifact, not an interpretive conclusion with a risk level
or a citable evidence chain — there is no domain rule to validate beyond "meaningful semantic
entity with metadata" (rule 14), which the source builder's quality gates already enforce. See
`ai/embeddings/__init__.py`'s module docstring for the full rationale.

## Demonstration path
1. Open an Assessment, ingest `demo-source/ABAP`, run "3 - Processamento por IA" to completion
   (now 8 stages, ending in the `embeddings` stage).
2. Open the new "Debug" → "Busca Semântica" nav item.
3. Type a business concept (e.g. "validação de pedido") and submit.
4. Ranked results appear — rules, objects and applications relevant to the concept, each tagged
   with its entity type, a relevance score and metadata chips (e.g. `rule_type`, `object_type`,
   `application_id`) — scoped to the open Assessment only.
5. Toggling an entity-type filter chip (e.g. "Aplicação") reactively narrows the results to that
   type alone.

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint: backend `/health` reports
  `migration_revision: 0016_embeddings`, `pgvector: true`; `alembic heads` at
  `0016_embeddings (head)`, applied linearly from `0015`.
- [x] Critical contracts introduced by the sprint: `EmbeddingProvider`/`EmbeddingRequest`/
  `EmbeddingResult` (`ai/embedding_provider.py`), `get_embedding_provider`
  (`ai/embedding_providers/__init__.py`), `collect_embeddable_entities`
  (`ai/embeddings/source_builder.py`), `semantic_search` (`ai/embeddings/search.py`), the 8th
  `StageDefinition` (`pipeline/stages.py`), and `GET /assessments/{id}/semantic-search`
  (`api/routes/semantic_search.py`) — covered by `tests/test_embeddings_pipeline.py` (5 tests:
  entity creation across all 3 pipeline-produced types, incrementality/upsert-vs-recreate
  behavior, the `EVIDENCE_RECORD` quality gate, cosine-ranking + assessment-scoping of the search
  service, and the HTTP API contract).
- [x] Primary demonstrable user flow: reproduced live via Playwright against the real
  electron-vite renderer (`localhost:5173`) with a real Bedrock pipeline run (structured
  completion + Titan Text Embeddings V2) over `demo-source/ABAP` — ingested, processed all 8
  stages to completion (12/12 embedding work items, 0 failures), opened "Busca Semântica",
  searched "validação de pedido", confirmed order-validation rules/objects ranked highest, and
  confirmed the entity-type filter chip reactively narrows results. Disposable demo
  Client/Assessment deleted afterward (scoped `DELETE FROM client WHERE id = ...`, twice — once
  per live-validation run during implementation).
- [x] Required integration checks: full backend suite **213/213** `pytest` passed (run three
  times across implementation/review/closure, on a freshly rebuilt Docker image with `pgvector`
  baked into `backend/pyproject.toml`); frontend `tsc --noEmit` and `npm run build` both clean.
  Pre-existing tests updated for the new 8-stage pipeline: `test_foundation.py` (migration
  revision 0015→0016), `test_sprint06.py` (stage count 7→8, `embeddings` added to the expected
  set), and a `_FakeEmbeddingProvider` monkeypatch added to the 4 pipeline-integration test files
  that already mock `get_provider` (`test_object_understanding_pipeline.py`,
  `test_business_rule_discovery_pipeline.py`, `test_application_discovery_pipeline.py`,
  `test_clean_core_analysis_pipeline.py`) so their existing mocks still reach a "completed" run
  without an unmocked live Bedrock embedding call.
- [x] Migration applicability: `0015_clean_core_analysis` → `0016_embeddings` applied both forward
  and reverted cleanly (`alembic downgrade`/`upgrade` round-trip during CAP-002); `alembic check`
  shows zero new drift for `embedding` — the only remaining drift is the pre-existing BL-013
  `sap_object`/`technical_finding` noise, unrelated to this sprint.

## Key implementation notes
- **`backend/src/ai/embedding_provider.py`** + **`ai/embedding_providers/{bedrock,azure_foundry,__init__}.py`**
  (new): Bedrock (Amazon Titan Text Embeddings V2, live-validated) + Azure AI Foundry
  (unit-tested only, no credentials in this environment — mirrors the ADR-006 Azure precedent
  since SPRINT-09/12). New `settings.py` fields: `embedding_provider`,
  `bedrock_embedding_model_id`, `embedding_dimensions`, `azure_foundry_embedding_deployment`.
- **`backend/src/persistence/models.py::Embedding`** (+ `SemanticEntityType`) — migration
  `0016_embeddings`. Polymorphic `entity_type`/`entity_id` (no FK, mirrors
  `EvidenceCorrelation.target_type`/`target_id`); `Vector(1024)` + HNSW cosine index.
- **`backend/src/ai/embeddings/`** (new): `source_builder.py`, `search.py`.
- **`backend/src/pipeline/stages.py`**: `_embeddings_prepare`/`_embeddings_process_item`, 8th
  `StageDefinition`.
- **API**: `api/routes/semantic_search.py` + `api/schemas/semantic_search.py`.
- **Frontend**: `components/debug/SemanticSearchPanel.tsx` (new); `Sidebar.tsx`/`Workspace.tsx`
  gained a "Debug" nav group; `lib/api.ts::fetchSemanticSearch`.
- **`.gitignore` fix**: the pre-existing blanket `embeddings/` pattern (meant for a file-based
  vector-index cache from before pgvector was decided, ADR-004) shadowed the new
  `backend/src/ai/embeddings/` source directory — re-anchored to `/embeddings/` (root-only).

## Known limitations
- **BL-020** (new): `business_rule_discovery`'s recreate-not-upsert semantics leave orphaned
  `Embedding` rows on reprocessing — pre-existing design choice of that stage, not this sprint's
  own incrementality logic. Low severity at PoC demo scale.
- `CleanCoreAssessment` conclusions are intentionally not embedded — not named in the sprint's
  stated demonstrable outcome (rules/applications/objects/process evidence); revisit only if a
  future sprint's demonstrable outcome explicitly asks for it.
- Azure AI Foundry embedding adapter ships unit-tested only, mirroring the ADR-006 Azure
  precedent — live validation deferred until credentials are available.
- The Copilot's stated future ability to "route to semantic search" (Baseline core rule 17) is not
  implemented this sprint — only the standalone debug endpoint/UI, as planned.

## Deferred items
- **BL-020** (new): orphaned `Embedding` rows on `business_rule_discovery` reprocessing.
- BL-008/BL-013 through BL-019 are pre-existing and unrelated to this sprint, untouched.

## Repository closure
- Sprint branch: `sprint/14-embeddings-and-semantic-retrieval`
- Official commit message: `feat(sprint-14): complete embeddings and semantic retrieval`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
