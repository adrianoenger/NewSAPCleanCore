# ADR-009 — Result Navigation Perspectives

**Status:** Accepted — revised 2026-09-24  
**Date:** 2026-09-23

## Decision
Expose **Dashboard Geral** plus four selectable result perspectives over the same Assessment:
- Executive View;
- Technical View;
- Functional View;
- Architecture View.

The four Views are UX perspectives, not user roles or permissions. Dashboard Geral is a synthesis/entry page and not an additional role/perspective.

Processing-stage navigation (Ingestão, ATC, Processamento por IA) is separate from results navigation.

## Consequence
Older labels such as `Architecture & Clean Core`, `Business & Rules` and `Engineering & Code` are superseded as top-level navigation names. Their useful content is redistributed into Architecture, Functional and Technical views respectively.
