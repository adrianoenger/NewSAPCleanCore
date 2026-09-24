# Plano: Modelagem do banco SQLite para análise de código SAP customizado (Clean Core)

## Context

Projeto de apoio à migração **SAP ECC → S/4HANA** do cliente **Copa Energia**, executado pela **T-Systems do Brasil**, sob o conceito **Clean Core**. A aplicação vai automatizar análise, remediação, modernização e classificação de código ABAP customizado (programas Z, user exits, enhancements, relatórios, interfaces, regras de negócio), reduzindo o esforço manual.

Frentes de trabalho:
1. **Análise** — inventário de objetos customizados, uso, obsolescência, risco, compatibilidade S/4HANA.
2. **Remediação** — apoio à correção automatizada de código quebrado por mudanças de tabelas/modelos/funções.
3. **Modernização** — sugestões para padrões ABAP modernos (performance, segurança, compatibilidade).
4. **Clean Core** — classificar cada customização em: descontinuar / remediar / modernizar / substituir por standard / reimplementar como extensão side-by-side.

Entrega final: **relatório único** respondendo quais programas ainda são usados, quais acessam tabelas alteradas no S/4HANA, quais têm problemas de performance, quais podem quebrar no upgrade, quais deveriam ser eliminados e quais podem ir para arquitetura aderente ao Clean Core.

**Entrada analítica privilegiada — ATC (ABAP Test Cockpit):** o cliente nos forneceu `Analise_ATC/ATC_20260427_ZandY_141515.xlsx` (+ DOCX narrativo), resultado oficial do ATC executado com a check variant **`S4HANA_READINESS_2025_NO_FLE`** contendo **7 899 findings** (2 139 Errors, 1 614 Warnings, 4 146 Info) em 11 categorias de checks que cobrem **Simplified Objects, Field Length Extensions, Database Operations, Simplified Transactions, SELECT sem ORDER BY, Critical Statements (Native SQL / DB Hints), ADBC, Readiness for SAP Queries, Base Tables de Views/CDS**, todas com `SAP Note Number`, `Short Text`, `Referenced Object` (tabela/DTEL/DOMA afetado) e `Simplification Item Category`. **Isso resolve oficialmente a parte técnica de detecção** ("quais acessam tabelas alteradas", "quais podem quebrar no upgrade", "quais têm problemas de performance") que planejávamos inferir com agentes IA. O papel dos agentes IA é reposicionado: passam a focar em **síntese** (`object_functional_summary` — objetivo funcional de negócio) e **decisão** (`clean_core_classification` — recomendação Clean Core considerando ATC + uso + contexto de negócio), e não mais em detecção técnica.

Arquitetura: **aplicação Python em notebooks separados por tarefa**, alimentando um **SQLite com suporte a embeddings** para consulta por agentes de IA.

## Escopo desta fase

Apenas **modelagem da estrutura de dados do SQLite**. Não haverá ingestão, parsers nem notebooks nesta etapa.

## Documento canônico da modelagem

**Fonte de verdade:** `C:\_Adriano\ClaudeCode\SapCleanCore\docs\modelagem_conceitual.md` (Entrega 1, versão 1.0, abril 2026).

Este plano mantém o **raciocínio de pesquisa** (achados por diretório, decisões de design com *why*, evolução histórica das escolhas); o `docs/modelagem_conceitual.md` tem o **modelo final publicável** para aprovação do cliente. Quando houver divergência, prevalece o `docs/modelagem_conceitual.md`. As diferenças estruturais desta versão formal em relação ao que este plano vinha modelando estão registradas na seção **"Diferenças entre o plano e o documento de Entrega 1"** adiante.

## Entregas incrementais previstas (doc formal)

1. **Entrega 1** — Modelagem conceitual (pré-DDL) — **concluída**, em `docs/modelagem_conceitual.md`.
2. **Entrega 2** — `db/schema.sql` (DDL SQLite) + indexes + sqlite-vec + constraints.
3. **Entrega 3** — Modelos SQLAlchemy Python.
4. **Entrega 4** — Estratégia de notebooks (pipeline ingestão → enriquecimento → IA → relatório).

**Decisões pendentes não-bloqueantes** (registradas na Entrega 1): prompt de extração do objetivo funcional, estratégia de chunking para includes muito grandes (ex.: `zcaiinc_frm_negocio_05.html` ~499KB), formato do relatório final (PDF/Excel/HTML interativo).

## Decisões já fixadas

| Decisão | Escolha |
|---|---|
| Vector store | **sqlite-vec** (extensão oficial moderna) |
| Modelo de embedding primário | **BAAI/bge-m3** executado **localmente** (via `sentence-transformers` ou `FlagEmbedding`). Dimensão **1024**. Multilingual nativo com forte suporte a português. Escolhido por: (1) **privacidade** — código do cliente nunca sai do ambiente T-Systems, requisito típico de cliente corporativo; (2) **reprodutibilidade/auditoria** — sem dependência de API externa; (3) **zero custo recorrente**; (4) equilíbrio qualidade × tamanho no SQLite. |
| Dimensão de embedding | **1024** (bge-m3). Schema continua flexível (`embedding_model.dimension` + uma `vec0` por dimensão), permitindo coexistir com outros modelos se necessário no futuro. |
| Granularidade de embeddings | Multi-grão: **objeto inteiro + unidade interna (método/form/routine) + metadados** — cobrindo casos de recuperação ampla e específica. A ser confirmado ao ver os exemplos |
| Dados de uso/execução | Schema vai prever **tabelas opcionais** para ingestão futura de ST03N / SCMON / UPL / Readiness Check, mesmo que só tenhamos análise estática agora |

## Fontes de dados (exportações SAP)

Raiz: `C:\_Adriano\ClaudeCode\SapCleanCore\abaps\` — HTML e TXT.

| Diretório / arquivo | Conteúdo |
|---|---|
| `abaps/dictionary_table_struc` | Estruturas de tabelas (campos, tipos, chaves) |
| `abaps/dictionary_table_type` | Tipos de tabelas (transparente, cluster, pool, CDS view etc.) |
| `abaps/Funções` | Function modules e function groups |
| `abaps/Mensagens` | Mensagens do sistema |
| `abaps/objetos` | Objetos diversos (a caracterizar ao ver amostras) |
| `abaps/Programas _e_classes` | Programas e classes (cada um é uma pasta) |
| `Analise_ATC/ATC_*.xlsx` | **Findings oficiais do ATC** (7 899 linhas, 20 colunas, variant S/4HANA Readiness 2025) — alimenta nova Camada F |
| `Analise_ATC/ATC_*.docx` | Relatório narrativo do mesmo ATC — `raw_document` para rastreabilidade |
| `Programas _e_classes` | Programas, classes, métodos |

## Achados da amostragem (2026-04-30)

Inspecionados ~12 arquivos cobrindo os 6 diretórios + observações complementares do usuário sobre `dictionary_table_struc`. Principais constatações que moldam o modelo:

1. **Template HTML uniforme** — `<title>` + `<h2>` com nome + `<h3> Description:` + tabelas ou blocos `<div class="code">`/`<div class="codeComment">`. Charset **ISO-8859-1**. Rodapé com versão do exportador (útil como metadado).
2. **Nome do diretório ≠ tipo semântico** — `dictionary_table_struc` tende a conter **structures** e **customer-includes** (`CI_*`, `Z01DT_*`) — definições de tipo sem persistência; `dictionary_table_type` tende a conter **tabelas transparentes** (ex.: `Z1B_MDFE_EVENTS`) com `MANDT` como primeiro campo e `Key = X`. Porém a estrutura HTML dos dois é **idêntica** (mesmas 10 colunas + "Fixed Domain Values" opcional) — a diferença é só semântica. Decisão: **uma única tabela `ddic_table` com coluna discriminadora `object_kind`** (TABLE / STRUCTURE / CUSTOMER_INCLUDE / TABLE_TYPE / VIEW / CDS), detectada pelo conteúdo (presença de MANDT + Key=X, prefixo CI_, título do HTML) e não pelo diretório.
3. **`objetos/` é o universo mestre**; os demais diretórios são recortes especializados com os mesmos arquivos.
4. **Arquivos duplicados entre diretórios** (ex.: includes compartilhados por função e programa). **Deduplicação por SHA-256 do conteúdo** é obrigatória.
5. **HTMLs com hyperlinks internos** — `<a href="...html">` permite extrair dependências sem precisar regex sobre ABAP.
6. **Function modules têm assinatura formal** em `codeComment` (`*"  IMPORTING / EXPORTING / CHANGING / TABLES / EXCEPTIONS`) — parseável para parâmetros e exceções.
7. **Cabeçalho `*$*$`** com Autor, Analista, Data, Projeto, Sistema, Finalidade, Histórico (RDM) — metadados valiosos por objeto.
8. **Screens em TXT** com seções `%_DYNPRO`/`%_HEADER`/`%_DESCRIPTION`/`%_FIELDS`/`%_FLOWLOGIC` — parser próprio.
9. **Programas compostos** referenciam includes via `INCLUDE X` (TOP/CLAS01/O01/I01/F01) e trazem dicionário e screens anexos.
10. **Objeto ≠ arquivo** — 1 arquivo pode descrever 1 ou mais objetos (ex.: uma função + seu global data); 1 objeto pode aparecer em vários arquivos por duplicação. Modelo precisa `source_file_object` (N:N).
11. **DDIC — estrutura HTML e entidades (consolidado a partir de `dictionary_table_struc/` e `dictionary_table_type/`):**
    - HTML idêntico entre as duas pastas: `<h2>` (nome) + `<h3>` (descrição, pode estar vazia) + tabela de 10 colunas (Row, Field name, Position, Key, Data element, Domain, Datatype, Length, Lowercase, Domain text) + bloco **opcional "Fixed Domain Values"** (Domain Name / Value Low / Value High / Text).
    - **Discriminador por conteúdo, não por diretório.** Heurísticas: presença de `MANDT` como primeiro campo + `Key = X` ⇒ tabela transparente client-dependent; prefixo `CI_*` ⇒ customer-include; ausência de chaves + prefixo `Z*/Y*` tipicamente estrutura; título do HTML ("Dictionary object (Table Type)") ⇒ table type.
    - **Data Elements e Domains são entidades de primeira classe**, reutilizáveis — viram tabelas próprias (`ddic_data_element`, `ddic_domain`) com integridade referencial a partir de `ddic_table_field`. O mesmo Domain (ex.: `ZZMSGTYP`, `ZZSEQNUM`) aparece em **múltiplos campos de múltiplas tabelas** — consolidar em entidade única com `UNIQUE(name)` evita duplicação massiva e habilita consultas tipo *"quais tabelas usam o domínio X?"* que alimentam agentes de IA.
    - **Fixed Domain Values** = entidade separada (`ddic_domain_fixed_value`) porque há N valores por domínio.
    - Campos podem ter Data element **e/ou** Domain vazios **independentemente** (ex.: `ACCKEY` com Domain preenchido mas sem Data element) — FKs nullable em ambos.
    - **Subtipos visíveis pelo prefixo**: `CI_*` (customer-include) / `Z*` / `Y*` / standard — relevante para Clean Core (customer-includes têm tratamento diferente de tabelas Z próprias). Vai para `ddic_table.ddic_subtype`.
    - **Datatypes ABAP aceitos como texto livre** (CHAR/CURR/QUAN/DEC/NUMC/CLNT/INT1/INT2/INT4/INT8/FLTP/DATS/TIMS/RAW/LRAW/STRG/TTYP/…). Sem enum rígido — apenas um `CHECK` frouxo ou nenhum. Novo datatype = nenhum breaking change.
    - Nome do arquivo segue `<nome_lowercase>.html` — heurística de normalização quando o `<h2>` vier sujo.
    - **Encoding ISO-8859-1 com mojibake** em vários exports (` ` no lugar de acentos). Parser registra `encoding_detected` e aplica correção heurística antes de gravar `content_text` em UTF-8.
