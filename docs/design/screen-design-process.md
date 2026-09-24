# Screen Design Process — PoC

**Status:** Approved for PoC

## 1. Goal

Introduzir uma etapa leve de design antes da implementação de cada visão sem transformar a PoC em um processo corporativo pesado.

## 2. Flow

**Functional Definition → High-Fidelity Mockup → Design Review → Interaction Contract → Implementation → Visual Review**

## 3. Functional definition

Antes do mockup, registrar apenas o necessário:

- persona principal;
- pergunta que a tela precisa responder;
- dados principais;
- ações principais;
- relacionamentos com outras visões;
- contexto que deve ser fornecido ao Copilot.

## 4. High-fidelity mockup

O mockup deve obrigatoriamente reutilizar:

- application shell;
- dark design system;
- `#E30074` como brand/action/AI color;
- padrões de evidência;
- contexto do Copilot;
- estados de seleção, loading, empty e error quando relevantes.

Não criar um novo design system por tela.

## 5. Design review checklist

Uma tela está pronta para implementação quando responde positivamente a:

- está dentro do shell padrão?
- o Copilot permanece disponível?
- há hierarquia clara entre aplicação, run, seleção e conteúdo?
- itens gerados por IA possuem caminho de evidência?
- elementos selecionáveis possuem estado visual definido?
- navegação para objeto/finding/rule/evidence está definida?
- loading/empty/error foram considerados quando críticos?
- a tela respeita os tokens do design system?
- a experiência continua coerente com o shell Assessment-centric e com as perspectivas Executive, Technical, Functional e Architecture?

## 6. Interaction contract

Antes de codificar, definir os eventos e dados mínimos, por exemplo:

- `object_selected`
- `finding_selected`
- `rule_selected`
- `evidence_opened`
- `copilot_action_received`
- `highlight_changed`
- `view_changed`

Não é necessário formalizar todos como eventos de domínio; o objetivo é evitar lógica de interação inventada durante a implementação.

## 7. Implementation

A implementação deve criar componentes reutilizáveis para:

- application shell;
- Copilot panel;
- context chips;
- evidence references;
- status/severity;
- cards/tables;
- graph selection/highlight;
- loading/empty/error states.

## 8. Visual review

Comparar a implementação com o mockup e validar principalmente:

- proporções;
- hierarchy;
- typography;
- spacing;
- selection states;
- color semantics;
- Copilot behavior;
- evidence affordances.

Pixel-perfect não é um requisito absoluto da PoC; coerência e usabilidade são.

## 9. Recommended next screens

Priorizar conforme o roadmap vigente:

1. Assessments Home e shell Assessment-centric (Sprint 04)
2. ATC Analysis
3. AI Processing/progress
4. Dashboard Geral
5. Executive View
6. Technical View
7. Functional View
8. Architecture View

O mockup histórico Architecture & Clean Core continua útil como referência visual interna para Architecture View, mas não define a navegação canônica.
