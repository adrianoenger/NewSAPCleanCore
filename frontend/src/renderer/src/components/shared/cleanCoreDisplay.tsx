/**
 * Clean Core display primitives shared by ApplicationBrowser (Architecture View), ObjectBrowser's
 * remediation panel (Technical View) and ExecutiveView — kept in one module so neither browser
 * needs to import the other (would otherwise be a circular import between the two).
 */
import type { ApplicationRecord } from '@/lib/api'
import { cn } from '@/lib/utils'

// Baseline core rule 8: Technical Risk and Business Importance are separate dimensions, each
// using the same 4-level severity palette from docs/design/design-system.md §3.4.
export const LEVEL_CONFIG: Record<string, { label: string; color: string }> = {
  LOW: { label: 'Baixo', color: 'text-low' },
  MEDIUM: { label: 'Médio', color: 'text-attention' },
  HIGH: { label: 'Alto', color: 'text-legacy' },
  CRITICAL: { label: 'Crítico', color: 'text-risk' },
}

export const RECOMMENDATION_CONFIG: Record<string, { label: string; color: string }> = {
  RETAIN: { label: 'Manter', color: 'text-success' },
  REMEDIATE: { label: 'Remediar', color: 'text-attention' },
  REPLATFORM: { label: 'Replataformar', color: 'text-info' },
  RETIRE: { label: 'Aposentar', color: 'text-risk' },
  REVIEW: { label: 'Revisão necessária', color: 'text-legacy' },
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

export function RecommendationChip({ recommendation }: { recommendation: string }) {
  const cfg = RECOMMENDATION_CONFIG[recommendation] ?? { label: recommendation, color: 'text-text-tertiary' }
  return (
    <span
      className={cn(
        'rounded-full border border-border-soft bg-surface-elevated px-1.5 py-0.5 text-[10px] font-medium',
        cfg.color,
      )}
    >
      {cfg.label}
    </span>
  )
}

/** Shared with ExecutiveView's Clean Core distribution + macro recommendations (SPRINT-15). */
export function countByRecommendation(applications: ApplicationRecord[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const app of applications) {
    if (!app.clean_core || app.clean_core.status === 'FAILED') continue
    counts[app.clean_core.recommendation] = (counts[app.clean_core.recommendation] ?? 0) + 1
  }
  return counts
}
