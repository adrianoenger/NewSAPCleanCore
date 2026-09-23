# Current Solution — Assets to Reuse or Migrate

The current source package contains notebook-driven processing, Python parsers, SQLite schema/models, ATC input and generated reports.

## Reuse candidates
- `parsers/common.py`
- `parsers/programas.py`
- `parsers/funcoes.py`
- `parsers/mensagens.py`
- `parsers/ddic.py`
- existing parsing rules embedded in notebooks;
- ATC ingestion logic;
- existing conceptual data ideas such as a unified SAP object catalog and dependency model;
- existing AI prompts/results as historical examples;
- existing report outputs as demonstration/reference material.

## Migration rule
Notebooks are laboratories/reference, not runtime architecture. Move reusable logic into testable Python modules and backend services.

## Do not carry forward blindly
- SQLite as target persistence;
- direct notebook orchestration;
- client-specific assumptions;
- static report as the primary UX;
- provider-specific LLM code spread through notebooks;
- secrets from legacy `.env`.

## Important legacy principle retained
Separate objective SAP/ATC facts from reprocessable AI interpretation and preserve end-to-end traceability.
