# Interaction Model — SAP Clean Core Analyzer

**Status:** Approved for PoC

## 1. Principle

A aplicação deve permitir navegação contínua entre níveis de entendimento:

**Executive Finding → Clean Core Finding → Business Rule → ABAP Object → Method / Code Evidence → Dependency Graph**

E também no sentido inverso.

O usuário explora perspectivas diferentes do mesmo modelo de aplicação, não conjuntos isolados de páginas.

## 2. Shared selection model

A seleção é um estado global do workspace. Tipos principais:

- application;
- SAP object;
- finding;
- business rule;
- dependency;
- code range;
- analysis run.

A seleção deve alimentar:

- detalhe da tela central;
- tab ativa quando pertinente;
- contexto do Copilot;
- referências/evidências disponíveis;
- ações contextuais.

## 3. Architecture graph behavior

### Node selection

Ao clicar em um node:

1. node torna-se selecionado;
2. detalhe do objeto é atualizado;
3. contexto do Copilot é atualizado;
4. findings/rules/dependencies relacionados são recarregados;
5. a seleção deve ser preservada ao alternar tabs relacionadas.

### Filter

Filtros devem reduzir ênfase dos nodes fora do critério, preferencialmente por opacidade, preservando contexto estrutural.

### Copilot highlight

Quando o Copilot solicita `highlight[]`:

- nodes relacionados recebem destaque controlado;
- elementos fora do conjunto são reduzidos em opacidade;
- edges do caminho relevante permanecem visíveis;
- a UI apresenta indicação de que o highlight foi disparado pelo Copilot;
- o usuário pode limpar o highlight manualmente.

## 4. Cross-navigation

### From Copilot references

- object reference → selecionar objeto e, se necessário, mudar para a visão adequada;
- finding reference → selecionar objeto, abrir Findings e ativar o finding;
- rule reference → abrir Rules e ativar a regra;
- evidence reference → abrir Engineering no objeto/método/linha correspondente.

### From workspace

- finding → evidência de código;
- business rule → objetos e evidências;
- dependency → selecionar objeto dependente;
- code annotation → finding/rule/dependency correspondente;
- modernization opportunity → findings e objetos que fundamentam a recomendação.

## 5. Interaction feedback

- Use transições curtas (~200ms) para borda, opacidade e selection state.
- Mudanças de contexto disparadas pela UI devem ser explicitadas no Copilot com um divisor discreto, por exemplo: `Context updated · ZCL_ORDER_VALIDATION selected`.
- Ações disparadas pelo Copilot devem gerar feedback visual no workspace, por exemplo: `Copilot highlighted 4 components`.
- Não usar animações decorativas que prejudiquem leitura técnica.

## 6. Persistence

No escopo da PoC, preservar ao menos:

- application corrente;
- Analysis Run corrente;
- view corrente;
- seleção corrente durante a sessão;
- conversa/contexto do Copilot durante a navegação entre visões.

Recarregamento total da aplicação pode evoluir posteriormente para restauração persistida do estado.

## 7. Human decision ownership

A IA apresenta evidência, contexto, alternativas e recomendações. Ela não deve comunicar decisões arquiteturais como se fossem automaticamente aprovadas.

A interface deve usar linguagem como:

- recommendation;
- suggested approach;
- modernization option;
- evidence;
- confidence;

Evitar linguagem que implique execução ou aprovação automática quando ainda há decisão humana.