15. **Programas e Classes (`Programas _e_classes/`) — cada programa é uma pasta com sua árvore completa:**
    - **Unidade de ingestão = diretório**, não arquivo. Exemplo `sapmz_cai_cadeia_transf/`:
      - Raiz: `sapmz_cai_cadeia_transf.html` (module pool principal, tipo M namespace Z) + 8 arquivos `zcaiinc_*.html` (includes segmentados em 00..08 para contornar limite de tamanho no ABAP: def/public, forms públicos, forms ALV, forms de negócio).
      - `dictionary/` — 26 tabelas Z específicas usadas pelo programa (`ztbcai_*`, `ztccai_*`, `ztbsd_*`, `ztbmm_*`), mesmo formato HTML das categorias 1 e 2.
      - `screens/` — 5 `screen_NNNN.txt` (dynpros) + 1 `gui_title_tl_NNNN.txt`.
    - **Cabeçalhos `*$*$` ricos nos programas** (mais ricos que nos outros tipos). Metadados que já estão mapeados em `abap_header_meta` / `abap_header_change` ganham aqui peso operacional:
      - `autor_original` + `analista` → rastreabilidade humana.
      - `data_criacao` → **idade do código** (proxy para "candidato a modernizar" — código escrito em 2013 e nunca alterado ≠ código iterado recentemente).
      - `projeto` + `sistema` → permite **agrupar Z's por domínio funcional** (ex.: "ANEXO — Controle Apuração ICMS" agrega múltiplos programas); adicionada coluna `business_system` em `abap_header_meta` com índice para suportar relatórios por sistema.
      - `finalidade` → texto livre do autor sobre o propósito; insumo direto para o agente IA validar contra o código real (coerência entre intenção declarada e implementação).
      - `histórico de modificações` (RDM + autor + data + descrição) → `abap_header_change` já cobre; adicionado campo derivado `modification_count` em `abap_header_meta` (proxy de criticidade/ativo vs estável).
    - **Includes "padrão" não materializados** — o module pool referencia via `INCLUDE`:
      ```
      INCLUDE sapmz_cai_cadeia_transftop .    " global Data
      INCLUDE sapmz_cai_cadeia_transfclas01.
      INCLUDE sapmz_cai_cadeia_transfo01 .    " PBO-Modules
      INCLUDE sapmz_cai_cadeia_transfi01 .    " PAI-Modules
      INCLUDE sapmz_cai_cadeia_transff01 .    " FORM-Routines
      ```
      Mas os arquivos físicos são `zcaiinc_*.html`. Hipótese: os includes `top/o01/i01/f01/clas01` são wrappers SAP-gerados que fazem `INCLUDE zcaiinc_*` internamente, e a exportação só trouxe os *leaves*. **Modelo precisa registrar referências a includes que podem não estar materializados** — já coberto pelo `object_reference.resolution_status` (`unresolved`/`resolved`). Sem refatoração.
    - **Classes locais vs globais** — o include `*clas01` traz classes ABAP **definidas dentro do module pool** (local classes), não classes globais SE24. Parser de classes precisa distinguir: `class.is_local` (bool) e `class.host_program_id` (FK para o programa que hospeda classe local). Classes globais têm `is_local=FALSE` e `host_program_id=NULL`.
    - **Dynpros como sinal forte para Clean Core** — telas dynpro são tecnologia legada em S/4HANA (Fiori-first). Programas com muitas dynpros + sub-screens + tab strips + ALV grids são **candidatos fortes a REIMPLEMENT_EXTENSION**. Adicionada métrica `dynpro_count` (cache) em `program` e regra automática `rule_high_dynpro_count` para popular `clean_core_classification`.
    - **Screens — estrutura interna dos `screen_NNNN.txt`:**
      - Cabeçalho `%_HEADER` (programa + número + tipo + descrição).
      - `%_FIELDS` (nome, datatype, length, row/col, label, referência a `GST_X-CAMPO`).
      - `%_FLOWLOGIC` (`PROCESS BEFORE OUTPUT` → `MODULE x`; `PROCESS AFTER INPUT` → `MODULE y`; `CALL SUBSCREEN`). Cada `MODULE` citado no flow logic vira `object_reference(reference_type='CALLS_MODULE')`.
      - `gui_title_tl_NNNN.txt` — texto do título GUI associado à screen.
    - **Tabelas em dois lugares** — mesma `ZTBCAI_DOC_A` aparece em `dictionary_table_type/` (dump global do dicionário) **e** em `Programas _e_classes/sapmz_cai_cadeia_transf/dictionary/`. **Resolvido pelo 3º nível da regra de deduplicação** (ver seção "Decisões de design"): um único `sap_object` + um único conjunto `ddic_table`/`ddic_table_field`; ambos paths registrados em `object_source` com `role` distinto (`primary` vs `dictionary_anexo`). A relação "programa usa tabela" é modelada em `object_reference`, não por duplicação.
    - **Matriz consolidada das 6 categorias:**

      | # | Diretório | Tipo de conteúdo | Estrutura física |
      |---|---|---|---|
      | 1 | `dictionary_table_struc/` | Structures, customer-includes, append structures | HTML simples por arquivo |
      | 2 | `dictionary_table_type/` | Tabelas transparentes | HTML simples por arquivo |
      | 3 | `Funções/` | Function modules + global declarations (TOP) | Pares HTML (`<fn>.html` + `global-<fn>.html`) |
      | 4 | `Mensagens/` | Message classes (T100) | HTML simples por arquivo |
      | 5 | `objetos/` | **Mesmo conteúdo da cat. 3 em TXT** (formato reduzido) | Pares TXT, deduplicado por `content_code_sha256` |
      | 6a | `Programas _e_classes/sapmz_*/` | Module pools (cada programa = 1 pasta: main na raiz + includes + `screens/` + `dictionary/`) | Hierárquica com arquivo-raiz |
      | 6b | `Programas _e_classes/zcl_*/` | Classes globais Z (cada classe = 1 pasta: **sem arquivo-raiz**; métodos em `public_methods/` / `private_methods/` / `protected_methods/` + `dictionary/`) — 308 classes, 89% com `public_methods/` | Hierárquica sem arquivo-raiz |

17. **Classes globais Z (`Programas _e_classes/zcl_*/`) — estrutura própria, diferente do module pool:**
    - **308 classes globais Z** identificadas, todas com prefixo `zcl_*`. **Unidade de ingestão = pasta** (como no module pool), mas **sem arquivo-raiz** como `sapmz_*.html` — a "cabeça" da classe não é um arquivo único; o conteúdo está organizado em **subpastas por visibilidade dos métodos**:
      ```
      zcl_<nome_classe>/
          public_methods/      ← 275/308 (89%)
          private_methods/     ← 71/308 (23%)
          protected_methods/   ← 41/308 (13%)
          dictionary/          ← 114/308 (37%) — tabelas Z usadas pela classe
          [outros raros]       ← ~6 ocorrências de subprogramas auxiliares
      ```
    - **Diferenças estruturais vs module pool** (ambos são "pasta-objeto", mas organizam diferente):

      | Aspecto | Module Pool (`sapmz_*/`) | Classe global (`zcl_*/`) |
      |---|---|---|
      | Arquivo principal na raiz | sim (`sapmz_*.html`) | **não** — definição distribuída |
      | Organização do código | includes na raiz (`zcaiinc_*.html`) | métodos em subpastas por visibilidade |
      | Telas (dynpros) | `screens/` | **nunca** (classes não têm telas) |
      | Dictionary anexo | `dictionary/` | `dictionary/` (mesmo padrão) |

    - **Implicação para o parser/ingestor:**
      - Ao detectar uma pasta `zcl_*`, o parser **não procura** arquivo-raiz; monta o objeto `class` iterando `public_methods/`, `private_methods/`, `protected_methods/` e atribuindo `visibility` a cada método pelo subdiretório onde o arquivo vive.
      - Cada `<método>.html` vira um `sap_object(object_type='METH')` + linha em `method` com FK para a classe e `visibility` preenchida.
      - `dictionary/` segue a mesma regra já definida no achado #15 (tabela como objeto único em `sap_object`, com `object_source.role='dictionary_anexo'` e relação de uso via `object_reference`).
      - Subpastas raras (subprogramas) podem ser mapeadas como `include_object` hospedadas pela classe (N:N via `include_host(host_role='class')`, já previsto).
    - **Atualizações na entidade `class`:**
      - `is_local` continua existindo (TRUE para classes locais dentro de module pools, `FALSE` para globais ZCL_).
      - Adicionada `is_global_zcl` (bool) — TRUE para classes ingeridas a partir de pasta `zcl_*/`. Redundante com `is_local=FALSE` na prática, mas explicita a origem e facilita queries.
      - Adicionadas colunas de cache: `public_method_count`, `private_method_count`, `protected_method_count`, `friends_count` — úteis para heurísticas (classe exclusivamente `public_methods` com poucos métodos frequentemente é fachada/BAPI-wrapper, sinal para Clean Core).
    - **Valor analítico** — a estrutura por visibilidade vem "grátis" do diretório e alimenta consultas que **não exigem parse do ABAP**:
      - *"quais classes públicas expõem o método X?"* → `method WHERE visibility='PUBLIC' AND name='X'`.
      - *"quais classes usam a tabela VBAK via dictionary anexo?"* → `object_source JOIN ddic_table` filtrado por `role='dictionary_anexo'`.
      - *"quais classes têm mais métodos privados que públicos?"* → indicador de coesão/encapsulamento.
      - *"classes com 100% métodos públicos"* → sinal de fachada/utilitária.

