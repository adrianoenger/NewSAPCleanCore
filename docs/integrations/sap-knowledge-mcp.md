# SAP Knowledge via MCP

## Providers
The PoC integrates two configurable MCP servers already used by the project environment:
- `mcp-sap-docs`
- `mcp-abap`

They are community/open-source services, not assumed to be an SAP-operated public SLA service. Local Docker endpoints are the preferred controlled PoC mode; remote endpoints may be used as a development convenience when configured.

## Backend abstraction
```text
SAPKnowledgeProvider
  ├── SapDocsMCPProvider
  └── AbapMCPProvider
```

No React component calls MCP directly.

## Usage policy
- Do not call MCP for every object.
- Trigger enrichment when a relevant finding/application requires SAP context.
- Cache/reuse semantically equivalent guidance when safe.
- Persist retrieved title/reference/provider/summary and retrieval timestamp as SAP documentation evidence.

## Knowledge separation
- Local database/vector knowledge answers: **what exists in this assessment?**
- SAP MCP answers: **what does SAP/ABAP guidance recommend or explain?**
- AI synthesizes both while keeping provenance visible.
