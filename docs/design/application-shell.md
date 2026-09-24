# Application Shell — SAP Clean Core Analyzer

**Status:** Approved for PoC

## 1. Core decision

Todas as visões da aplicação devem operar dentro de um shell único composto por três regiões permanentes:

**Sidebar | Main Workspace | AI Copilot**

Essa estrutura é uma decisão de produto e de arquitetura frontend, não apenas uma preferência estética.

## 2. Desktop composition

Target principal da PoC: desktop widescreen, com referência visual em 1920×1080.

Distribuição recomendada:

- Sidebar: aproximadamente 12–14% ou 220–250px.
- Main Workspace: aproximadamente 56–58% quando o Copilot está aberto.
- AI Copilot: aproximadamente 28–32%.

O Copilot pode ser recolhido para um rail estreito, liberando espaço para o workspace, mas deve permanecer imediatamente acessível.

## 3. Sidebar

Navegação sugerida:

- Applications / Dashboard
- Application Discovery
- Architecture & Clean Core
- Business Rules
- Engineering
- Analysis Runs
- Settings

A seleção ativa usa indicador magenta `#E30074`, sem preencher toda a sidebar com a cor de marca.

Na região inferior podem aparecer:

- sistema SAP conectado;
- ambiente;
- status de conexão;
- usuário/configurações.

## 4. Main Workspace

A região central representa a visão atual da mesma aplicação SAP analisada. Mudanças entre Executive, Architecture, Rules e Engineering não devem parecer troca entre produtos independentes.

Elementos compartilhados recomendados:

- breadcrumb;
- application identity;
- Analysis Run atual;
- status da análise;
- ações de re-run / compare / changes quando aplicável;
- seleção corrente;
- links para evidência.

## 5. Permanent AI Copilot

O painel direito é estrutural e permanece disponível em todas as visões:

- Executive Overview
- Application Discovery
- Architecture & Clean Core
- Clean Core Findings
- Business Rules
- Engineering
- Modernization Opportunities
- Analysis Runs, quando houver valor contextual

O painel deve conhecer no mínimo:

- application id/name;
- current view;
- selected object/finding/rule/code range;
- current Analysis Run;
- relevant evidence references.

## 6. Context synchronization

Ao selecionar um elemento no workspace, o contexto do Copilot deve atualizar sem exigir que o usuário repita o que está vendo.

Exemplos:

- selecionar `ZCL_ORDER_VALIDATION` atualiza o chip de contexto do Copilot;
- abrir `CC-003` torna o finding parte do contexto;
- selecionar linhas ABAP informa objeto, método e range;
- navegar pelo Copilot atualiza a interface central quando a ação estruturada solicitar isso.

## 7. Collapsed Copilot behavior

Quando recolhido:

- workspace expande para ocupar o espaço liberado;
- um rail persistente continua visível;
- contexto e conversa não são descartados;
- reabrir o painel restaura o estado anterior.

## 8. Responsive scope for PoC

A PoC prioriza desktop. Responsividade completa mobile/tablet não é requisito inicial.

O frontend deve, porém, evitar hard-coding que inviabilize evolução futura. Breakpoints e dimensões podem ser parametrizados por tokens/layout primitives.
