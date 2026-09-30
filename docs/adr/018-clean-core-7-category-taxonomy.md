# ADR-018 — Clean Core 7-Category Recommendation Taxonomy

- **Status:** Accepted (human decision, 2026-09-29, SPRINT-18)
- **Date:** 2026-09-29
- **Supersedes:** the `RETAIN/REMEDIATE/REPLATFORM/RETIRE/REVIEW` recommendation values introduced in SPRINT-13.

## Context
The demo review asked for the Clean Core classification used by the customer's existing reporting (7 categories, pt-BR identifiers). The previous 5-value set also used `REVIEW` as a pseudo-category for failures, which mixed "the analysis could not conclude" with an actual recommendation.

## Decision
`CleanCoreAssessment.recommendation` takes one of:

| Value | Meaning |
|---|---|
| `MODERNIZAR` | Refatorar para ABAP Cloud / APIs liberadas. |
| `MANTER_AS_IS` | Já compatível ou sem risco relevante. |
| `REMEDIAR` | Corrigir violações pontuais (ATC / APIs não liberadas). |
| `DESCONTINUAR` | Sem uso ou obsoleto; pode ser removido. |
| `REIMPLEMENTAR_EXTENSAO` | Reconstruir como extensão side-by-side (BTP) ou key-user. |
| `SUBSTITUIR_STANDARD` | Existe funcionalidade standard SAP equivalente. |
| `ATUALIZAR_OSS` | Depende de nota OSS / correção SAP a aplicar. |

- Granularity is unchanged: one classification **per Application**; member `SAPObject`s inherit it (object-level counts are derived by membership).
- There is no fallback category. A failed or insufficient-context analysis persists `recommendation = NULL` with status `FAILED` / `INSUFFICIENT_CONTEXT`; the UI shows "Não classificado".
- Baseline core rule 8 is preserved: technical risk, business importance and recommendation stay independent fields, each with its own rationale and evidence refs (ADR-008/ADR-012).
- Existing rows are mapped by migration `0017`: RETAIN→MANTER_AS_IS, REMEDIATE→REMEDIAR, REPLATFORM→REIMPLEMENTAR_EXTENSAO, RETIRE→DESCONTINUAR, REVIEW→NULL. Reprocessing regenerates them with the new prompt.

## Consequence
The clean_core_analysis prompt/schema moves to `v2`. The 4-value mapping of old data is lossy by design (no old value maps to MODERNIZAR, SUBSTITUIR_STANDARD or ATUALIZAR_OSS); reprocessing is the authoritative way to reclassify.
