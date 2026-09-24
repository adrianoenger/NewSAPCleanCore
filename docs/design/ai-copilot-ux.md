# AI Copilot UX and UI Contract

**Status:** Approved for PoC

## 1. Role

O AI Copilot é a camada conversacional e de navegação inteligente da aplicação. Ele não é um chatbot isolado: opera sobre o mesmo modelo de aplicação SAP apresentado visualmente no workspace.

O Copilot deve conseguir:

- explicar arquitetura;
- sintetizar riscos;
- explicar findings e regras de negócio;
- localizar evidências;
- relacionar objetos e dependências;
- apresentar alternativas Clean Core;
- destacar elementos no workspace;
- navegar para objetos/findings/rules/evidence;
- comparar elementos quando a visão suportar.

## 2. Provider abstraction

A experiência não expõe o provedor de LLM como parte do fluxo principal.

A camada de IA da PoC deve suportar:

- AWS Bedrock;
- Azure AI Foundry.

A lógica de domínio e o contrato do Copilot não devem depender diretamente do SDK de um provedor específico.

## 3. Required context

Cada interação deve poder receber contexto estruturado semelhante a:

```json
{
  "application_id": "...",
  "analysis_run_id": "...",
  "view": "architecture_clean_core",
  "selection": {
    "type": "sap_object",
    "id": "..."
  }
}
```

Quando pertinente, acrescentar object, finding, rule, dependency ou code range.

## 4. Structured response contract

O backend não deve retornar somente texto. A resposta deve admitir dados estruturados para que a interface possa reagir de forma determinística.

Contrato conceitual mínimo:

```json
{
  "intro": "...",
  "items": [],
  "outro": "...",
  "refs": [
    {"type": "object|finding|rule|evidence", "id": "...", "label": "..."}
  ],
  "sources": [
    {
      "object": "...",
      "method": "...",
      "line_start": 0,
      "line_end": 0,
      "analysis_run_id": "..."
    }
  ],
  "highlight": ["optional object ids"],
  "action": {
    "type": "optional action type",
    "payload": {}
  }
}
```

O contrato final pode evoluir, mas os conceitos de `refs`, `sources`, `highlight` e `action` são requisitos de produto.

## 5. Allowed UI actions

A PoC deve começar com um conjunto reduzido e explícito de ações, por exemplo:

- `select_object`
- `open_finding`
- `open_rule`
- `open_evidence`
- `highlight_objects`
- `switch_view`
- `open_engineering`
- `clear_highlight`

Ações devem ser validadas no frontend/backend. O modelo não deve injetar comandos arbitrários de UI.

## 6. Evidence-first behavior

Toda resposta que faça afirmação analítica ou recomendação deve oferecer evidências quando disponíveis.

A evidência deve referenciar, conforme o caso:

- SAP object;
- method/form/routine;
- code line range;
- ATC finding;
- dependency;
- metadata/source document;
- Analysis Run.

Padrão de UI recomendado: `View Evidence · N Sources`.

## 7. Conversation design

### Header

- AI Copilot
- T-Systems identity, de forma discreta
- current context
- history/new chat/collapse quando suportado

### Messages

User messages: bubble discreto à direita.  
AI messages: texto sem bubble pesado, com estrutura de leitura, referências clicáveis e evidências.

### Suggestions

Sugestões são contextuais. Exemplos:

- Explain architecture
- Summarize risks
- Find SAP standard alternatives
- Show affected business rules
- Create modernization summary

Não fixar sugestões irrelevantes em todas as telas.

## 8. Pending and error states

Pending deve indicar a tarefa contextual, por exemplo:

`Tracing dependencies and evidence for ZCL_ORDER_VALIDATION…`

Erros devem preservar contexto e permitir nova tentativa sem perder a seleção.

Nunca inventar evidência quando uma fonte não está disponível. A UI deve distinguir claramente:

- grounded analysis;
- inferred interpretation;
- unavailable evidence.

## 9. Copilot-driven UI

Quando uma resposta retornar `highlight` ou `action`:

1. texto da resposta é apresentado;
2. referências permanecem clicáveis;
3. workspace executa apenas ações suportadas;
4. feedback visual informa a mudança;
5. usuário pode desfazer/limpar o estado transitório quando pertinente.

Essa capacidade é essencial para diferenciar o Copilot de um chat lateral passivo.
