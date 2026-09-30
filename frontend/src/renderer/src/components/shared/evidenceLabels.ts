/** Human labels for evidence/context `source_type` values (shared by every detail view and the Copilot). */
export const SOURCE_TYPE_LABELS: Record<string, string> = {
  SOURCE_CODE: 'Código-fonte',
  ATC_FINDING: 'Achado ATC',
  SUPPLEMENTAL_EVIDENCE: 'Evidência complementar',
  SAP_OBJECT: 'Objeto SAP',
  DEPENDENCY: 'Dependência detectada',
  TECHNICAL_FINDING: 'Finding técnico',
  PROCESS_USAGE_EVIDENCE: 'Evidência de processo/uso',
  SAP_KNOWLEDGE: 'Referência SAP',
  // SPRINT-16: AI Copilot context item source types (ai/copilot/context.py)
  OBJECT_UNDERSTANDING: 'Entendimento por IA',
  BUSINESS_RULE: 'Regra de negócio',
  APPLICATION: 'Aplicação',
  CLEAN_CORE_ASSESSMENT: 'Avaliação Clean Core',
  STRUCTURED_SUMMARY: 'Resumo estruturado',
  EVIDENCE_RECORD: 'Registro de evidência',
}
