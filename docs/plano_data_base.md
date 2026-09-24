# Plano: Entrega 2 — DDL SQLite (schema.sql + seed)

> **R3.1 ATC compatibility note (2026-09-24):** this is historical/analytical material. Any fixed counts, column lists, pre-seeded ATC checks, packages or values described below reflect a reviewed sample and are **not** the runtime XLSX contract. Canonical ATC ingestion is schema-tolerant and defined by `docs/data/atc-import-contract.md` and ADR-016.


> **HISTORICAL ANALYTICAL DOCUMENT:** Preserved as prior analysis/reference. It is not the current runtime/domain/UX source of truth. Baseline R3.1, accepted ADRs, and current `docs/data`, `docs/product`, `docs/ux`, `docs/design`, and `docs/delivery` documents prevail on conflicts.

## Contexto

Projeto Copa Energia — migração SAP ECC → S/4HANA. A Entrega 1 (modelagem conceitual em `docs/modelagem_conceitual.md`) foi aprovada. Esta entrega produz o DDL SQLite executável que materialize essa modelagem.

Fonte de verdade para nomes e estrutura: `docs/modelagem_conceitual.md`.
Fonte de verdade para decisões de design e achados técnicos: `docs/plano_sap_clean_core.md`.

Quando há divergência entre os dois documentos, prevalece o `modelagem_conceitual.md` (conforme registrado no plano).

---

## Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `db/schema.sql` | DDL principal: CREATE TABLE, indexes, constraints, FKs |
| `db/seed_reference_data.sql` | INSERT de dados de referência: enums, catálogos pré-seed |
| `db/views.sql` | CREATE VIEW para as `v_*` do relatório final |

---

## Ordem de criação das tabelas no schema.sql

O SQLite com `PRAGMA foreign_keys = ON` exige que as tabelas pai existam antes das filhas. Ordem:

### Bloco 0 — Metadados de ingestão (sem dependências)
1. `ingestion_run`
2. `source_file`
3. `parse_error`

### Bloco 1 — Catálogo de objetos (entidades pai)
4. `package`
5. `code_object` ← tabela central; FK para `package` e `source_file`
6. `source_file` precisa de FK para `code_object` (primário) — resolver com ALTER ou coluna nullable

**Nota sobre dependência circular** entre `source_file` e `code_object`: `source_file` tem FK `code_object_id` (opcional) e `code_object` tem FK `primary_source_file_id` (opcional). Solução: ambas as FKs são nullable; criar as duas tabelas sem a FK circular primeiro, depois os índices. O SQLite não suporta ALTER TABLE ADD CONSTRAINT — solução: `code_object.primary_source_file_id` declarado sem FK formal; a integridade é mantida na camada de aplicação (Python). Registrar no comentário do DDL.

### Bloco 2 — Entidades filhas de code_object (1:1 ou 1:N diretas)
7. `object_header_metadata`
8. `modification_history`
9. `domain` (sem FK para code_object — entidade própria)
10. `domain_value`
11. `data_element` (sem FK para code_object no DDL — referenciada por table_field)
12. `table_field`
13. `function_group`
14. `function_module`
15. `function_parameter`
16. `function_exception`
17. `class_attribute`
18. `class_method`
19. `method_parameter`
20. `method_exception`
21. `interface_implementation`
22. `screen`
23. `screen_field`
24. `gui_title`
25. `message`
26. `object_dependency`

### Bloco 3 — ATC (Camada 2)
27. `atc_run`
28. `atc_check`
29. `sap_note`
30. `simplification_item_category`
31. `atc_finding`

### Bloco 4 — Análise IA (Camada 3)
32. `ai_analysis_run`
33. `ai_object_analysis`
34. `ai_finding`
35. `clean_core_classification`
36. `recommendation`

### Bloco 5 — Embeddings (Camada 4)
37. `embedding_model`
38. `embedding_chunk`
39. `embedding_vector` (tabela virtual `vec0` do sqlite-vec)

---

## Decisões de implementação DDL

### Tipos de dados SQLite
- PKs: `INTEGER PRIMARY KEY AUTOINCREMENT`
- Texto: `TEXT NOT NULL` ou `TEXT` (nullable quando explicitamente opcional)
- Booleanos: `INTEGER NOT NULL DEFAULT 0` com `CHECK(col IN (0,1))`
- Datas/timestamps: `TEXT` em formato ISO-8601 UTC
- Contadores/inteiros: `INTEGER`
- Floats (confidence scores): `REAL`

