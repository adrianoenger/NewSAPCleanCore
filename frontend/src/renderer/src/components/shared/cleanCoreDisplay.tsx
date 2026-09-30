/**
 * Clean Core display primitives shared by the Dashboard charts/lists and the application/object
 * detail pages — kept in one module so the detail pages do not need to import each other.
 */
import { Sparkles } from 'lucide-react'
import { SOURCE_TYPE_LABELS } from '@/components/shared/evidenceLabels'
import type { ApplicationRecord, CleanCoreAssessmentRecord } from '@/lib/api'
import { cn } from '@/lib/utils'

// Baseline core rule 8: Technical Risk and Business Importance are separate dimensions, each
// using the same 4-level severity palette from docs/design/design-system.md §3.4.
export const LEVEL_CONFIG: Record<string, { label: string; color: string }> = {
  LOW: { label: 'Baixo', color: 'text-low' },
  MEDIUM: { label: 'Médio', color: 'text-attention' },
  HIGH: { label: 'Alto', color: 'text-legacy' },
  CRITICAL: { label: 'Crítico', color: 'text-risk' },
}

// ADR-018: the 7 Clean Core categories — hex colors mirror the reference dashboard's palette
// (docs/adr/018) so charts and chips stay visually consistent. A NULL recommendation is rendered
// as UNCLASSIFIED ("Não classificado") — there is no fallback category.
export const RECOMMENDATION_CONFIG: Record<string, { label: string; hex: string; description: string }> = {
  MODERNIZAR: { label: 'Modernizar', hex: '#3498db', description: 'Refatorar para ABAP Cloud / APIs liberadas.' },
  MANTER_AS_IS: { label: 'Manter as-is', hex: '#95a5a6', description: 'Já compatível ou sem risco relevante.' },
  REMEDIAR: { label: 'Remediar', hex: '#f39c12', description: 'Corrigir violações pontuais (ATC / APIs não liberadas).' },
  DESCONTINUAR: { label: 'Descontinuar', hex: '#e74c3c', description: 'Sem uso ou obsoleto; pode ser removido.' },
  REIMPLEMENTAR_EXTENSAO: {
    label: 'Reimplementar como extensão',
    hex: '#9b59b6',
    description: 'Reconstruir como extensão side-by-side (BTP) ou key-user.',
  },
  SUBSTITUIR_STANDARD: {
    label: 'Substituir por standard',
    hex: '#2ecc71',
    description: 'Existe funcionalidade standard SAP equivalente.',
  },
  ATUALIZAR_OSS: { label: 'Atualizar via nota OSS', hex: '#f1c40f', description: 'Depende de nota OSS / correção SAP a aplicar.' },
}

export const UNCLASSIFIED = 'UNCLASSIFIED'
export const UNCLASSIFIED_CONFIG = {
  label: 'Não classificado',
  hex: '#bdc3c7',
  description: 'A análise não chegou a uma classificação confiável (falha ou contexto insuficiente).',
}

export function recommendationConfig(recommendation: string | null) {
  if (recommendation == null || recommendation === UNCLASSIFIED) return UNCLASSIFIED_CONFIG
  return RECOMMENDATION_CONFIG[recommendation] ?? { label: recommendation, hex: '#7f8c8d', description: '' }
}

export function LevelBadge({ level, title }: { level: string | null; title: string }) {
  if (level == null) {
    return <span className="text-[10px] text-text-tertiary">—</span>
  }
  const cfg = LEVEL_CONFIG[level] ?? { label: level, color: 'text-text-tertiary' }
  return (
    <span className={cn('text-[10px] font-medium', cfg.color)} title={title}>
      {cfg.label}
    </span>
  )
}

export function RecommendationChip({ recommendation }: { recommendation: string | null }) {
  const cfg = recommendationConfig(recommendation)
  return (
    <span
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-full border border-border-soft bg-surface-elevated px-1.5 py-0.5 text-[10px] font-medium text-text-primary"
      title={cfg.description}
    >
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: cfg.hex }} />
      {cfg.label}
    </span>
  )
}

