# ADR-UX-001 — Context-Aware AI Copilot as Application Controller

- **Status:** Accepted
- **Date:** 2026-09-23
- **Scope:** SAP Clean Core Analyzer PoC

## Context

The product needs to connect executive understanding, business rules, architecture, Clean Core findings, engineering evidence and modernization recommendations. A conventional chat window beside independent pages would force users to repeat context and would not exploit the structured application model built by the analysis pipeline.

The high-fidelity Architecture & Clean Core mockup validated a stronger interaction model: the Copilot is permanently available, receives the current application/view/selection context and can return typed references and supported UI actions.

## Decision

The SAP Clean Core Analyzer will implement the AI Copilot as a **persistent, context-aware region of the application shell** and as a **controlled application interaction layer**.

The Copilot:

1. is available in the right region of all principal views;
2. knows application, Analysis Run, current view and current selection;
3. receives context updates from workspace interactions;
4. returns structured references to objects, findings, rules and evidence;
5. may request a limited set of validated UI actions such as navigation and graph highlighting;
6. always preserves traceability for analytic/recommendation responses when evidence exists;
7. uses a provider-agnostic AI contract so the domain layer can operate with AWS Bedrock or Azure AI Foundry;
8. does not expose provider-specific SDK concepts in the main UI.

## Structured response

A Copilot response is not modeled as plain text only. It may contain:

- narrative (`intro`, `items`, `outro`);
- typed references (`refs`);
- evidence (`sources`);
- temporary visual highlight (`highlight`);
- optional validated action (`action`).

The concrete API schema may evolve, but these semantics are part of the accepted architecture.

## UI action safety

The model cannot execute arbitrary frontend code. Only whitelisted actions are interpreted by the application. The UI/controller validates payloads before changing application state.

## Consequences

### Positive

- less repeated context in chat;
- stronger continuity between business and technical views;
- explainability and traceability become visible product capabilities;
- the Copilot differentiates itself from a passive side chat;
- frontend interactions can remain deterministic despite LLM-generated language;
- AI provider can change without redesigning the UX contract.

### Trade-offs

- requires a shared selection/context model across screens;
- requires explicit action schemas and frontend validation;
- requires evidence/reference identifiers to be stable enough for deep links;
- adds integration work between chat responses and workspace state.

## PoC implementation guidance

Start with a narrow action set:

- select object;
- open finding;
- open business rule;
- open evidence;
- highlight object set;
- switch supported view;
- clear highlight.

Do not attempt a generic agentic UI runtime in the PoC.

## Related documentation

- `docs/design/application-shell.md`
- `docs/design/interaction-model.md`
- `docs/design/ai-copilot-ux.md`
- `docs/design/design-system.md`