### Foreign Keys
- `PRAGMA foreign_keys = ON` no topo do schema (instrução de runtime, não DDL)
- Comentário no arquivo informando que deve ser executado em cada conexão
- FKs explícitas via `REFERENCES tabela(col)` com `ON DELETE` adequado:
  - Filhas de `code_object`: `ON DELETE CASCADE`
  - Referências cruzadas opcionais (ex.: `atc_finding.code_object_id`): `ON DELETE SET NULL`

### Enums como CHECK constraints
Valores controlados implementados como `CHECK(col IN (...))` diretamente na coluna, sem tabelas de lookup separadas para tipos simples. Catálogos com descrição própria (ex.: `simplification_item_category`, `atc_check`) são tabelas.

### Indexes
Todos os índices identificados no plano:
- `source_file(sha256)`
- `code_object(object_type, object_name)` — UNIQUE
- `code_object(package_id)`
- `object_dependency(source_object_id)`
- `object_dependency(target_object_id)`
- `object_dependency(target_object_name)`
- `table_field(code_object_id)`
- `atc_finding(atc_run_id, source_object_id)`
- `atc_finding(atc_run_id, referenced_object_id)` (quando preenchido)
- `atc_finding(check_id, priority)`
- `atc_finding(referenced_object_name)`
- `atc_finding(sap_note_id)`
- `atc_finding(package_id)`
- `clean_core_classification(code_object_id, is_current)`
- `embedding_chunk(code_object_id)`

### sqlite-vec
- `embedding_vector` declarada como tabela virtual: `CREATE VIRTUAL TABLE embedding_vector USING vec0(chunk_id INTEGER, embedding FLOAT[1024])`
- Comentário no DDL: requer `SELECT load_extension('vec0')` antes de executar esta instrução
- Schema separado em bloco comentado no final do `schema.sql`

---

## Conteúdo do seed_reference_data.sql

### `simplification_item_category` (6 registros)
`I`=Information, `W`=Warning, `B`=Blocker, `S`=Structural, `A`=Automatic, `C`=Compatible

### `atc_check` (catálogo dinâmico; o arquivo de referência apresentou 12 checks)
- Search problematic statements for SELECT/OPEN CURSOR without ORDER BY
- S/4HANA: Search for Usages of Simplified Objects
- S/4HANA: Field Length Extensions
- S/4HANA: Search for Database Operations
- S/4HANA: Search for Simplified Transactions in Literals
- Prerequisites for the test
- Critical Statements
- S/4HANA: Readiness Check for SAP Queries
- Use of ADBC Interface
- S/4HANA: Search for Base Tables of ABAP Dictionary and CDS Views
- Find ABAP Statement Patterns
- Scan a Program

### `embedding_model` (1 registro pré-seed)
`BAAI/bge-m3`, provider=`local`, dimension=1024

---

## Conteúdo do views.sql

Views nomeadas `v_*` para as 6 perguntas do relatório final + auxiliares:
- `v_programas_em_uso`
- `v_acessos_tabelas_alteradas_s4`
- `v_problemas_performance`
- `v_riscos_upgrade`
- `v_candidatos_descontinuar`
- `v_candidatos_clean_core`
- `v_mensagens_orfas`
- `v_hardcoded_messages`
- `v_findings_por_sap_note`
- `v_findings_por_simplified_object`
- `v_findings_por_package`

---

## Verificação

Após criar os arquivos:
```bash
# Criar banco e verificar que o schema executa sem erros
sqlite3 db/sap_clean_core.db < db/schema.sql
sqlite3 db/sap_clean_core.db < db/seed_reference_data.sql
sqlite3 db/sap_clean_core.db < db/views.sql

# Verificar tabelas criadas
sqlite3 db/sap_clean_core.db ".tables"

# Verificar seed carregado
sqlite3 db/sap_clean_core.db "SELECT * FROM simplification_item_category;"
sqlite3 db/sap_clean_core.db "SELECT count(*) FROM atc_check;"
```

---

## Arquivos críticos (referência, não modificar)

- `docs/modelagem_conceitual.md` — fonte de verdade do modelo
- `docs/plano_sap_clean_core.md` — decisões de design e achados técnicos
