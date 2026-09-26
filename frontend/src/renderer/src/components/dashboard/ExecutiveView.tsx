/**
 * Executive View (ADR-009 / Baseline): risks, critical applications, macro recommendations,
 * Clean Core distribution and a suggested roadmap — all derived from the same Application +
 * CleanCoreAssessment data ApplicationBrowser (Architecture View) already loads, grouped/ranked
 * differently for an executive audience. Every item drills into Architecture View.
 */
import { useQuery } from '@tanstack/react-query'
import { AlertOctagon, ChevronRight, Map, ShieldAlert, Sparkles } from 'lucide-react'
import { LevelBadge, RECOMMENDATION_CONFIG, RecommendationChip, countByRecommendation } from '@/components/shared/cleanCoreDisplay'
import { ErrorState } from '@/components/shared/ErrorState'
import { fetchApplications, type ApplicationRecord } from '@/lib/api'
import type { ResultFocus } from '@/lib/resultNav'

interface Props {
  assessmentId: number
  onNavigate: (target: ResultFocus) => void
}

const SEVERITY_ORDER: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
const ROADMAP_ORDER = ['RETIRE', 'REPLATFORM', 'REMEDIATE', 'REVIEW', 'RETAIN']

function analyzedApplications(applications: ApplicationRecord[]): ApplicationRecord[] {
  return applications.filter((a) => a.clean_core && a.clean_core.status !== 'FAILED')
}

function AppRow({ app, onNavigate }: { app: ApplicationRecord; onNavigate: (target: ResultFocus) => void }) {
  return (
    <button
      type="button"
      onClick={() => onNavigate({ kind: 'application', id: app.id })}
      className="flex w-full items-center justify-between gap-2 rounded bg-surface-elevated px-3 py-2 text-left text-[12px] hover:bg-surface-hover"
    >
      <span className="min-w-0 truncate font-medium text-text-primary">
        {app.name || `Aplicação #${app.id} (sem nome)`}
      </span>
      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-text-tertiary" strokeWidth={2} />
    </button>
  )
}

export function ExecutiveView({ assessmentId, onNavigate }: Props) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['applications', assessmentId],
    queryFn: () => fetchApplications(assessmentId),
  })

  if (isLoading) {
    return <div className="flex h-full items-center justify-center text-[12px] text-text-tertiary">Carregando…</div>
  }

  if (isError) {
    return <ErrorState message="Não foi possível carregar as aplicações." onRetry={refetch} />
  }

  const applications = data?.applications ?? []
  const analyzed = analyzedApplications(applications)

  if (analyzed.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-text-tertiary">
        <p className="text-[13px] text-text-secondary">Nenhuma análise Clean Core disponível ainda.</p>
        <p className="text-[12px]">Execute &quot;3 - Processamento por IA&quot; primeiro.</p>
      </div>
    )
  }

  const risks = [...analyzed]
    .filter((a) => a.clean_core!.technical_risk != null)
    .sort(
      (a, b) => SEVERITY_ORDER[a.clean_core!.technical_risk!] - SEVERITY_ORDER[b.clean_core!.technical_risk!],
    )
    .slice(0, 5)

  const critical = analyzed.filter(
    (a) =>
      ['HIGH', 'CRITICAL'].includes(a.clean_core!.technical_risk ?? '') &&
      ['HIGH', 'CRITICAL'].includes(a.clean_core!.business_importance ?? ''),
  )

  const distribution = countByRecommendation(applications)

  const roadmapGroups = ROADMAP_ORDER.map((rec) => ({
    recommendation: rec,
    apps: analyzed.filter((a) => a.clean_core!.recommendation === rec),
  })).filter((g) => g.apps.length > 0)

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div className="grid grid-cols-2 gap-6">
        <div>
          <div className="mb-2 flex items-center gap-1.5 text-[12px] font-medium text-text-secondary">
            <ShieldAlert className="h-3.5 w-3.5" strokeWidth={2} />
            Principais riscos técnicos
          </div>
          <div className="space-y-1.5">
            {risks.map((app) => (
              <button
                key={app.id}
                type="button"
                onClick={() => onNavigate({ kind: 'application', id: app.id })}
                className="block w-full rounded bg-surface-elevated px-3 py-2 text-left text-[12px] hover:bg-surface-hover"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate font-medium text-text-primary">
                    {app.name || `Aplicação #${app.id} (sem nome)`}
                  </span>
                  <LevelBadge level={app.clean_core!.technical_risk} title="Risco Técnico" />
                </div>
                {app.clean_core!.technical_risk_rationale && (
                  <div className="mt-0.5 text-[11px] text-text-tertiary">
                    {app.clean_core!.technical_risk_rationale}
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-1.5 text-[12px] font-medium text-text-secondary">
            <AlertOctagon className="h-3.5 w-3.5" strokeWidth={2} />
            Aplicações críticas (alto risco + alta importância)
          </div>
          {critical.length === 0 ? (
            <div className="text-[11px] text-text-tertiary">Nenhuma aplicação combina alto risco e alta importância.</div>
          ) : (
            <div className="space-y-1.5">
              {critical.map((app) => (
                <AppRow key={app.id} app={app} onNavigate={onNavigate} />
              ))}
            </div>
          )}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center gap-1.5 text-[12px] font-medium text-text-secondary">
          <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
          Distribuição Clean Core e recomendações macro
        </div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(distribution).map(([recommendation, count]) => (
            <span key={recommendation} className="flex items-center gap-1.5 rounded bg-surface-elevated px-2.5 py-1.5 text-[11px]">
              <RecommendationChip recommendation={recommendation} />
              <span className="text-text-secondary">
                {count} aplica{count === 1 ? 'ção recomendada' : 'ções recomendadas'} para{' '}
                {RECOMMENDATION_CONFIG[recommendation]?.label ?? recommendation}
              </span>
            </span>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center gap-1.5 text-[12px] font-medium text-text-secondary">
          <Map className="h-3.5 w-3.5" strokeWidth={2} />
          Roadmap sugerido
        </div>
        <div className="space-y-3">
          {roadmapGroups.map(({ recommendation, apps }) => (
            <div key={recommendation}>
              <div className="mb-1 flex items-center gap-2">
                <RecommendationChip recommendation={recommendation} />
                <span className="text-[10px] text-text-tertiary">{apps.length} aplicação(ões)</span>
              </div>
              <div className="space-y-1">
                {apps.map((app) => (
                  <AppRow key={app.id} app={app} onNavigate={onNavigate} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