16. **ATC (`Analise_ATC/ATC_*.xlsx` + `.docx`) — análise técnica oficial da SAP já pronta:**
    - **Números consolidados do run:** 7 899 findings, **1 264 objetos únicos analisados**, **56 pacotes distintos**, **14 tipos de objeto**, **12 categorias de check**, **56 SAP Notes únicas referenciadas**. Executado em 27/04/2026 por T-SYSTEMS BASIS. Run series `ERP_S4_Z_Y` (foco em namespaces Z e Y), check variant `S4HANA_READINESS_2025_NO_FLE`.
    - **XLSX é a fonte primária** — tabela única × 20 colunas (`Priority`, `Check Title`, `Check Message`, `Object name`, `Object Type`, `Exemption State`, `Contact Person`, `Package`, `First Found On`, `Object Responsible`, `Last Changed by`, `SAP Note Number`, `Short Text`, `Referenced Application Component`, `Referenced Object Type`, `Referenced Object`, `Additional Info`, `Simplification Item Category`, `Change Category of Piecelist Items`, `Description of Change Category`, `Remarks`).
    - **DOCX é narrativo** (40 659 parágrafos com sumário + código citado por linha). Redundante com o XLSX para fim analítico; ingerido como `raw_document` só para rastreabilidade.
    - **12 categorias de check** do variant `S4HANA_READINESS_2025_NO_FLE` (contagens aproximadas observadas): *Search problematic statements for SELECT/OPEN CURSOR without ORDER BY* (2 999), *S/4HANA: Search for Usages of Simplified Objects* (2 252), *S/4HANA: Field Length Extensions* (779), *S/4HANA: Search for Database Operations* (519), *S/4HANA: Search for Simplified Transactions in Literals* (514), *Prerequisites for the test* (393), *Critical Statements* (354, Native SQL + DB Hints), *S/4HANA: Readiness Check for SAP Queries* (47), *Use of ADBC Interface* (30), *S/4HANA: Search for Base Tables of ABAP Dictionary and CDS Views* (8), *Find ABAP Statement Patterns* (1), *Scan a Program* (3). Total de 12 quando consideradas como classes distintas.
    - **Priority mapeia direto para severity**: 1=Error/blocker (2 139), 2=Warning/high (1 614), 3=Info/medium (4 146).
    - **14 `Object Type` distintos** (mais amplo que o que os HTMLs capturam): PROG (4 820), FUGR (1 816), CLAS (837), **ENHO** (133, Enhancement Implementation — BAdIs/CMOD/SMOD), FUGS (96), TABL (91), FUGX (30), **AQQU**/**AQSG** (47, SAP Query + InfoSet), VIEW (11), **SHLP** (8, Search Help), **SSFO** (7, Smart Form), **LDBA** (2, Logical Database), TTYP (1). **Indicador de cobertura:** os HTMLs só trouxeram amostras de PROG/FUGR/TABL/TTYP/STRU/MSAG — ATC sinaliza que ENHO/CLAS globais/AQQU/SHLP/SSFO/VIEW/LDBA **vão aparecer na exportação real** e o modelo precisa acomodá-los.
    - **Objetos "descobertos" pelo ATC sem arquivo de código correspondente** (ex.: `SAPFV45C`, programas SAP standard impactados) — registrados em `sap_object` com `is_discovered = TRUE` (mesmo padrão já aplicado a DTEL/DOMA).
    - **`Referenced Object Type` + `Referenced Object`** (ex.: `DTEL/WRBTR`, `DOMA/ATWRT`, `TABL/VBUK`) **é a aresta direta objeto-alvo S/4HANA-simplificado**. Substitui com qualidade superior o que um agente IA inferiria fazendo regex sobre ABAP. Permite a consulta-chave: *"todas as tabelas SAP simplificadas que nossos Z's tocam, com contagem de findings"*.
    - **`SAP Note Number`** (preenchido em ~2 043 findings, **56 notas únicas**) é entrada oficial SAP com nota + `Short Text`. Vira tabela `atc_sap_note` deduplicada com FK no finding. URL derivada: `https://launchpad.support.sap.com/#/notes/<note_number>`.
    - **Metadados que o ATC preenche e que faltavam aos HTMLs exportados**:
      - **`Package` (DEVCLASS)** — agora temos em todos os findings; viabiliza agrupamento por área de desenvolvimento (ZSD, ZMM, ZFI, ZINCORPORACAO…).
      - **`Object Responsible` / `Contact Person` / `Last Changed by`** — rastreio de autoria operacional (diferente do autor do cabeçalho `*$*$`, que é histórico).
      - **`First Found On`** — data em que o ATC detectou o problema (armazenada como data serial Excel; converter na ingestão).
      - **`Referenced Application Component`** (ex.: `SD-BF-MIG`, `CA-FLE-AMT`, `LO-MD-BP`, `CO-PA`) — permite **agrupar findings por área funcional SAP** e cruzar com o `sistema`/`projeto` do cabeçalho `*$*$`.
      - **`Change Category of Piecelist Items`** (`A`=Automatic, `T`=Technical, `F`=Functional) — indicador direto de **esforço/risco da remediação**; Functional = alto risco, Automatic = baixo.
      - **`Simplification Item Category`** (`B`/`A`/`C`/`I`/`S`/`W`) — alinhamento com o catálogo SAP oficial de Simplification Items.
    - **Impacto no papel dos agentes IA** — detecção técnica (FLE, DML, simplified objects, SELECT sem ORDER BY, Native SQL, ADBC) **sai do escopo da IA** e passa a ser consulta direta ao ATC. **A IA fica mais poderosa, não obsoleta** — deixa de produzir inferências para cruzar findings ATC com análise estrutural/funcional do código e gerar recomendações **fundamentadas em fonte oficial SAP**. Em vez de *"esse programa parece ter problemas"* a IA diz *"esse programa tem 47 findings ATC, 23 errors, vinculados a 8 SAP Notes específicas, 65% Functional"*.
    - **Papel da IA concretizado em três saídas**: (a) `object_functional_summary` (objetivo funcional de negócio — não detectável pelo ATC); (b) `clean_core_classification` (síntese Clean Core combinando findings ATC + uso estático + contexto de negócio); (c) apoio opcional na **remediação** (gerar patches ABAP a partir da SAP Note + código do objeto).
    - **Múltiplos runs ATC** — o schema precisa permitir várias execuções (antes/depois de remediação) via `atc_run.atc_run_id`. Uma nova execução **não sobrescreve** a anterior; findings de runs diferentes coexistem e os relatórios de evolução comparam counts entre runs.
    - **Relatório final — mapeamento das 6 perguntas-chave**:
      - *"Quais acessam tabelas alteradas no S/4HANA"* → `atc_finding` com `Check Title` em {Simplified Objects, Field Length Extensions, Base Tables of Views/CDS}.
      - *"Quais têm problemas de performance"* → `atc_finding` com `Check Title` em {SELECT sem ORDER BY, Critical Statements, Database Operations, ADBC}.
      - *"Quais podem quebrar no upgrade"* → `atc_finding WHERE priority = 1 AND change_category = 'F'` (Functional = quebra real de comportamento).
      - *"Quais deveriam ser eliminados"* → cruzamento `atc_finding(Functionality unavailable + SAP Note 2296016 "orphaned objects")` × `usage_indicator(inbound_refs=0)`.
      - *"Quais para arquitetura mais limpa"* → heurística combinando findings ATC + Simplification Item Category + Application Component + Change Category.
      - *"Quais ainda são usados"* → `usage_indicator` + ST03N/SCMON (quando disponíveis) — **única pergunta ainda dependente de dados externos ao ATC**.

14. **Objetos (`objetos/`) — exportação alternativa em TXT das mesmas funções de `Funções/`:**
    - Amostra inspecionada: `field_exit_auart_a.txt`, `field_exit_kdgrp_b.txt`, `field_exit_kun16_a.txt` — todos são **function modules** (FIELD_EXIT_*) em formato **.txt**, sem wrapper HTML e sem `global-*` pareado.
    - **Conteúdo ABAP idêntico** ao equivalente em `Funções/` (mesmas linhas, mesma interface, mesmo corpo). Diferença: o HTML adiciona **descrição** (`<h3> Description: Field-exit VA01`), **título canônico** no `<h2>`, **hyperlinks** `<a href="global-...">` e, no arquivo global, o **nome técnico do TOP include** (ex.: `LZSDGF_VA01TOP`) — informação que o TXT não revela.
    - **HTML = fonte canônica; TXT = fallback "code-only".** Regra de ingestão: quando ambos existem (detectado por mesmo `object_name` ou `sha256` do código normalizado), HTML prevalece e o TXT vira registro adicional em `source_file` (preservando rastreabilidade do path físico) sem duplicar `sap_object`. Objeto que só aparece em TXT é ingerido com metadados reduzidos.
    - **Normalização "code-only" também para HTMLs** — durante a ingestão do raw_document, extraímos todo conteúdo de `<div class="code">` e concatenamos em `raw_document.content_code_only` (novo campo) para alimentar parser ABAP e embeddings sem ter que reprocessar o HTML toda vez. Isso aproxima HTML e TXT no momento do parse e também serve para detectar equivalência de código entre exportações em formatos diferentes.
    - **Função-pool Z agregador** — `FIELD_EXIT_AUART` e `FIELD_EXIT_AUART_A` apontam para `FUNCTION-POOL ZSDGF_VA01`; `FIELD_EXIT_KDGRP_B` para `ZSDGF_VK12`. Confirma **N:1 function_module → function_group** (um grupo Z agrega múltiplos field exits); proibido inferir grupo pelo nome do arquivo.
    - **Confirmações adicionais a partir deste diretório:**
      - Hard-coded messages **disseminadas** — todos os 3 exemplos contêm `MESSAGE 'texto' TYPE 'E'`. `HARDCODED_MESSAGE` será um dos findings mais frequentes.
      - Field Exits **em escala** — confirmação de que há um cluster grande de candidatos automáticos a DISCONTINUE/REIMPLEMENT_EXTENSION.
      - Offset notation antiga (`input+6(10)`) ainda funciona em S/4HANA mas é candidata a modernização → novo `finding_code='LEGACY_OFFSET_SUBSTRING'`.
    - **Parser defensivo por conteúdo, não por diretório** — decisão estratégica reforçada: detectamos o tipo de objeto pela primeira instrução ABAP significativa (`FUNCTION` / `REPORT` / `CLASS` / `INCLUDE` / `INTERFACE` / `FUNCTION-POOL` / `PROGRAM` / `FORM-POOL`) em vez de assumir pelo rótulo do diretório. Se `objetos/` trouxer surpresa em produção (e.g. tabelas, estruturas, message classes), o modelo absorve sem refatoração.

13. **Mensagens (`Mensagens/`) — estrutura e entidades:**
    - Estrutura bem mais simples: `<h2>` com nome da message class (ex.: `ZA`, `Z_NEG`, `Z_ROAD_IDM_MONITOR`), `<h3>` de descrição (tipicamente vazio neste export) e bloco `<div class="code">` com linhas `<número 3 dígitos>   <texto>`.
    - **Placeholders** — `& & & & &` (sintaxe antiga, anônima) vs `&1 &2 &3` (sintaxe moderna, posicional). Parser grava ambas as contagens: `placeholder_count_unnamed` (quantos `&` soltos) e `placeholder_count_named` (quantos `&N` únicos). Estilo legado é code smell de modernização — gera `quality_finding(category='modernization', finding_code='LEGACY_MESSAGE_PLACEHOLDER')`.
    - **Mensagem 000** é template/placeholder universal — em várias classes traz apenas `& & & & &` ou `& & & &` e nunca carrega conteúdo real; parser mantém mas marca `is_template_placeholder = TRUE`.
    - **Numeração esparsa** (ex.: ZA traz 000, 106, 944–949) — o número não é sequencial; `msgnr` (3 dígitos) é a chave dentro da classe. PK composta `(message_class_id, msgnr)` já prevista.
    - **Ciclo de vida da mensagem ↔ Clean Core:** agentes IA vão cruzar:
      - mensagens declaradas × usos em programas/funções/classes ⇒ `v_mensagens_orfas` (candidatas a DISCONTINUE).
      - `MESSAGE 'texto literal' TYPE 'E'` (hard-coded) × mensagens declaradas ⇒ candidatas a MODERNIZE (substituir por `MESSAGE E001(ZA)`).
    - **Volumetria baixa** (dezenas a centenas de mensagens por classe); sem necessidade de índices especiais.
    - **Embeddings agregados por classe** (decisão adotada): o chunk embeddável é **uma classe inteira** (todas as mensagens concatenadas) com `grain='message_class_full'`. Mensagem individual isolada tem pouco sinal semântico. Isso habilita consulta tipo "encontre classes de mensagens relacionadas a autorização".

12. **Funções (`Funções/`) — estrutura e entidades:**
    - Arquivos vêm em **pares**: principal `<nome>.html` (code listing do FM) + `global-<nome>.html` (TOP include do function group com `FUNCTION-POOL`). Conectados por `<a href="global-...">` dentro do HTML.
    - **Relação N:1 Function Module → Function Group** é explícita: múltiplas funções compartilham o mesmo function pool (ex.: `FIELD_EXIT_KDGRP_A` e `FIELD_EXIT_KUNNR_V` compartilham `LZSDGF_VK12TOP`). Modelo precisa de `function_module.function_group_id`.
    - **Interface formal** em bloco `codeComment` entre `*"---`: `IMPORTING` / `EXPORTING` / `CHANGING` / `TABLES` / `EXCEPTIONS` com modo de passagem `REFERENCE(...)` ou `VALUE(...)`. Parser captura o modo — relevante para modernização (VALUE é preferido quando não há efeito colateral).
    - **Funções "esqueleto"** existem no legado (só `FUNCTION / ENDFUNCTION`). Candidatas automáticas a **DISCONTINUE**. Modelo precisa de `is_empty_implementation` e `effective_loc` (linhas excluindo comentários/vazias) em `function_module`.
    - **Field Exits são tecnologia legada** (substituída por screen exits/BAdIs). Prefixo `FIELD_EXIT_*` implica classificação Clean Core automática — flag `legacy_tech_kind` em `function_module` (valores: `FIELD_EXIT`/`USER_EXIT`/`CUSTOMER_EXIT`/`BADI_CLASSIC`/`NULL`).
    - **Referências cruzadas no código bruto** que alimentam `object_reference`: `SELECT FROM` (ex.: `TVARVC`, `ZTBSD_PARAIBA_*`), `INCLUDE` (ex.: `LZSDGF_VK12D`), `MESSAGE-ID`, `CALL FUNCTION`, `CALL METHOD`, `PERFORM`.
    - **Hard-coded strings em `MESSAGE 'texto' TYPE 'E'`** são anti-pattern i18n/manutenibilidade — geram `quality_finding(category='maintainability', finding_code='HARDCODED_MESSAGE_TEXT')`.

## Modelo de dados revisado — 3 camadas + suporte

Conforme alinhado com o usuário, o modelo é dividido em **três camadas funcionais** (RAW → STRUCT → ANALYSIS) mais embeddings e metadados de ingestão. O fluxo de trabalho em notebooks alimenta uma camada por vez.

### CAMADA A — RAW (notebook 01 de ingestão)

Objetivo: persistir **fielmente** o que há nos arquivos, sem interpretar. Permite reparse futuro sem reler disco.

- `source_file` — 1 linha por **path físico**. Colunas: `file_id`, `relative_path`, `absolute_path`, `directory_category` (um dos 6 rótulos), `file_type` (`html`/`txt`), `size_bytes`, `mtime`, `sha256`, `encoding_detected`, `ingested_at`, `parser_version`, `status`, `error_message`.
- `raw_document` — 1 linha por **conteúdo único** (deduplicado por `sha256` do arquivo completo). Colunas: `doc_id`, `sha256` (UNIQUE), `content_text` (TEXT completo já decodificado para UTF-8 — inclui o HTML/TXT original), `content_code_only` (TEXT — somente código ABAP extraído: concatenação dos `<div class="code">` para HTML, ou o próprio texto para TXT; normalizado: trim de espaços finais, line endings LF), `content_code_sha256` (UNIQUE indexado — hash do `content_code_only`; permite detectar que um HTML e um TXT carregam o **mesmo código** mesmo que o `sha256` do arquivo seja diferente), `content_html_title`, `content_h2`, `content_h3_description`, `byte_size`, `line_count`, `first_seen_at`.
- `source_file_document` — N:N entre arquivos e conteúdos (um mesmo `sha256` pode vir de vários paths). Colunas: `file_id`, `doc_id`, `preferred` (bool — TRUE para o registro considerado canônico entre formatos; HTML > TXT).

### CAMADA B — STRUCT (notebooks 02–05 de parse estruturado)

Objetivo: **entidades SAP** extraídas dos raw_documents, normalizadas.

#### B.1 Objetos SAP (entidades canônicas)

- `sap_object` — todo objeto SAP identificado (custom **ou** SAP standard referenciado pelo ATC). Colunas: `object_id`, `object_type` (PROG/CLAS/METH/FUGR/FUGS/FUGX/FUNC/INCL/FORM/MSAG/MSGE/TABL/STRU/VIEW/TTYP/DTEL/DOMA/DYNP/TITL/FIEX/**ENHO**/**AQQU**/**AQSG**/**SHLP**/**SSFO**/**LDBA**), `object_name`, `parent_object_id` (FK, ex.: método→classe; form→programa), `description`, `is_custom` (Z/Y), `is_discovered` (bool — TRUE para objetos conhecidos apenas por referência, ex.: objetos SAP standard citados pelo ATC ou DTEL/DOMA descobertos via `ddic_table_field`), `namespace_prefix`, `package`, UNIQUE(`object_type`, `object_name`).
- `object_source` — N:N entre objetos e os `raw_document`s que os descrevem. `object_id`, `doc_id`, `role` (primary/included/dictionary_anexo/screen_anexo).

