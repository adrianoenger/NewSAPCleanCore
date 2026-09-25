# SPRINT-13 — Embeddings and Semantic Retrieval

## Position in the sequence
- Prerequisite: SPRINT-12 completed.
- Coherence rule: Semantic retrieval is Assessment-scoped and complements structured facts; it must not become the authoritative persistence model.

## Goal
Enable semantic exploration without replacing structured facts.

## Planned capabilities
- Create embeddings for semantic entities with metadata filters.
- Store vectors in pgvector.
- Implement assessment-scoped semantic search service.
- Add a simple semantic search UI/debug endpoint.

## Demonstrable outcome
Search for a business concept and retrieve relevant rules/applications/objects only from the active assessment.

## Minimal validation
- Primary user flow for this sprint works.
- Relevant smoke test(s) pass.
- Critical API/schema/domain contracts introduced by this sprint are validated.
- Do not add broad test coverage unrelated to the demonstrated capability.

## Completion criteria
- Planned capabilities implemented or explicitly deferred with rationale.
- Demonstrable outcome reproduced successfully.
- Progress/state files updated.
- Application remains runnable for the next sprint.
