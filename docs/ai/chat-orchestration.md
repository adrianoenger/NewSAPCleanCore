# AI Copilot and Chat Orchestration

## Permanent placement
The Copilot is permanently mounted on the right side of the App Shell on Assessments Home and in all Assessment stages/result views. It can be resized or collapsed to a narrow rail, but is not a separate destination.

## Context model
`AIContext` should include:
- client_id;
- sap_source_system (Assessment metadata, when relevant);
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
- supplemental evidence retrieval for process/usage/conversion/user-role context;
- SAP MCP for authoritative external guidance.

A question may use multiple sources.

## Answer contract
Return:
- answer text;
- citations/references to internal entities/evidence;
- optional navigation actions (`open_object`, `open_source`, `open_finding`, `open_rule`, `open_application`, `open_evidence_dataset`, `open_evidence_record`, `open_sap_guidance`).

## Behavior
- Preserve conversation across Assessments Home / Assessment transitions as appropriate and across view changes within an Assessment.
- Adjust language/depth to current navigation perspective.
- Support adding entities or code selections to Copilot context.
- Chat answers never mutate assessment state automatically. Explicit user action is required to apply an AI suggestion.