#### B.2 Cabeçalho documental ABAP (metadados `*$*$`)

- `abap_header_meta` — 1 linha por objeto com cabeçalho parseado. Colunas: `object_id`, `autor_original`, `analista`, `data_criacao`, `projeto`, `sistema` (alias `business_system` — usado para agrupamento funcional), `finalidade`, `observacoes`, `raw_header_text`, `modification_count` (cache derivado de `abap_header_change` — proxy de atividade/criticidade), `age_years` (cache derivado: hoje − `data_criacao`). Índices em `sistema` e `autor_original` para consultas de relatório.
- `abap_header_change` — histórico de modificações do cabeçalho (N por objeto). Colunas: `object_id`, `data_mod`, `autor_mod`, `rdm`, `descricao_mod`, `ordem`.

#### B.3 Código ABAP (programas, classes, funções, includes, forms)

- `program` — atributos extras de programa: `object_id` (FK), `program_type` (report / module_pool / include / subroutine_pool / function_pool / …), `main_include_name`, `uses_message_class`, `dynpro_count` (cache — nº de screens associadas; sinal forte para Clean Core REIMPLEMENT_EXTENSION), `include_count` (cache), `form_count` (cache), `has_local_classes` (bool — TRUE quando há include `*clas01` ou similar com `CLASS ... DEFINITION` local).
- `class` — `object_id` (FK), `is_local` (bool — TRUE para classes definidas dentro de module pools; FALSE para classes globais SE24), `is_global_zcl` (bool — TRUE quando ingerida a partir de pasta `zcl_*/` no dump; redundante com `is_local=FALSE` na prática, explicita origem), `host_program_id` (FK → `program`, nullable — só preenchido quando `is_local=TRUE`), `is_exception` (detectado por prefixo ZCX_), `abstract`, `final`, `superclass_name`, `interfaces` (JSON), `friends` (JSON), `public_method_count` (cache), `private_method_count` (cache), `protected_method_count` (cache).
- `method` — `object_id` (FK), `class_object_id` (FK), `visibility` (**PUBLIC/PRIVATE/PROTECTED** — derivada do subdiretório `public_methods/`/`private_methods/`/`protected_methods/` ao ingerir pastas `zcl_*/`, ou do parse do `CLASS ... DEFINITION` para classes locais), `is_static`, `is_abstract`, `signature_raw`.
- `function_group` — `object_id` (FK), `top_include_name` (ex.: `LZSDGF_VK12TOP`), `message_class_assoc`.
- `function_module` — `object_id` (FK), `function_group_id` (FK — **N:1 explícita**), `is_rfc`, `is_remote_callable`, `short_text`, `signature_raw_block`, `is_empty_implementation` (bool — corpo só `FUNCTION/ENDFUNCTION`), `effective_loc` (INTEGER — linhas excluindo comentários/vazias), `legacy_tech_kind` (nullable: `FIELD_EXIT` / `USER_EXIT` / `CUSTOMER_EXIT` / `BADI_CLASSIC` / `NULL`) — derivado do prefixo/nome e usado como hint automático para Clean Core.
- `function_parameter` — assinatura parseada do FM. Colunas: `function_module_id`, `param_kind` (IMPORTING/EXPORTING/CHANGING/TABLES/EXCEPTIONS), `param_name`, `param_type`, `passing_mode` (`REFERENCE`/`VALUE`/`NULL` para TABLES/EXCEPTIONS), `param_default`, `is_optional`, `position`.
- `include_object` — include ABAP (reutilizável por programas, function groups e classes). Colunas: `object_id` (FK), `include_kind` (`TOP` / `PBO_O01` / `PAI_I01` / `FORM_F01` / `CLASS_CLAS01` / `DEFINITIONS` / `GENERIC`), `inferred_name_pattern`. **N:N com hosts** via `include_host` (abaixo).
- `include_host` — N:N entre includes e seus hosts (um mesmo include pode ser reutilizado por múltiplos programas/grupos/classes). Colunas: `include_id` (FK → `include_object.object_id`), `host_object_id` (FK → `sap_object`), `host_role` (program/function_group/class).
- `form_routine` — `object_id` (FK), `host_object_id` (FK — programa/include), `signature_raw`.

#### B.4 Dicionário de dados (DDIC)

Observação do usuário (2026-04-30): **Data Elements e Domains são entidades de primeira classe** — reutilizáveis entre múltiplas estruturas/tabelas — e **Domain Values fixos** formam uma tabela filha própria. O modelo cria registros "descobertos" para cada nome único que apareça em qualquer `ddic_table_field`, mesmo que o objeto não tenha arquivo próprio (marcados `is_discovered = TRUE`). Isso mantém integridade referencial e permite enriquecer depois.

