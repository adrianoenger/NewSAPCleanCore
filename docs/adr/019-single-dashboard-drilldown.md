# ADR-019 — Dashboard Geral as Single Drill-Down Results Screen

- **Status:** Accepted (human decision, 2026-09-29, SPRINT-18)
- **Date:** 2026-09-29
- **Revises:** ADR-009 (Result Navigation Perspectives)

## Context
In the demo review the four result perspectives (Executive, Technical, Functional, Architecture) fragmented the exploration: the Dashboard KPIs were not clickable and each detail lived in a different view.

## Decision
- Opening an Assessment lands on **Dashboard Geral**, the single results screen.
- Every KPI/panel/chart segment is clickable and opens a **full-page list** (objects, applications, findings, business rules), filtered by what was clicked; every list row opens a **full-page detail** containing all analysis for that item, with cross-links (object ↔ application ↔ business rule ↔ finding). A breadcrumb/back control keeps the drill-down path.
- The sidebar results group contains **Dashboard Geral** and **Resumo Executivo** (a generated pt-BR markdown executive summary). The Executive/Technical/Functional/Architecture views are removed from navigation; their detail components are reused inside the drill-down.
- Processing-stage navigation (Ingestão, ATC, Processamento por IA) and the permanent Copilot (ADR-010) are unchanged. The Copilot's navigation targets open the corresponding drill-down detail.

## Consequence
`docs/ux/navigation-views.md` is amended accordingly. The perspective concept of ADR-009 remains valid as content grouping inside detail pages, not as top-level navigation.
