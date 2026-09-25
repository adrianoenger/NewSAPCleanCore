# AI Architecture

## Providers
Support both AWS Bedrock and Azure AI Foundry through an internal provider abstraction.

```text
Domain AI Service
      ↓
AIProvider interface
  ├── BedrockProvider
  └── AzureFoundryProvider
```

Domain services must not depend directly on provider SDKs.

## AI capabilities
- Object Understanding
- Business Rule Discovery
- Business Rule Consolidation
- Application Discovery
- SAP Knowledge Interpretation
- Clean Core Assessment
- Recommendation Generation
- AI Copilot

## Structured AI by default
Persistable pipeline AI outputs must use typed structured schemas, not free-form text as the primary contract.

Validation path:
LLM response → schema validation → evidence-reference validation → domain validation → persist.

Before invoking AI, backend services assemble provider-neutral evidence packages from canonical SAP/source facts, ATC and reliably correlated supplemental `EvidenceRecord` data. Prompts must not consume raw Panaya/Signavio/FUE schemas directly.

## Key rules
- AI may return `insufficient_context` and missing-context hints.
- AI may only cite evidence IDs supplied by the backend.
- Process/usage/user-role evidence may add business context, but correlation quality and provenance must be supplied to the model and preserved in outputs.
- Opaque or partially decoded evidence is never passed as if it were a verified fact.
- Prompts and schemas are versioned.
- Use structural ABAP chunking (method/form/include/class boundaries) before token-only chunking.
- Do not analyze every trivial object with AI; support eligibility/analysis level decisions.
- Persist each completed AI work item immediately.
