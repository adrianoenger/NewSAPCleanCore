# SPRINT-18 — Final Adjustments

## Position in the sequence
- Prerequisite: SPRINT-17 completed.
- Coherence rule: Adjustments requested after the demo review. Preserve evidence-first (ADR-008), structured AI outputs (ADR-012), provider abstraction (ADR-006) and `Client → Assessment` (ADR-015). The Clean Core taxonomy change is governed by ADR-018.

## Goal
Make the assessment results consumable in pt-BR from a single drill-down Dashboard, give the Copilot enough assessment context to answer inventory/classification questions, and add a generated Executive Summary.

## Planned capabilities
- CAP-000 — Carry pending work from `main`: SE80 HTML parser and the critical-findings sample in the Copilot context.
- CAP-001 — All AI-generated analysis texts in Brazilian Portuguese (versioned v2 prompts; deterministic user-visible strings translated).
- CAP-002 — Clean Core 7-category taxonomy per Application, inherited by member objects (ADR-018): MODERNIZAR, MANTER_AS_IS, REMEDIAR, DESCONTINUAR, REIMPLEMENTAR_EXTENSAO, SUBSTITUIR_STANDARD, ATUALIZAR_OSS. Unclassified (failed/insufficient context) is `NULL`, not a category.
- CAP-003 — Dashboard Geral as the single result entry screen: clickable KPIs → full-page lists → full-page detail with all analysis per item; object inventory, ATC-by-priority and Clean Core distribution panels/charts. Executive/Technical/Functional/Architecture views leave the sidebar.
- CAP-004 — Copilot able to answer assessment-level questions (object catalog, Clean Core classification per application with rationale, ATC counts), with deterministic intent routing and tolerant evidence-ref validation.
- CAP-005 — Executive Summary: new pipeline stage + on-demand regenerate, persisted markdown in pt-BR, evidence-bound, rendered as formatted markdown in a new sidebar item.
- CAP-006 — AI-only reprocessing run (reuse the current scan, skip parse/dependencies).
- CAP-007 — Reprocess assessments so persisted texts are regenerated in pt-BR.

## Demonstrable outcome
Open an assessment → land on Dashboard Geral → click "Objetos analisados" → list → object detail with understanding, source, ATC findings, business rules, Clean Core classification; click a donut slice/ATC bar → filtered list; open "Resumo Executivo" (formatted markdown, pt-BR); ask the Copilot "Liste os objetos analisados" and "Quais objetos o clean core categorizou como Remediar? Explique o porquê" and get grounded answers with navigable references.

## Minimal validation
- Primary user flow for this sprint works (live Playwright).
- Relevant smoke test(s) pass.
- Critical API/schema/domain contracts introduced by this sprint are validated (taxonomy migration, dashboard overview, findings list, copilot catalog/intent, executive summary, AI-only reprocess).
- Do not add broad test coverage unrelated to the demonstrated capability.

## Completion criteria
- Planned capabilities implemented or explicitly deferred with rationale.
- Demonstrable outcome reproduced successfully.
- Progress/state files updated.
- Application remains runnable for the next sprint.
