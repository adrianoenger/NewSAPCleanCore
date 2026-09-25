# SAP Clean Core Analyzer — Documentation Index

> Status: baseline de documentação da PoC atualizada em 25/09/2026 — R3.3.

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
9. Relatórios ATC em `.xlsx` são tratados como fontes semi-estruturadas: colunas opcionais/novas não devem quebrar a ingestão; dado bruto e mapeamento devem ser preservados.
10. Exportações complementares de landscape/processo/uso entram por uma camada genérica de **Evidence Datasets**, com adapters por formato, proveniência obrigatória e correlação explícita; não viram novos tipos de `SAPObject`.

## Documentos de design e experiência

- [`design/design-system.md`](design/design-system.md) — tokens visuais, cores, tipografia, espaçamento e componentes.
- [`design/application-shell.md`](design/application-shell.md) — shell em dois estados: Assessments Home sem sidebar e Assessment Workspace com sidebar; AI Copilot permanente.
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

Esses documentos preservam o histórico e o detalhamento da modelagem/analítica já produzida. Esses documentos são históricos/analíticos e não prevalecem sobre `delivery/IMPLEMENTATION_BASELINE.md`, ADRs aceitas ou a documentação atual em `product/`, `ux/` e `design/`.


## Current product correction — 2026-09-24

Baseline R3.3 preserves completed Sprints 00–07 and inserts a new Sprint 08 for Supplemental Evidence Foundation. Former future Sprints 08–16 were shifted to 09–17, with exactly one canonical definition per sprint number.

ATC import is governed by `data/atc-import-contract.md` and `adr/016-variable-atc-xlsx-import.md`: the reviewed 21-column sample is a reference, not a fixed schema.


The canonical UX/domain model is Assessment-centric: `Client → Assessment`, with `sap_source_system` as Assessment metadata. The application starts on Assessments Home without a left sidebar; the Assessment sidebar appears only after an Assessment is opened; the AI Copilot stays on the right. See `adr/015-assessment-centric-workspace.md` and `delivery/IMPLEMENTATION_BASELINE.md`.


## Supplemental evidence architecture — 2026-09-25
ADR-017 and `data/supplemental-evidence-import-contract.md` define the optional evidence path for Panaya ETL, SAP Signavio Process Insights and FUE User Validation. These packages are handled inside Step 1 as complementary evidence sources and feed the shared Assessment evidence graph before downstream AI/Clean Core intelligence.
