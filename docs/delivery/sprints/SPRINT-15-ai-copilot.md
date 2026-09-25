# SPRINT-15 — AI Copilot

## Position in the sequence
- Prerequisite: SPRINT-14 completed.
- Coherence rule: The Copilot is permanently mounted on the right, context-aware, and may propose/navigate controlled UI actions but never mutate Assessment state without explicit user action.

## Goal
Make the right-side Copilot fully contextual and navigable.

## Planned capabilities
- Keep Copilot permanently mounted in AppShell.
- Publish UI context and selected source/entity context.
- Route questions to structured query, semantic retrieval, source retrieval and MCP as appropriate.
- Return answer references and navigation actions.
- Preserve conversation while navigating and switching views.

## Demonstrable outcome
Ask questions from different views, select code, follow Copilot references back to source/findings/guidance, and continue the same conversation.

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
