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

## Key rules
- AI may return `insufficient_context` and missing-context hints.
- AI may only cite evidence IDs supplied by the backend.
- Prompts and schemas are versioned.
- Use structural ABAP chunking (method/form/include/class boundaries) before token-only chunking.
- Do not analyze every trivial object with AI; support eligibility/analysis level decisions.
- Persist each completed AI work item immediately.
