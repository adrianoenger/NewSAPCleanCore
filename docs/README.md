# SAP Clean Core Analyzer — Documentation Index

> Status: baseline de documentação da PoC atualizada em 23/09/2026.

Este diretório consolida a documentação funcional, de dados, arquitetura e experiência de usuário da PoC **SAP Clean Core Analyzer**.

## Princípios vigentes da PoC

1. A solução deve transformar artefatos SAP/ABAP em uma visão navegável que conecte **negócio, arquitetura, código, dependências, evidências, Clean Core e modernização**.
2. A coleta de artefatos SAP deve evoluir para conexão direta via **RFC/PyRFC**, integrada ao pipeline Python.
3. A camada de IA deve abstrair o provedor, suportando **AWS Bedrock** e **Azure AI Foundry** sem acoplamento da lógica de domínio aos SDKs específicos.
4. O **AI Copilot ocupa permanentemente a região direita da aplicação** e permanece disponível em todas as visões.
5. O Copilot é **context-aware**: conhece a aplicação, a visão, a seleção corrente e as evidências associadas, podendo também comandar navegação, seleção e highlights da interface por ações estruturadas.
6. Toda saída de IA que represente análise, finding, regra ou recomendação deve manter **rastreabilidade até evidências** e o respectivo Analysis Run.
7. A PoC utiliza uma estratégia de testes enxuta, priorizando fluxos críticos, contratos principais, persistência, retomada do pipeline e integrações centrais.
8. O design padrão é **Dark Enterprise**, com **#E30074** como cor oficial T-Systems para ações primárias, seleção, foco, IA e identidade.

## Documentos de design e experiência

- [`design/design-system.md`](design/design-system.md) — tokens visuais, cores, tipografia, espaçamento e componentes.
- [`design/application-shell.md`](design/application-shell.md) — shell permanente Sidebar + Workspace + AI Copilot.
- [`design/interaction-model.md`](design/interaction-model.md) — navegação contextual, seleção, highlights e sincronização entre visões.
- [`design/ai-copilot-ux.md`](design/ai-copilot-ux.md) — comportamento do Copilot, evidências e contrato de resposta estruturada.
- [`design/screen-design-process.md`](design/screen-design-process.md) — fluxo enxuto de design antes da implementação.
- [`product/application-experience.md`](product/application-experience.md) — personas, visões e jornadas principais.
- [`architecture/adr-ux-001-context-aware-ai-copilot.md`](architecture/adr-ux-001-context-aware-ai-copilot.md) — decisão arquitetural sobre Copilot contextual e controlador da UI.

## Referência visual

O mockup de alta fidelidade **Architecture & Clean Core** está preservado em:

- `design/reference/architecture-clean-core/`

Esse material é uma **referência de design/handoff**, não código de produção. A implementação deve reutilizar os princípios, tokens, interações e contratos documentados, sem copiar a estrutura HTML como arquitetura definitiva do frontend.

## Documentação analítica existente

- [`modelagem_conceitual.md`](modelagem_conceitual.md)
- [`plano_data_base.md`](plano_data_base.md)
- [`plano_sap_clean_core.md`](plano_sap_clean_core.md)

Esses documentos preservam o histórico e o detalhamento da modelagem/analítica já produzida. As decisões de UX descritas neste índice e na pasta `design/` passam a ser a fonte de verdade para a experiência da PoC.
