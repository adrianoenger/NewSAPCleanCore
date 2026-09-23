# AI Copilot and Chat Orchestration

## Permanent placement
The Copilot is permanently mounted on the right side of the App Shell in all navigation views. It can be resized or collapsed to a narrow rail, but is not a separate destination.

## Context model
`AIContext` should include:
- client_id;
- sap_system_id;
- assessment_id;
- view_mode: EXECUTIVE / ARCHITECTURE / FUNCTIONAL / TECHNICAL;
- current entity type/id;
- selected entities;
- selected source range;
- current route/view.

## Tool routing
The chat orchestrator chooses one or more sources:
- SQL/structured query for counts and facts;
- semantic retrieval for conceptual matches;
- source retrieval for code/evidence;
- SAP MCP for authoritative external guidance.

A question may use multiple sources.

## Answer contract
Return:
- answer text;
- citations/references to internal entities/evidence;
- optional navigation actions (`open_object`, `open_source`, `open_finding`, `open_rule`, `open_application`, `open_sap_guidance`).

## Behavior
- Preserve conversation across view changes within an assessment.
- Adjust language/depth to current navigation perspective.
- Support adding entities or code selections to Copilot context.
- Chat answers never mutate assessment state automatically. Explicit user action is required to apply an AI suggestion.