/** Counts applications per recommendation; analyzed-but-unclassified ones fall under UNCLASSIFIED. */
export function countByRecommendation(applications: ApplicationRecord[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const app of applications) {
    if (!app.clean_core) continue
    const key = app.clean_core.recommendation ?? UNCLASSIFIED
    counts[key] = (counts[key] ?? 0) + 1
  }
  return counts
}

/** Full Clean Core conclusion of one Application (risk, importance, classification + rationale). */
export function CleanCorePanel({ cleanCore }: { cleanCore: CleanCoreAssessmentRecord | null }) {
  if (cleanCore == null) {
    return (
      <div className="rounded border border-border-soft bg-surface-elevated px-3 py-2 text-[11px] text-text-tertiary">
        Ainda não analisado pelo Clean Core. Execute &quot;3 - Processamento por IA&quot;.
      </div>
    )
  }

  if (cleanCore.status === 'FAILED') {
    return (
      <div className="rounded border border-risk/30 bg-risk/5 px-3 py-2 text-[11px] text-risk">
        Falha ao gerar a análise Clean Core: {cleanCore.error ?? 'erro desconhecido'}
      </div>
    )
  }

  return (
    <div className="space-y-3 rounded border border-border-soft bg-surface-elevated p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary">
          <Sparkles className="h-3.5 w-3.5 text-brand" strokeWidth={2} />
          Clean Core
        </div>
        {cleanCore.confidence != null && (
          <span className="rounded-full bg-surface-hover px-2 py-0.5 text-[10px] font-mono text-text-tertiary">
            confiança {Math.round(cleanCore.confidence * 100)}%
          </span>
        )}
      </div>

      {cleanCore.status === 'INSUFFICIENT_CONTEXT' && (
        <div className="rounded border border-attention/30 bg-attention/5 px-2 py-1.5 text-[11px] text-attention">
          Evidência insuficiente para uma classificação Clean Core confiável.
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Risco Técnico</div>
          <div className="mt-0.5">
            <LevelBadge level={cleanCore.technical_risk} title="Risco Técnico" />
          </div>
          {cleanCore.technical_risk_rationale && (
            <div className="mt-1 text-[11px] text-text-secondary">{cleanCore.technical_risk_rationale}</div>
          )}
          {cleanCore.technical_risk_evidence_refs.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {cleanCore.technical_risk_evidence_refs.map((ref) => (
                <span
                  key={ref.ref_id}
                  title={SOURCE_TYPE_LABELS[ref.source_type] ?? ref.source_type}
                  className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary"
                >
                  {ref.ref_id}
                </span>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
            Importância de Negócio
          </div>
          <div className="mt-0.5">
            <LevelBadge level={cleanCore.business_importance} title="Importância de Negócio" />
          </div>
          {cleanCore.business_importance_rationale && (
            <div className="mt-1 text-[11px] text-text-secondary">{cleanCore.business_importance_rationale}</div>
          )}
          {cleanCore.business_importance_evidence_refs.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {cleanCore.business_importance_evidence_refs.map((ref) => (
                <span
                  key={ref.ref_id}
                  title={SOURCE_TYPE_LABELS[ref.source_type] ?? ref.source_type}
                  className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary"
                >
                  {ref.ref_id}
                </span>
              ))}
            </div>
          )}
          <div className="mt-1 text-[10px] text-text-tertiary">
            {cleanCore.business_importance_uses_process_usage_evidence
              ? '✓ considera sinais de processo/uso/perfil correlacionados'
              : 'baseada apenas na identidade dos objetos — sem sinais de processo/uso correlacionados'}
          </div>
        </div>
      </div>

      <div className="border-t border-border-soft pt-2">
        <div className="flex items-center gap-2">
          <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Recomendação</div>
          <RecommendationChip recommendation={cleanCore.recommendation} />
        </div>
        {cleanCore.recommendation_rationale && (
          <div className="mt-1 text-[11px] text-text-secondary">{cleanCore.recommendation_rationale}</div>
        )}
        {cleanCore.recommendation_evidence_refs.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {cleanCore.recommendation_evidence_refs.map((ref) => (
              <span
                key={ref.ref_id}
                title={SOURCE_TYPE_LABELS[ref.source_type] ?? ref.source_type}
                className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary"
              >
                {ref.ref_id}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
