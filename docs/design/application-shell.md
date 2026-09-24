# Application Shell — SAP Clean Core Analyzer

**Status:** Approved for PoC — revised 2026-09-24

## 1. Core decision
The shell has two states:

1. **Assessments Home:** Main Workspace | AI Copilot — no left sidebar.
2. **Assessment Workspace:** Sidebar | Main Workspace | AI Copilot.

The AI Copilot is permanently available on the right in both states.

## 2. Desktop composition
Target: desktop widescreen, reference 1920×1080.

Assessment Workspace recommended distribution:
- Sidebar: ~220–250px;
- Main Workspace: flexible;
- AI Copilot: ~360–480px, resizable.

On Assessments Home the workspace receives the space normally occupied by the sidebar.

## 3. Assessments Home
First application screen. It contains:
- title / product identity;
- filters for Client and Assessment;
- assessment grid/list;
- `Novo Assessment`;
- `Novo Cliente`;
- status/last-updated metadata when available.

No navigation sidebar is rendered here.

## 4. Assessment Sidebar
Only visible with an active Assessment:

```text
Clean Core
  1 - Ingestão dos dados
  2 - Análise ATC
  3 - Processamento por IA

Resultado
  Dashboard Geral
  Executive View
  Technical View
  Functional View
  Architecture View
```

Active selection uses T-Systems magenta `#E30074` as an accent, not as a full background fill.

## 5. Main Workspace
Inside an Assessment show Client / Assessment context and relevant source SAP system metadata. The workspace should feel like stages and perspectives of one Assessment, not separate products.

Source Ingestion has no pre-populated source path. Browse must precede Start Scan; Start Scan is disabled until a valid selection exists.

AI Processing completion should surface KPI cards such as:
- Objetos analisados;
- Customizações identificadas;
- Findings críticos;
- Objetos com alto impacto;
- Regras de negócio identificadas.

## 6. Permanent AI Copilot
The right panel remains available on:
- Assessments Home;
- ingestion;
- ATC analysis;
- AI processing;
- Dashboard Geral;
- Executive, Technical, Functional and Architecture views.

Inside an Assessment it should know at least:
- client / assessment identity;
- current stage or result view;
- selected object/finding/rule/application/code range;
- ATC context;
- relevant evidence references.

## 7. Context synchronization
Selecting a workspace element updates Copilot context without requiring copy/paste. Structured Copilot navigation actions may change the central workspace only through supported controlled UI actions.

## 8. Collapsed Copilot behavior
If collapsed:
- workspace expands;
- a persistent rail remains visible;
- context/conversation are preserved;
- reopening restores state.

## 9. Responsive scope
PoC prioritizes desktop. Avoid layout hard-coding that prevents future evolution.