- `ddic_table` — **tabela unificada** para todo objeto de dicionário com estrutura de campos (tabelas transparentes, estruturas, customer-includes, append structures, views). Colunas: `object_id` (FK), `object_kind` (**discriminador** — `TABLE` / `STRUCTURE` / `CUSTOMER_INCLUDE` / `APPEND_STRUCTURE` / `POOL` / `CLUSTER` / `VIEW` / `CDS`), `ddic_subtype` (`CI_*` / `Z_NAMESPACE` / `Y_NAMESPACE` / `STANDARD` — derivado do prefixo do nome), `is_client_dependent` (TRUE se primeiro campo = `MANDT` + `Key=X`), `delivery_class`, `description`, `source_directory_hint` (qual diretório trouxe o arquivo — apenas hint, não verdade). `object_kind` é inferido pelo conteúdo (MANDT+Key=X ⇒ TABLE; prefixo CI_ ⇒ CUSTOMER_INCLUDE; título "Table Type" ⇒ atende a `ddic_table_type` e não entra aqui; etc.).
- `ddic_table_field` — campos parseados. Colunas: `table_id` (FK → `ddic_table`), `position`, `field_name`, `is_key`, `data_element_id` (FK → `ddic_data_element`, **nullable**), `domain_id` (FK → `ddic_domain`, **nullable**), `datatype` (texto livre — aceita todo datatype ABAP: CHAR, NUMC, CLNT, CURR, QUAN, DEC, INT1/2/4/8, FLTP, DATS, TIMS, RAW, LRAW, STRG, TTYP, …), `length`, `lowercase`, `domain_text` (descrição exibida no export — preservada mesmo quando não há domínio formal, pois carrega a semântica do campo).
- `ddic_data_element` — elemento de dados (reutilizável). Colunas: `object_id` (FK → `sap_object`), `name` (UNIQUE), `is_custom`, `is_discovered` (TRUE = só visto via referência; FALSE = tem arquivo fonte), `description`.
- `ddic_domain` — domínio (reutilizável). Colunas: `object_id` (FK), `name` (UNIQUE), `is_custom`, `is_discovered`, `datatype`, `length`, `decimals`, `description`.
- `ddic_domain_fixed_value` — valores fixos permitidos por domínio (bloco "Fixed Domain Values" quando presente). Colunas: `domain_id` (FK), `position`, `value_low`, `value_high` (nullable — intervalos), `text`.
- `ddic_table_type` — entradas de listas "Table Type". Colunas: `object_id` (FK), `row_type_name`, `category` (range / general), `range_elem_type`, `referenced_object_type`, `initial_lines`, `description`.

**Regra de ingestão DDIC:** ao parsear um `ddic_table_field`, se `data_element` ou `domain` ainda não existem, **insere-se** em `ddic_data_element` / `ddic_domain` com `is_discovered = TRUE`. Quando um arquivo próprio desses objetos for ingerido depois, faz-se UPSERT enriquecendo (datatype, length, decimals, description) e marcando `is_discovered = FALSE`.

#### B.5 Mensagens

- `message_class` — `object_id` (FK → `sap_object`), `short_text`, `message_count` (cache derivado). UNIQUE via `sap_object(object_type='MSAG', object_name)`.
- `message` — uma linha por mensagem. **PK composta** `(message_class_id, msgnr)`. Colunas: `message_class_id` (FK), `msgnr` (CHAR(3) — aceita '000'–'999' preservando zeros à esquerda), `msg_text` (texto com placeholders preservados), `placeholder_count_unnamed` (quantos `&` soltos), `placeholder_count_named` (quantos `&N` distintos, usando max do N), `uses_legacy_placeholder_style` (bool — TRUE quando só há `&` anônimos), `is_template_placeholder` (bool — TRUE para mensagens só com placeholders e sem texto, tipicamente a 000), `inferred_type` (E/W/I/A/S — nullable; só preenchido quando agente IA cruzar uso em `MESSAGE ... TYPE '...'`).

#### B.6 Screens (dynpros)

- `dynpro_screen` — `object_id` (FK do programa host), `screen_number`, `screen_type` (normal/subscreen/modal…), `next_screen`, `description`.
- `dynpro_field` — 1 linha por `%_FIELDS` do screen txt. Colunas: `screen_id`, `field_name`, `datatype`, `length`, `row`, `col`, `is_input`, `is_output`, `source_table_field` (se usar `GST_X-CAMPO`).
- `dynpro_flowlogic` — bloco `%_FLOWLOGIC` inteiro (texto bruto) + parse mínimo de `MODULE`/`CALL SUBSCREEN` como referências (vai para `object_reference`).
- `gui_title` — `object_id`, `title_code`, `title_text`.

#### B.7 Relacionamentos (grafo de dependências)

- `object_reference` — **entidade genérica** que captura toda dependência detectada no código (tabela, função, include, classe, message class, data element, domain, FORM, BAdI). É alimentada em duas passadas: (1) parser simples (regex + `<a href>` dos HTMLs) na camada STRUCT; (2) enriquecimento pelos agentes de IA na camada ANALYSIS (resolução de nomes ambíguos, inferência de semântica). Colunas: `ref_id`, `source_object_id`, `source_location` (ex.: "FORM documento_aberto_ler linha 123"), `target_object_type_hint` (TABL/FUNC/CLAS/INCL/MSAG/DTEL/DOMA/TTYP/STRU/FORM/BADI), `target_object_name`, `target_object_id` (nullable — só preenchido após resolução), `reference_type` (CALL_FUNCTION / PERFORM / INCLUDE / SUBMIT / INHERITS / IMPLEMENTS / USES_CLASS / CALL_METHOD / SELECT_FROM / INSERT_INTO / UPDATE / MODIFY / DELETE_FROM / MESSAGE_ID / USES_MESSAGE / USES_DATA_ELEMENT / USES_DOMAIN / USES_TTYP / USES_STRUCTURE / USES_FIELD_EXIT / HARDCODED_MESSAGE / CALLS_MODULE / CALL_SUBSCREEN / USES_GUI_TITLE / **ATC_REFERENCES_SIMPLIFIED_OBJECT**), `via_html_link` (bool — veio de `<a href>` ou de regex), `raw_snippet`, `resolution_status` (`unresolved` / `resolved` / `ambiguous` / `external`).
- `table_access` — view materializada (ou tabela derivada) de `object_reference` onde `reference_type` ∈ operações DML/SELECT, para consultas rápidas do tipo "quem lê VBAK?".

### CAMADA F — ATC External Analysis (notebook 06, ingerido antes da ANALYSIS)

Objetivo: persistir **como verdade primária** o resultado oficial do ATC (check variant S/4HANA Readiness). Esta camada **precede** a ANALYSIS da IA e a alimenta. Estrutura comporta **múltiplas execuções** (novos runs do ATC antes/depois de remediação) coexistindo no banco para comparação temporal.

- `atc_run` — metadados da execução. Colunas: `atc_run_id`, `run_label` (ex.: `ATC_20260427_ZandY_141515`), `check_variant` (`S4HANA_READINESS_2025_NO_FLE`), `run_series` (`ERP_S4_Z_Y`), `run_date`, `executed_by` (`T-SYSTEMS BASIS`), `system_id`, `total_findings`, `total_errors`, `total_warnings`, `total_info`, `total_objects_unique` (ex.: 1 264), `total_packages` (ex.: 56), `total_object_types` (ex.: 14), `total_checks` (ex.: 12), `total_sap_notes` (ex.: 56), `source_xlsx_doc_id` (FK → `raw_document`), `source_docx_doc_id` (FK → `raw_document`, nullable), `imported_at`, `is_current` (bool — último run vigente).
- `atc_check` — catálogo das categorias de check. Colunas: `check_id`, `check_title` (UNIQUE), `check_class` (ex.: `CL_CI_TEST_SEARCH_ABAP_PATTERN`), `check_category` (`PERFORMANCE` / `S4HANA_COMPAT` / `CRITICAL_STMT` / `READINESS` / `SYNTAX`), `default_priority`, `default_recommended_action` (`PERFORMANCE_FIX` / `ADAPT_FOR_S4` / `REWRITE` / `EVALUATE`), `description`.
- `atc_sap_note` — catálogo de SAP Notes referenciadas (56 únicas no run inicial, expansível). Colunas: `note_id`, `note_number` (UNIQUE ex.: `2610650`), `short_text` (ex.: *Amount Field Length Extension: Code Adaptations*), `application_component` (ex.: `CA-FLE-AMT`), `url` (derivado: `https://launchpad.support.sap.com/#/notes/<note_number>`), `first_seen_at`, `is_orphan_objects_note` (bool — TRUE para nota `2296016` *removal of orphaned objects*; ajuda na view de candidatos a eliminar).
- `atc_simplification_item_category` — catálogo normalizado das 6 categorias SAP (`I`, `W`, `B`, `S`, `A`, `C`). Colunas: `code` (PK, CHAR(1)), `label`, `description`. Pré-seed: `I`=Information, `W`=Warning, `B`=Blocker, `S`=Structural, `A`=Automatic, `C`=Compatible (labels a confirmar com doc oficial SAP).
- `atc_change_category` — catálogo normalizado das categorias de mudança (`A`, `T`, `F`). Colunas: `code` (PK, CHAR(1)), `label`, `description`, `effort_level` (low/medium/high), `risk_level` (low/medium/high). Pré-seed: `A`=Automatic (effort=low, risk=low), `T`=Technical (effort=medium, risk=medium), `F`=Functional (effort=high, risk=high).
- `atc_application_component` — catálogo derivado dos `Referenced Application Component` únicos (ex.: `SD-BF-MIG`, `CA-FLE-AMT`, `LO-MD-BP`, `CO-PA`). Colunas: `component_id`, `component_code` (UNIQUE), `module` (derivado: SD / MM / FI / CA / CO / …), `area` (resto do código após o módulo).
- `atc_finding` — **1 linha por finding do XLSX**. Colunas:
  - `finding_id`
  - `atc_run_id` (FK → `atc_run`)
  - `check_id` (FK → `atc_check`)
  - `priority` (1/2/3)
  - `check_message` (mensagem específica do finding, pode ser diferente do título)
  - `source_object_id` (FK → `sap_object` — o objeto que tem o problema; se não existir nos nossos HTMLs, `sap_object` é inserido com `is_discovered=TRUE`)
  - `source_object_name_raw` (preservado — útil quando `source_object_id` é nullable ambíguo)
  - `source_object_type_raw` (PROG/FUGR/CLAS/ENHO/…)
  - `package` (DEVCLASS)
  - `object_responsible`, `last_changed_by`, `contact_person`
  - `first_found_on` (data convertida; chegada como número serial Excel)
  - `sap_note_id` (FK → `atc_sap_note`, nullable)
  - `short_text` (cache de `atc_sap_note.short_text`)
  - `application_component_id` (FK → `atc_application_component`, nullable)
  - `referenced_object_type` (ex.: `TABL` / `DTEL` / `DOMA`)
  - `referenced_object_name` (ex.: `VBUK` / `WRBTR` / `ATWRT`)
  - `referenced_object_id` (FK → `sap_object`, nullable — resolvido quando o referenced_object existe localmente)
  - `simplification_item_category_code` (FK → `atc_simplification_item_category.code`, nullable)
  - `change_category_code` (FK → `atc_change_category.code`, nullable)
  - `change_category_description` (texto livre do XLSX — ex.: `Not specified`, `Technical`, `Functional`)
  - `exemption_state` (ex.: `APPROVED` / `PENDING` / NULL)
  - `additional_info`, `remarks`
  - `location_line` (extraída do `Check Message` ou do DOCX quando disponível, nullable)
  - `row_index_in_xlsx` (auditoria)
  - Índices: `(atc_run_id, source_object_id)`, `(atc_run_id, referenced_object_id)`, `(check_id, priority)`, `(referenced_object_name)`, `(sap_note_id)`, `(package)`, `(application_component_id)`, `(change_category_code)`.
