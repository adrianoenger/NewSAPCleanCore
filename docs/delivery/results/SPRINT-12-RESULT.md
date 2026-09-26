# SPRINT-12 Result — SAP Knowledge MCP

**Status:** Completed
**Completed at:** 2026-09-26
**Official commit:** resolve from Git history using the sprint commit message after closure

## Delivered increment
Introduced `SAPKnowledgeProvider` — an ADR-006/ADR-007-style abstraction connecting configurable
`mcp-sap-docs`/`mcp-abap` streamable-HTTP endpoints, called on demand from an Application or
BusinessRule detail view ("SAP Guidance") rather than as a pipeline stage: ADR-007 explicitly
calls for "contextual enrichment ... rather than indiscriminate per-object calls", and the
sprint's own "Query only when relevant" capability rules out an automatic per-object call during
`source_processing`. `ai/knowledge_service.py::fetch_guidance` enforces that two ways — it is only
ever invoked by an explicit `POST`, never a background job, and a target that already has a
persisted reference from a given provider is never re-queried. A `query_fingerprint`
(provider + normalized query text) still lets a *different* target with an equivalent query reuse
a prior retrieval instead of calling MCP again (ADR-007: "cache/reuse semantically equivalent
guidance when safe") — safe here because SAP/ABAP documentation is generic, not customer
evidence, unlike `EvidenceDataset`/`EvidenceRecord` (ADR-017), which this new
`SapKnowledgeReference` table is deliberately kept separate from.

The generic `MCPKnowledgeProvider` adapter (`ai/knowledge_providers/mcp_client.py`) targets the
real `mcp` Python SDK (`mcp>=1.2`, resolved to `mcp==2.2.0` — its actual API differs substantially
from older SDK documentation; every call site was written and fixed against the installed
package's real signatures/field names, not assumption). It deliberately does not assume any
project-specific result shape: neither `mcp-sap-docs` nor `mcp-abap` publish a stable structured-
content schema, so each MCP text content block becomes one `KnowledgeReference` (first line as
title, remainder as summary) — honest about what was actually retrieved, never a guessed layout.
`GET/POST /assessments/{id}/sap-knowledge/{applications|business-rules}/{target_id}` expose it;
`GET` only reads what was already retrieved, `POST` is the only trigger. The frontend's
`SapGuidancePanel` (an explicit "Consultar SAP Docs" button, never automatic) is wired into
`ApplicationBrowser` and `BusinessRuleBrowser` — the two existing detail views with a
selectable-list-plus-detail-panel layout; `ATCFinding`'s flat table has no per-row detail view yet
to plug into (BL-017).

No real `mcp-sap-docs`/`mcp-abap` server/endpoint exists in this environment (unlike Bedrock,
which has real AWS credentials mounted) — the adapter is unit-tested against a mocked MCP
transport, and the persisted-guidance flow is proven end-to-end (API → service → persistence →
render) with a fake provider swapped in, mirroring how Azure AI Foundry shipped unit-tested-only
in SPRINT-09 (BL-018).

## Demonstration path
1. Open an Assessment with at least one discovered `Application` (Architecture View) or
   `BusinessRule` (Functional View) — from a completed "3 - Processamento por IA" run.
2. Select an application/rule → its detail panel shows a new "Orientação SAP" section with a
   "Consultar SAP Docs" button.
3. Click it → `POST /assessments/{id}/sap-knowledge/...` runs; with no `CCA_SAP_DOCS_MCP_ENDPOINT`/
   `CCA_ABAP_MCP_ENDPOINT` configured (this environment's actual state), the response is a clean
   empty list — the honest behavior per ADR-007, not fabricated guidance. With an endpoint
   configured, the same click persists and renders one card per retrieved reference (title,
   summary, `provider · reference · retrieved_at`, and a "reaproveitado" tag when reused from a
   prior semantically-equivalent query).
4. Re-opening the same application/rule shows the same guidance immediately via `GET`, without a
   new MCP call.

## Minimal validation executed
- [x] Startup/smoke checks required by the sprint (backend `/health` reports
  `migration_revision: 0014_sap_knowledge_mcp`; `alembic current`/`heads` both at
  `0014_sap_knowledge_mcp (head)`, applied linearly from `0013`).
- [x] Critical contracts introduced by the sprint: `SAPKnowledgeProvider`/`KnowledgeQuery`/
  `KnowledgeReference`/`KnowledgeQueryResult` (`ai/knowledge_provider.py`); `MCPKnowledgeProvider`
  against the real `mcp` SDK's `streamable_http_client`/`ClientSession`/`CallToolResult`
  (`ai/knowledge_providers/mcp_client.py`); `get_knowledge_providers` registry
  (`ai/knowledge_providers/__init__.py`); `build_query_text`/`list_guidance`/`fetch_guidance`
  cache-reuse/query-only-when-relevant/error-skip logic (`ai/knowledge_service.py`);
  `GET`/`POST /assessments/{id}/sap-knowledge/{target_kind}/{target_id}` — each covered by a
  dedicated test in `tests/test_sap_knowledge.py` (16 tests).
- [x] Primary demonstrable user flow: reproduced live via Playwright against the real
  electron-vite renderer (`localhost:5173`) — opened a throwaway demo Application's detail panel,
  confirmed the "Orientação SAP" empty state, clicked "Consultar SAP Docs", confirmed a clean
  `200` response and zero console errors (no MCP endpoint configured in this environment, so an
  empty reference list is the correct outcome). The full retrieval → persist → render → reuse
  path (with actual reference content) is proven by `test_post_guidance_persists_and_get_reflects`
  and the cache/reuse tests using a fake provider, since no real `mcp-sap-docs`/`mcp-abap` server
  exists to exercise live (see Known limitations). Disposable demo Client/Assessment/Application
  deleted afterward (scoped `DELETE FROM client WHERE id=:cid`).
- [x] Required integration checks: full backend suite **189/189** `pytest` passed — verified with
  pytest's own process exit code captured directly (`pytest -q > log 2>&1; echo $?`), after an
  earlier review pass had mistakenly trusted a piped invocation (`pytest -q | tail -N`) whose
  reported "exit code 0" was actually `tail`'s exit code, not pytest's, masking one deterministic
  failure and one apparent flake. The deterministic failure was
  `test_foundation.py::test_health_contract`'s hardcoded `migration_revision`
  (`0013_application_discovery` → `0014_sap_knowledge_mcp`, the same class of fix SPRINT-11 made
  for its own new migration); a clean direct-exit-code re-run confirmed 189/189. Frontend
  `tsc --noEmit` and `npm run build` both clean.
- [x] Migration applicability: `0013_application_discovery` → `0014_sap_knowledge_mcp` applied;
  `alembic current`/`heads` both at `0014_sap_knowledge_mcp (head)`.

## Key implementation notes
- **`backend/src/ai/knowledge_provider.py`** (new): `KnowledgeQuery`, `KnowledgeReference`,
  `KnowledgeQueryResult`, `SAPKnowledgeProvider` Protocol, `SAPKnowledgeProviderError`.
- **`backend/src/ai/knowledge_providers/`** (new): `mcp_client.py::MCPKnowledgeProvider` (generic
  one-tool-per-endpoint adapter), `__init__.py::get_knowledge_providers` (skips an unconfigured
  endpoint rather than raising).
- **`backend/src/ai/knowledge_service.py`** (new): `build_query_text` (derives the query from the
  target's own content, never free text from the caller), `list_guidance` (read-only),
  `fetch_guidance` (query-only-when-relevant + cross-target cache reuse + per-provider error
  isolation).
- **`backend/src/persistence/models.py`**: `SapKnowledgeReference` (+ `SapKnowledgeTargetType`) —
  migration `0014_sap_knowledge_mcp`. Kept separate from `EvidenceDataset`/`EvidenceRecord`
  (ADR-017) — a live MCP retrieval's provenance, never a dataset imported by the user.
- **`backend/src/api/`**: `schemas/sap_knowledge.py`, `routes/sap_knowledge.py` — `GET`/
  `POST /assessments/{id}/sap-knowledge/{applications|business-rules}/{target_id}`.
- **`backend/src/settings.py`**: `sap_docs_mcp_endpoint`/`sap_docs_mcp_tool_name`,
  `abap_mcp_endpoint`/`abap_mcp_tool_name` (both optional, `CCA_` env prefix).
- **Frontend**: `components/knowledge/SapGuidancePanel.tsx` (new), wired into
  `ApplicationBrowser.tsx` and `BusinessRuleBrowser.tsx`; `lib/api.ts` additions
  (`fetchSapGuidance`/`requestSapGuidance`/`SapKnowledgeGuidanceResponse`).
- `mcp>=1.2` added to `backend/pyproject.toml` (resolved to `mcp==2.2.0`); backend Docker image
  rebuilt. `.env.example` documents the two optional endpoint/tool-name pairs; `compose.yml`'s
  stale "introduced in SPRINT-09" comment corrected.

## Known limitations
- No real `mcp-sap-docs`/`mcp-abap` server/endpoint exists in this environment — the adapter is
  unit-tested against a mocked MCP transport only; live retrieval of real guidance content has
  never been observed against an actual running server. Recorded as **BL-018**.
- `ATCFinding` detail (Technical View / ATC import table) has no "SAP Guidance" block — its
  findings are a flat table with no per-row detail affordance to plug the panel into yet.
  Recorded as **BL-017**.
- Azure AI Foundry live validation remains deferred (unchanged from SPRINT-09/10/11 — no
  credentials available); unrelated to this sprint.

## Deferred items
- **BL-017** (new): ATC finding detail has no SAP Guidance block.
- **BL-018** (new): SAP Knowledge MCP adapter is unit-tested only, no real MCP server available.
- BL-013/BL-014/BL-015/BL-016 are pre-existing and unrelated to this sprint, untouched.

## Repository closure
- Sprint branch: `sprint/12-sap-knowledge-mcp`
- Official commit message: `feat(sprint-12): complete sap knowledge mcp`
- Final branch after closure: `main`
- Sprint branch pushed to remote: yes
- `main` pushed and equal to `origin/main`: yes
- Local sprint branch removed: yes
- Working tree clean: yes
