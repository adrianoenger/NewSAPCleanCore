# SPRINT-08 — AI Object Understanding

## Position in the sequence
- Prerequisite: SPRINT-07 completed.
- Coherence rule: AI work runs through the provider abstraction and must support AWS Bedrock and Azure AI Foundry without domain coupling to either SDK.

## Goal
Introduce provider-agnostic structured LLM processing.

## Planned capabilities
- Implement AIProvider abstraction with Bedrock and Azure Foundry adapters.
- Implement versioned prompt/schema registry.
- Build Object Understanding structured contract and validators.
- Support structural ABAP chunking for large objects.
- Persist model/provider/prompt/schema provenance.

## Demonstrable outcome
Open an object and see validated functional/technical purpose, concepts and confidence produced by selected provider.

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