- **Integração com `object_reference`** — cada `atc_finding` com `referenced_object_*` preenchido gera automaticamente um `object_reference` com `reference_type='ATC_REFERENCES_SIMPLIFIED_OBJECT'`, `via_html_link=FALSE`, `resolution_status='resolved'`, `raw_snippet` apontando para o finding. Isso coloca o ATC no **mesmo grafo** que o parser ABAP, permitindo queries unificadas do tipo *"quem acessa VBUK (direto no código OU detectado pelo ATC)"*.
- **Integração com `analysis_run`** — a importação do XLSX cria um registro em `analysis_run` com `run_type='atc_import'`, `agent_name='SAP_ATC'`, `model_name='S4HANA_READINESS_2025_NO_FLE'`, vinculando o run ATC como entrada da camada ANALYSIS.

### CAMADA C — ANALYSIS (notebooks 06–08 de LLM e regras)

Objetivo: **síntese e decisão** derivadas sobre cada objeto, combinando (a) estrutura parseada da STRUCT, (b) achados oficiais da Camada F (ATC) e (c) heurísticas/LLMs. **A detecção técnica foi movida para a Camada F** — os agentes IA **consomem** o ATC em vez de duplicar o trabalho. Tudo aqui é reprocessável/versionável.

**Reposicionamento do papel da IA:**
- **O que a IA faz:** inferir `object_functional_summary` (propósito de negócio do objeto — não detectável pelo ATC), sintetizar `clean_core_classification` combinando evidências ATC + grafo + metadados de cabeçalho, gerar sugestões de remediação a partir da SAP Note + código.
- **O que a IA não faz mais:** detectar SELECT sem ORDER BY, uso de tabelas simplificadas, FLE, Native SQL, ADBC — tudo isso já vem do ATC.

- `analysis_run` — cada execução de um agente, regra ou importação externa. Colunas: `run_id`, `run_type` (`atc_import` / `llm_functional_summary` / `llm_clean_core_classifier` / `rule_header_metadata` / `rule_legacy_tech` / `manual_review`), `agent_name`, `model_name`, `model_version`, `prompt_version`, `ruleset_version`, `started_at`, `finished_at`, `input_scope` (JSON), `status`, `notes`.
- `object_functional_summary` — "objetivo funcional" do objeto (principal output do agente de IA). Colunas: `object_id`, `run_id`, `summary_short` (1 parágrafo), `summary_detailed` (markdown), `business_domain` (FI/SD/MM/PM/LE/QM/CO/PS/…), `functional_keywords` (JSON array), `inputs_described` (JSON), `outputs_described` (JSON), `external_systems` (JSON — ex. Salesforce, Finnet, SIVA), `confidence`, `created_at`. UNIQUE(`object_id`, `run_id`).
- `s4hana_impact` — **visão consolidada de impactos técnicos por objeto**, derivada majoritariamente de `atc_finding` + eventuais regras complementares. Colunas: `finding_id` (PK interna), `object_id`, `run_id`, `source` (`atc` / `rule` / `ai`), `atc_finding_id` (FK → `atc_finding`, nullable quando `source != 'atc'`), `affected_object_type`, `affected_object_name`, `impact_category` (`simplification_list` / `signature_changed` / `removed_api` / `deprecated_statement` / `cds_alternative_exists` / `field_length_extension` / `native_sql` / `db_hint` / `adbc` / `select_no_order_by`), `severity` (derivada de priority ATC: 1→blocker, 2→high, 3→medium), `recommendation` (derivada de `atc_sap_note.short_text` ou gerada), `evidence_reference_id` (FK opcional para `object_reference`). **Para findings ATC isso é uma projeção 1:1; campos são `NOT NULL` quando `source='atc'`.**
- `quality_finding` — qualidade/performance/segurança **além** do que o ATC cobre. Colunas: `finding_id`, `object_id`, `run_id`, `category` (performance / security / maintainability / modernization), `finding_code`, `severity`, `location_text`, `message`, `suggestion`. **Finding codes previstos próprios da nossa análise** (complementares ao ATC): `HARDCODED_MESSAGE_TEXT` / `LEGACY_MESSAGE_PLACEHOLDER` / `LEGACY_OFFSET_SUBSTRING` / `EMPTY_FUNCTION_BODY` / `USES_FIELD_EXIT_TECH` / `HIGH_DYNPRO_COUNT` / `ORPHAN_MESSAGE` / `UNUSED_OBJECT_NO_INBOUND_REFS`.
- `clean_core_classification` — veredito final por objeto (última classificação prevalece via `is_current`). Colunas: `classification_id`, `object_id`, `run_id`, `classification` (DISCONTINUE / REMEDIATE / MODERNIZE / REPLACE_BY_STANDARD / REIMPLEMENT_EXTENSION / KEEP_AS_IS), `rationale` (texto combinando evidências: *"2 findings Priority=1 do ATC em simplified objects + 0 referências de entrada + classe tecnológica FIELD_EXIT → DISCONTINUE ou REIMPLEMENT_EXTENSION"*), `confidence`, `set_by` (rule/agent/human), `is_current` (bool), `set_at`.
- `usage_indicator` — indicadores de uso (inicialmente só análise estática: "referenciado por N objetos", "é transação?", "tem entrypoint?"). Campos opcionais para futura ingestão de ST03N/SCMON/UPL (`last_execution`, `exec_count_90d`, `user_count_90d`, `source`).
- `report_view` *(views SQL, não tabelas)* — consultas nomeadas que montam o relatório final. **Várias agora são triviais sobre `atc_finding`:**
  - `v_programas_em_uso` — derivada de `object_reference` (tem inbound refs) + usage_indicator.
  - `v_acessos_a_tabelas_alteradas_s4` — `SELECT ... FROM atc_finding JOIN atc_check WHERE check_title IN ('S/4HANA: Search for Usages of Simplified Objects', 'S/4HANA: Field Length Extensions', 'S/4HANA: Search for Base Tables of ABAP Dictionary and CDS Views')`.
  - `v_problemas_performance` — `atc_finding` em `check_title IN ('Search problematic statements...ORDER BY', 'Critical Statements', 'S/4HANA: Search for Database Operations', 'Use of ADBC Interface')`.
  - `v_riscos_upgrade` — `atc_finding WHERE priority = 1` agrupado por objeto.
  - `v_candidatos_descontinuar` — join `sap_object` × `object_reference` (zero inbound) × `atc_finding` (total findings) — objetos sem uso + com findings críticos.
  - `v_candidatos_clean_core_side_by_side` — heurística combinada: `dynpro_count > N` OR `legacy_tech_kind IS NOT NULL` OR classificado `REIMPLEMENT_EXTENSION`.
  - `v_mensagens_orfas`.
  - `v_hardcoded_messages`.
  - `v_findings_por_sap_note` — `atc_finding` agrupado por `sap_note_id` — dá a **lista de SAP Notes mais frequentes** no ambiente (vetor de esforço de remediação).
  - `v_findings_por_simplified_object` — `atc_finding` agrupado por `referenced_object_name` — mostra **quais tabelas simplificadas S/4** impactam **mais objetos custom** (priorização de migração de dados).
  - `v_findings_por_package` — distribuição de findings por package (ZSD, ZMM, ZFI, ZINCORPORACAO…), para priorização por área de desenvolvimento.
  - `v_findings_por_application_component` — distribuição por `atc_application_component` (SD-BF-MIG, CA-FLE-AMT, LO-MD-BP, CO-PA…) cruzada com `abap_header_meta.sistema` — **alinha área técnica SAP com área funcional declarada pelos autores**.
  - `v_findings_por_change_category` — contagem de findings por `A`/`T`/`F` e por objeto — **proxy de esforço total de remediação**.
  - `v_evolucao_findings_entre_runs` — comparação entre `atc_run`s (antes/depois). Colunas: objeto, check, run_before, run_after, delta_priority1, delta_priority2, delta_priority3.
  - `v_classes_fachada` — classes globais com 100% de métodos públicos (candidatas a simples wrapper/BAPI → avaliar substituição por standard) a partir de `public_method_count`/`private_method_count`/`protected_method_count`.
  - `v_classes_publicas_metodo` — busca inversa: para um método de nome `X`, listar todas as classes globais que o expõem publicamente (sem parse de ABAP).

### CAMADA D — Embeddings e RAG (notebook 07)

**Modelo primário: `BAAI/bge-m3` executado localmente**, dimensão 1024. Razões consolidadas:
- **Privacidade** — código do cliente nunca sai do ambiente T-Systems; requisito típico de cliente corporativo como Copa Energia. Ambiente com proxy corporativo pode ter restrições a chamadas externas.
- **Multilingual nativo** — bge-m3 tem suporte forte a português, melhor que muitas alternativas open-source. Crítico porque os cabeçalhos `*$*$`, `finalidade`, comentários de código e `abap_header_change.descricao_mod` estão em PT-BR.
- **Reprodutibilidade/auditoria** — projeto pode ser re-executado sem dependência de API; resultados determinísticos para a mesma versão do modelo.
- **Zero custo recorrente** — uma passagem de embedding cobre todo o dataset.
- **1024 dimensões** — equilíbrio qualidade × tamanho no SQLite (~4KB/vetor em float32; ~2KB em float16 se o sqlite-vec suportar quantização).

Execução: via `FlagEmbedding.BGEM3FlagModel` ou `sentence-transformers` — decisão de biblioteca diferida para o notebook 07. Cache local do modelo em `~/.cache/huggingface/` ou em disco do projeto para offline.

- `embedding_model` — catálogo. Colunas: `model_id`, `model_name` (ex.: `BAAI/bge-m3`), `provider` (`local_sentence_transformers` / `local_flag_embedding` / `openai` / `voyage` / …), `dimension`, `model_revision` (commit hash HF para reprodutibilidade), `library_version`, `created_at`. Pré-seed com `BAAI/bge-m3` como registro inicial.
- `chunk` — unidade embeddável. Colunas: `chunk_id`, `object_id` (FK), `doc_id` (FK — qual raw_document foi chunkado), `grain` (object_full / header_meta / method / form / function_signature / functional_summary / **message_class_full**), `sub_index` (ordem do chunk dentro do grão), `start_line`, `end_line`, `content_text`, `content_hash`, `token_count`, `created_at`. **Para `grain='message_class_full'`** o `content_text` é a concatenação "msgnr texto\nmsgnr texto\n…" de todas as mensagens da classe — sem incluir a 000 template.
- `chunk_embedding_1024` — tabela virtual `vec0` do sqlite-vec para bge-m3. Colunas: `chunk_id`, `model_id`, `embedding float[1024]`. Outras dimensões (caso um segundo modelo seja adicionado) ganham suas próprias tabelas (`chunk_embedding_<N>`).
- **Estratégia de chunking recomendada** (a confirmar no notebook 07):
  - Contexto máximo do bge-m3: 8192 tokens → cabe um objeto inteiro ABAP de tamanho médio.
  - Priorizar embeddar: (a) `object_functional_summary` (grain=`functional_summary` — mais curto e semântico, output da IA); (b) cabeçalho `*$*$` (grain=`header_meta` — PT-BR rico); (c) assinatura de function_module (grain=`function_signature`); (d) `message_class_full` (grain=`message_class_full`); (e) `object_full` só para objetos selecionados onde a recuperação por código cru agrega valor.
  - Código completo (grain=`object_full`) só é embeddado sob demanda, não por default — muitos objetos grandes gerariam índice inflado sem ganho proporcional.
- **Custo computacional esperado** — ordem de 10k–50k chunks no total; bge-m3 em CPU roda ~50 chunks/s e em GPU ~500 chunks/s. Indexação inicial é tarefa de minutos a poucas horas, não dias.

### CAMADA E — Metadados de ingestão/processamento

- `ingestion_run` — `run_id`, `phase` (`raw_ingest` / `struct_parse` / `atc_import` / `analysis_llm` / `embeddings`), `started_at`, `finished_at`, `files_total`, `files_ok`, `files_failed`, `parser_version`, `notes`.
- `ingestion_error` — `error_id`, `run_id`, `file_id` (nullable), `object_id` (nullable), `stage`, `error_type`, `error_message`, `traceback`.

## Decisões de design

- **IDs internos** `INTEGER PRIMARY KEY`; UNIQUE nos identificadores naturais SAP (`object_type + object_name`, `sha256`).
- **Separação RAW vs STRUCT** — conteúdo original **nunca** é descartado; o parse é derivado e regenerável. Reparse não exige releitura de disco.
- **Deduplicação em três níveis** (um arquivo/conteúdo/objeto pode aparecer em múltiplos lugares; tudo é unificado):
  1. **Arquivo** (`source_file` ↔ `raw_document`) por `sha256` do arquivo completo — mesmo arquivo em N paths = 1 `raw_document`.
  2. **Código** (`raw_document.content_code_sha256`) — **mesmo código em formatos diferentes** (HTML canônico de `Funções/` vs TXT de `objetos/`) = detectado e vinculado ao mesmo `sap_object`; o registro HTML fica como `preferred=TRUE` em `source_file_document`.
  3. **Objeto SAP** (`sap_object(object_type, object_name)` UNIQUE) — **uma tabela/classe/programa/function é uma só no SAP**, então é uma só no banco, independentemente de quantos arquivos/diretórios a descrevam. Auditoria preservada pela cadeia `object_source → source_file_document → source_file`.

  **Exemplo canônico — `ZTBCAI_DOC_A`**: tabela que aparece em dois lugares distintos da exportação — (a) `abaps/dictionary_table_type/ztbcai_doc_a.html` (dump global do dicionário) e (b) `abaps/Programas _e_classes/sapmz_cai_cadeia_transf/dictionary/ztbcai_doc_a.html` (dicionário anexo ao programa que a usa). **Regra aplicada:**
  - Um único registro em `sap_object` (`object_type='TABL'`, `object_name='ZTBCAI_DOC_A'`).
  - Um único conjunto de `ddic_table` + `ddic_table_field` (a estrutura da tabela no SAP é única).
  - `object_source` recebe **duas linhas** ligando o mesmo `object_id` aos dois `doc_id`s, com `role` discriminado (`primary` para o dump global, `dictionary_anexo` para o anexado ao programa). Se os dois arquivos tiverem `sha256` idêntico, eles compartilham o mesmo `doc_id` e a deduplicação já ocorre no nível 1; se diferirem por whitespace/encoding, são dois `doc_id`s distintos mas apontam para o mesmo `sap_object`.
  - A relação "programa `SAPMZ_CAI_CADEIA_TRANSF` usa a tabela `ZTBCAI_DOC_A`" **não** depende de duplicar a tabela; vai como `object_reference(source=programa, target=tabela, reference_type='SELECT_FROM'|'USES_STRUCTURE')`, derivado do fato de a tabela estar no `dictionary/` do programa e/ou de acesso SQL no código.
  - Consultas como *"quantas tabelas Z existem?"* contam 1, não 2. Consulta *"de onde veio esse registro?"* responde via `object_source` com os dois paths.
- **Encoding** — arquivos são ISO-8859-1; parser decodifica e **armazena UTF-8** em `content_text`. Guardar `encoding_detected` para auditoria.
- **Timestamps** em UTC ISO-8601.
- **`PRAGMA foreign_keys = ON`** habilitado.
- **Múltiplos resultados de análise coexistem** via `run_id` — permite comparar outputs de diferentes versões de prompt/modelo. Campo `is_current` em `clean_core_classification` marca o vigente.
- **sqlite-vec com dimensão fixa** — uma virtual table por dimensão. Dimensão primária **1024** (bge-m3); nomenclatura `chunk_embedding_1024`. Outras dimensões podem ser adicionadas sob demanda.
- **Embedding local, nunca API externa** — `BAAI/bge-m3` local (dim 1024) é o modelo primário por razões de privacidade, reprodutibilidade e custo. `model_revision` (commit HF) persistido para auditoria/reprodutibilidade.
- **Índices essenciais**: `source_file(sha256)`, `raw_document(sha256)`, `raw_document(content_code_sha256)`, `sap_object(object_type, object_name)`, `sap_object(is_discovered)`, `object_reference(source_object_id)`, `object_reference(target_object_id)`, `object_reference(target_object_name)`, `ddic_table_field(table_id)`, `chunk(object_id)`, `clean_core_classification(object_id, is_current)`, `atc_finding(atc_run_id, source_object_id)`, `atc_finding(atc_run_id, referenced_object_id)`, `atc_finding(check_id, priority)`, `atc_finding(referenced_object_name)`, `atc_finding(sap_note_id)`, `atc_finding(package)`, `atc_finding(application_component_id)`, `atc_finding(change_category_code)`, `atc_run(is_current)`.
- **Views nomeadas** (`v_*`) para cada pergunta do relatório final — o notebook final apenas formata o output dessas views. Por default, as views filtram `atc_run.is_current = TRUE`.
- **ATC como verdade primária para detecção técnica** — camada F é ingerida antes da ANALYSIS e os agentes IA consumem seus findings. **Múltiplos `atc_run`s coexistem** para comparação de evolução (antes/depois de remediação); flag `is_current` marca o run vigente.

## Arquivos críticos para a próxima iteração

Serão definidos após receber as amostras. O DDL SQL final ficará em:
- `C:\_Adriano\ClaudeCode\SapCleanCore\db\schema.sql` *(a criar)*
- `C:\_Adriano\ClaudeCode\SapCleanCore\db\seed_reference_data.sql` *(a criar — enums de `object_type`, `reference_type`, `impact_category`, `classification`)*

Notebooks serão separados por tarefa:
- `notebooks/01_ingestao_raw.ipynb` (raw_document, source_file — dos 6 diretórios de `abaps/` + XLSX/DOCX do ATC)
- `notebooks/02_parse_dicionario.ipynb` (DDIC: tables, structures, data elements, domains, domain values, table types)
- `notebooks/03_parse_programas_classes.ipynb` (programas, classes, métodos, forms, includes, screens, GUI titles, cabeçalhos `*$*$`)
- `notebooks/04_parse_funcoes_mensagens.ipynb` (function groups, function modules, parameters, message classes, messages)
- `notebooks/05_grafo_dependencias.ipynb` (popular `object_reference` — parser + links HTML)
- **`notebooks/06_ingestao_atc.ipynb`** (nova — ler XLSX ATC, popular camada F, resolver `source_object_id` e `referenced_object_id`, emitir `object_reference` tipo `ATC_REFERENCES_SIMPLIFIED_OBJECT`)
- `notebooks/07_embeddings.ipynb` (chunks + vetorização multi-grão)
- `notebooks/08_analise_funcional_llm.ipynb` (objetos funcionais com LLM — `object_functional_summary`)
- `notebooks/09_clean_core_classificacao.ipynb` (regras + LLM combinando ATC + grafo + metadados)
- `notebooks/10_relatorio_final.ipynb` (consome `v_*`)

(Apenas referência — notebooks não serão criados nesta fase.)

## Diferenças entre o plano e o documento de Entrega 1 (`docs/modelagem_conceitual.md`)

A versão formal em `docs/` introduziu **naming conventions e entidades diferentes** do que este plano vinha modelando. A implementação do DDL (Entrega 2) seguirá o documento formal. Mapeamento explícito:

### Nomes de tabela renomeados (plano → documento formal)

| Plano interno | Entrega 1 (formal) | Observação |
|---|---|---|
| `sap_object` | **`code_object`** | Nome mais alinhado com literatura de análise de código |
| `ddic_table` + `ddic_table_field` | **`code_object(type in {TABL,STRU,TTYP})`** + **`table_field`** | DDIC absorvido no `code_object` via discriminator, só `table_field` permanece como filha |
| `ddic_data_element` | **`code_object(type='DTEL')`** | Absorvido no `code_object` |
| `ddic_domain` + `ddic_domain_fixed_value` | **`domain`** + **`domain_value`** | Mantidas como entidades próprias (fora do `code_object`) por serem referenciadas de forma relacional |
| `message_class` + `message` | **`code_object(type='MSAG')`** + **`message`** | Classe absorvida; entidade `message` permanece filha |
| `abap_header_meta` + `abap_header_change` | **`object_header_metadata`** + **`modification_history`** | Campos renomeados em PT-EN mais claro (`autor_original` → `author_original`, etc.) |
| `class` + `method` + `class_attribute` | **`code_object(type='CLAS')`** + **`class_attribute`** + **`class_method`** | A entidade formal explicita `class_attribute` (não estava no plano) |
| `object_reference` | **`object_dependency`** | Nome mais claro; semântica idêntica; novo campo `detected_by` (`PARSER`/`AI`) |
| `atc_finding` | idem, **mas com `sap_note_id` apontando para `sap_note` (e não `atc_sap_note`)** | Nome do catálogo reduzido |
| `atc_sap_note` | **`sap_note`** | Nome enxuto |
| `analysis_run` | **`ai_analysis_run`** | Enfatiza IA |
| `object_functional_summary` | **`ai_object_analysis`** | Escopo maior: captura objetivo funcional + `business_domain_inferred` + `complexity_assessment` + `criticality_inferred` + detecção de OSS |
| `quality_finding` | **`ai_finding`** | Mesma função; nome consistente com `ai_analysis_run` |
| `clean_core_classification` | idem, **com novo valor `ATUALIZAR_OSS`** e campos `effort_estimate`/`risk_assessment`/`priority`/`is_final` |
| (ausente) | **`recommendation`** | **Entidade nova** — recomendações textuais consolidadas por objeto, com FK para `clean_core_classification` e lista de SAP Notes consultadas |
| `chunk` + `chunk_embedding_1024` | **`embedding_chunk`** + **`embedding_vector`** (sqlite-vec) | `chunk_text_hash` SHA-256 para detectar rechunking |
| `source_file` + `raw_document` + `source_file_document` | **`source_file`** (com `content_hash` + FK `code_object_id`) + **`ingestion_run`** + **`parse_error`** | Simplificado: sem `raw_document` separado. O conteúdo cru do código vive em `code_object.raw_code`; o hash de conteúdo fica em `source_file.content_hash` |
| `dynpro_screen` + `dynpro_field` + `dynpro_flowlogic` + `gui_title` | **`screen`** + **`screen_field`** + `code_object(type='GUIT')` + `gui_title` | Flow logic embutido como colunas `flow_logic_pbo`/`flow_logic_pai` em `screen` |
| `package` | idem | Primária fonte = ATC (56 pacotes) |

### Entidades / conceitos novos trazidos pela Entrega 1

- **`recommendation`** — camada de recomendações textuais consolidadas (separada de `clean_core_classification`). Cada recomendação tem `title`, `description`, `target_state` (ex.: *"Substituir por API I_SalesOrder do S/4HANA"*) e lista de `referenced_sap_notes`.
- **Detecção de OSS** — `ai_object_analysis.is_oss_library_detected` + `oss_library_name`. Reconhece bibliotecas públicas (abap2xlsx, abapGit, ZSAPLINK) misturadas ao código do cliente. Gera a classificação Clean Core `ATUALIZAR_OSS`.
- **Classificação `ATUALIZAR_OSS`** — sétimo valor em `clean_core_classification.classification` (além de DESCONTINUAR/REMEDIAR/MODERNIZAR/SUBSTITUIR_STANDARD/REIMPLEMENTAR_EXTENSAO/MANTER_AS_IS).
- **`ai_object_analysis.confidence_score`** — autoavaliação 0.0–1.0 do agente por objeto. Crítica para o usuário final filtrar recomendações de baixa confiança no relatório.
- **`ai_object_analysis.complexity_assessment`** e **`criticality_inferred`** — LOW/MEDIUM/HIGH/VERY_HIGH. Alimentam priorização do roadmap.
- **Snapshot do prompt** — `ai_analysis_run.prompt_template_text` guarda o texto completo do prompt usado, não só o `prompt_version`. Garante **reprodutibilidade completa**.
- **Limitações conhecidas (9 itens)** documentadas explicitamente no schema para o relatório final ser claro sobre o escopo — ver `docs/modelagem_conceitual.md` §10. Resumo: sem dados de execução runtime (ST03N/SCMON), TCODES ausentes, SSFO/AQQU/AQSG/LDBA sem código-fonte (só metadados ATC), ZIF_ não exportadas, pacotes só via ATC, cabeçalhos `*$*$` não universais, mojibake ISO-8859-1, OSS misturado com custom, namespace Y pouco exportado (só 2 objetos).

### Decisões que o plano já tinha e a Entrega 1 confirmou

- Deduplicação por `(object_name, object_type)` UNIQUE — Entrega 1 §1.1.
- ATC como camada separada (Camada 2 no formal; Camada F no plano). Semântica idêntica.
- Múltiplos `ai_analysis_run`s coexistindo para reprocessar sem perder histórico — Entrega 1 §1.4.
- `bge-m3` local 1024-dim como modelo primário — Entrega 1 §1.5.
- Rastreabilidade ponta-a-ponta recomendação → análise → finding → objeto → arquivo — Entrega 1 §1.6.

### Decisões que o plano tinha e **a Entrega 1 simplificou**

- **`raw_document` fundido em `code_object.raw_code`** — o plano modelava RAW separada de STRUCT com dedup por `sha256` do arquivo inteiro. A Entrega 1 simplifica: o código fica direto no `code_object` (UTF-8, sem markup) e a rastreabilidade de arquivo-de-origem fica em `source_file(content_hash, code_object_id)`. **Perde-se** a dedup por conteúdo idêntico em formatos diferentes (HTML vs TXT do `objetos/`) — precisa ser resolvida na camada de ingestão (comparar `raw_code` normalizado antes de inserir). A implementação do DDL (Entrega 2) precisa decidir se reintroduz um hash do `raw_code` para detectar essa equivalência.
- **`content_code_sha256`** do plano não aparece na Entrega 1 — equivalente seria um hash em `code_object.raw_code` ou um `source_file.raw_code_hash` adicional. **Ponto a confirmar na Entrega 2.**

### Ajustes para o parser de classes globais Z

A Entrega 1 §3.5 traz `class_attribute` **e** `class_method`, confirmando o que o plano vinha indicando após a descoberta das 308 classes `zcl_*/` com subdiretórios `public_methods/private_methods/protected_methods/dictionary/`. A `visibility` em ambas as entidades é derivada do subdiretório na ingestão (ou do parse `CLASS ... DEFINITION` para classes locais).

## Próximo passo imediato — Entrega 2 (DDL SQLite)

Modelo conceitual aprovado em `docs/modelagem_conceitual.md`. A Entrega 2 materializa:

1. **`db/schema.sql`** — DDL completo SQLite seguindo **estritamente a nomenclatura da Entrega 1**:
   - Camada 0: `ingestion_run`, `source_file`, `parse_error`.
   - Camada 1: `code_object` (central com discriminator), `object_header_metadata`, `modification_history`, `table_field`, `domain`, `domain_value`, `function_module`, `function_group`, `function_parameter`, `function_exception`, `class_attribute`, `class_method`, `method_parameter`, `method_exception`, `interface_implementation`, `screen`, `screen_field`, `gui_title`, `message`, `object_dependency`, `package`.
   - Camada 2 (ATC): `atc_run`, `atc_check`, `atc_finding`, `sap_note`, `simplification_item_category`.
   - Camada 3 (IA): `ai_analysis_run`, `ai_object_analysis`, `ai_finding`, `clean_core_classification`, `recommendation`.
   - Camada 4 (RAG): `embedding_model`, `embedding_chunk`, `embedding_vector` (sqlite-vec `vec0`).
2. **`db/seed_reference_data.sql`** — catálogos:
   - Enums de `object_type` (incluindo ENHO/AQQU/AQSG/SHLP/SSFO/LDBA/FUGS/FUGX/VIEW/INTF).
   - Enums de `dependency_kind` (TABLE_USAGE/FUNCTION_CALL/METHOD_CALL/INCLUDE_USE/MESSAGE_USE/SUBMIT/SCREEN_CALL/INTERFACE_IMPL/INHERITANCE/TYPE_REF/VIEW_BASE/ATC_REFERENCES_SIMPLIFIED_OBJECT).
   - Enums de `clean_core_classification.classification` (DESCONTINUAR/REMEDIAR/MODERNIZAR/SUBSTITUIR_STANDARD/REIMPLEMENTAR_EXTENSAO/**ATUALIZAR_OSS**/MANTER_AS_IS).
   - `atc_check` pré-populado com as 12 Check Titles conhecidas.
   - `simplification_item_category` (B/A/C/I/S/W).
   - Catálogo de `finding_type` em `ai_finding` (HARDCODED_MESSAGE, OBSOLETE_FIELD_EXIT, EMPTY_IMPLEMENTATION, NATIVE_SQL, LEGACY_OFFSET_SUBSTRING, LEGACY_MESSAGE_PLACEHOLDER, …).
   - `embedding_model` pré-populado com `BAAI/bge-m3` (dim 1024, provider `local`).
   - `package` populado a partir dos 56 distintos do ATC.
3. **Decisão pendente na Entrega 2**: reintroduzir ou não um `raw_code_hash` em `source_file` / `code_object` para detectar equivalência de código entre formatos (HTML canônico vs TXT do `objetos/`). Recomendação: **incluir `source_file.raw_code_hash`** (SHA-256 do código limpo extraído) como defesa contra duplicação lógica.
4. **Diagrama ER Mermaid** já está na §8 do `docs/modelagem_conceitual.md`.

Entrega 3 (SQLAlchemy) e Entrega 4 (notebooks) ficam para sessões seguintes.

## Verificação do schema (quando materializado)

- Carga da extensão: `python -c "import sqlite3, sqlite_vec; con = sqlite3.connect(':memory:'); con.enable_load_extension(True); sqlite_vec.load(con); con.executescript(open('db/schema.sql').read())"`.
- Smoke test básico: inserir 1 `ingestion_run` + 1 `source_file` + 1 `code_object` + 1 `embedding_chunk` + 1 `embedding_vector` float[1024]; rodar KNN contra si mesmo.
- Smoke test bge-m3: carregar modelo (`BAAI/bge-m3`), embeddar um cabeçalho `*$*$` real em PT-BR (via `object_header_metadata.purpose`) e a query `"apuração de ICMS"`; verificar que retorna o cabeçalho do sistema ANEXO no topo do KNN.
- Smoke test dedupe: ingerir `ZTBCAI_DOC_A` duas vezes (dump global + anexo ao programa) e validar que `code_object` tem 1 linha, `table_field` tem N linhas (não 2N), e `source_file` tem 2 linhas apontando para o mesmo `code_object_id`.
- **Smoke test ATC**: importar o XLSX real; validar que:
  - Totais batem com o cabeçalho do DOCX: 7 899 findings, 2 139 E / 1 614 W / 4 146 I, 1 264 objetos únicos, 56 pacotes, 14 tipos de objeto, 12 checks, 56 SAP Notes.
  - Query *"quais custom tocam tabelas simplificadas"* retorna linhas com `referenced_object_name='VBUK'`, `WRBTR`, `ATWRT`.
  - Agregação por `sap_note` lista 56 notas (ex.: 2610650, 2215424, 2198647, 3320010, **2296016** para orphaned objects).
  - Agregação por `package` mostra ZSD, ZMM, ZFI, ZINCORPORACAO com volumes esperados.
  - Agregação por `referenced_app_component` lista SD-BF-MIG, CA-FLE-AMT, LO-MD-BP, CO-PA.
  - Agregação por `change_category` mostra distribuição A/T/F (proxy de esforço).
- Smoke test classes globais: ingerir uma pasta `zcl_*` com 3 métodos em `public_methods/` e 1 em `private_methods/`; validar que `code_object(type='CLAS')` tem 1 linha, `class_method` tem 4 linhas com `visibility` correto derivado do subdiretório.
- Validar as views do relatório com dados sintéticos cobrindo cada situação Clean Core (DESCONTINUAR/REMEDIAR/MODERNIZAR/SUBSTITUIR_STANDARD/REIMPLEMENTAR_EXTENSAO/**ATUALIZAR_OSS**/MANTER_AS_IS) e cada categoria ATC.
- Validar rastreabilidade ponta-a-ponta: partindo de uma `recommendation`, navegar até a `clean_core_classification`, daí aos `ai_finding`/`atc_finding`, daí ao `code_object`, daí aos `source_file`s de origem — retorna os paths físicos.

---

## Atualização da PoC — baseline de experiência e design (23/09/2026)

A evolução da PoC passa a considerar a experiência visual e de interação como parte explícita da arquitetura da solução.

As decisões canônicas de design estão documentadas em `docs/design/` e devem orientar qualquer nova implementação de frontend:

- Dark Mode enterprise como padrão;
- `#E30074` como cor oficial T-Systems para ações primárias, seleção, foco, IA e identidade;
- application shell permanente em três regiões: **Sidebar | Main Workspace | AI Copilot**;
- AI Copilot disponível em todas as principais visões;
- Copilot context-aware, sincronizado com application, Analysis Run, view e seleção corrente;
- respostas de IA com referências/evidências estruturadas;
- possibilidade de ações controladas do Copilot sobre a UI, como seleção, navegação e highlight de componentes;
- rastreabilidade obrigatória para afirmações analíticas e recomendações sempre que houver evidência disponível;
- mesmo design system e shell reutilizados em Executive Overview, Architecture & Clean Core, Clean Core Findings, Business Rules, Engineering, Application Discovery e Modernization Opportunities.

A referência visual inicial é o mockup **Architecture & Clean Core**, preservado em `docs/design/reference/architecture-clean-core/`. O HTML é material de handoff e validação visual, não arquitetura de produção.

A decisão arquitetural correspondente está registrada em `docs/architecture/adr-ux-001-context-aware-ai-copilot.md`.
