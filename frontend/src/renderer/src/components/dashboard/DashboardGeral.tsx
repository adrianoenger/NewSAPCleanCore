/**
 * Dashboard Geral — the single results screen (SPRINT-18 / ADR-019, supersedes the SPRINT-15
 * perspective views). Root: clickable KPIs + reference-dashboard panels. Every KPI/panel opens a
 * full-page list, every list row a full-page detail; the drill-down is a stack owned by App.tsx
 * (so Copilot navigation can push onto it) rendered here with a breadcrumb and a Voltar button.
 */
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, Boxes, ChevronRight, ScrollText, Sparkles, TrendingUp } from 'lucide-react'
import { AtcPanel, AtcPriorityBars, CleanCoreDonut, InventoryPanel } from '@/components/dashboard/charts'
import { DetailPage } from '@/components/dashboard/DetailPage'
import { EntityList } from '@/components/dashboard/EntityList'
import { ErrorState } from '@/components/shared/ErrorState'
import { fetchDashboardOverview } from '@/lib/api'
import type { DrillPage, ResultFocus } from '@/lib/resultNav'

type ListPage = Extract<DrillPage, { type: 'list' }>

interface Props {
  assessmentId: number
  drill: DrillPage[]
  onPush: (page: DrillPage) => void
  onPopTo: (depth: number) => void
}

const DETAIL_FALLBACK_LABEL: Record<ResultFocus['kind'], string> = {
  sap_object: 'Objeto',
  application: 'Aplicação',
  business_rule: 'Regra de negócio',
  atc_finding: 'Finding ATC',
}

function pageLabel(page: DrillPage): string {
  if (page.type === 'list') return page.title
  return page.label ?? `${DETAIL_FALLBACK_LABEL[page.focus.kind]} #${page.focus.id}`
}

function KpiCard({
  icon: Icon,
  label,
  value,
  onClick,
}: {
  icon: React.ElementType
  label: string
  value: number
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex flex-col gap-2 rounded border border-border-soft bg-surface-elevated p-4 text-left transition-colors hover:border-brand/50 hover:bg-surface-hover"
    >
      <div className="flex items-center justify-between">
        <Icon className="h-4 w-4 text-brand" strokeWidth={1.75} />
        <ChevronRight className="h-3.5 w-3.5 text-text-tertiary opacity-0 transition-opacity group-hover:opacity-100" strokeWidth={2} />
      </div>
      <div className="text-[22px] font-semibold text-text-primary">{value.toLocaleString('pt-BR')}</div>
      <div className="text-[11px] text-text-tertiary">{label}</div>
    </button>
  )
}

function DashboardRoot({ assessmentId, onOpenList }: { assessmentId: number; onOpenList: (page: ListPage) => void }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dashboard-overview', assessmentId],
    queryFn: () => fetchDashboardOverview(assessmentId),
  })

  if (isLoading) return <div className="flex h-full items-center justify-center text-[12px] text-text-tertiary">Carregando…</div>
  if (isError || !data) return <ErrorState message="Não foi possível carregar o dashboard." onRetry={refetch} />
  const s = data.summary

  return (
    <div className="space-y-6 p-6">
      {s.is_stale && (
        <div className="flex items-start gap-2 rounded border border-attention/30 bg-attention/5 px-3 py-2 text-[11px] text-attention">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Dados desatualizados — reprocesse em &quot;3 - Processamento por IA&quot; para uma síntese atual.
        </div>
      )}

      <div>
        <div className="mb-2 text-[12px] font-medium text-text-secondary">Resumo do processamento</div>
        <div className="grid grid-cols-5 gap-3">
          <KpiCard
            icon={Boxes}
            label="Objetos analisados"
            value={s.objects_analyzed}
            onClick={() => onOpenList({ type: 'list', entity: 'objects', filter: {}, title: 'Objetos analisados' })}
          />
          <KpiCard
            icon={Sparkles}
            label="Customizações identificadas"
            value={s.customizations_identified}
            onClick={() => onOpenList({ type: 'list', entity: 'applications', filter: {}, title: 'Customizações identificadas (aplicações)' })}
          />
          <KpiCard
            icon={AlertTriangle}
            label="Findings críticos"
            value={s.critical_findings}
            onClick={() =>
              onOpenList({ type: 'list', entity: 'atc_findings', filter: { priority: 1 }, title: 'Findings críticos (Prioridade 1)' })
            }
          />
          <KpiCard
            icon={TrendingUp}
            label="Objetos com alto impacto"
            value={s.high_impact_objects}
            onClick={() =>
              onOpenList({ type: 'list', entity: 'objects', filter: { high_impact: true }, title: 'Objetos com alto impacto' })
            }
          />
          <KpiCard
            icon={ScrollText}
            label="Regras de negócio identificadas"
            value={s.business_rules_identified}
            onClick={() => onOpenList({ type: 'list', entity: 'business_rules', filter: {}, title: 'Regras de negócio' })}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <InventoryPanel data={data} onOpenList={onOpenList} />
        <AtcPanel data={data} onOpenList={onOpenList} />
        <CleanCoreDonut data={data} onOpenList={onOpenList} />
        <AtcPriorityBars data={data} onOpenList={onOpenList} />
      </div>
    </div>
  )
}

export function DashboardGeral({ assessmentId, drill, onPush, onPopTo }: Props) {
  const top = drill[drill.length - 1]
  const onNavigate = (focus: ResultFocus, label?: string) => onPush({ type: 'detail', focus, label })

  return (
    <div className="flex h-full flex-col">
      {drill.length > 0 && (
        <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border-soft px-6 text-[12px]">
          <button
            type="button"
            onClick={() => onPopTo(drill.length - 1)}
            className="flex items-center gap-1 rounded-control px-1.5 py-0.5 text-text-secondary hover:bg-surface-hover hover:text-text-primary"
          >
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} />
            Voltar
          </button>
          <span className="text-border-default">|</span>
          <nav className="flex min-w-0 items-center gap-1 text-text-tertiary" aria-label="Drill-down">
            <button type="button" onClick={() => onPopTo(0)} className="shrink-0 hover:text-text-primary">
              Dashboard Geral
            </button>
            {drill.map((page, idx) => (
              <span key={idx} className="flex min-w-0 items-center gap-1">
                <ChevronRight className="h-3 w-3 shrink-0" strokeWidth={2} />
                {idx === drill.length - 1 ? (
                  <span className="truncate font-medium text-text-primary">{pageLabel(page)}</span>
                ) : (
                  <button type="button" onClick={() => onPopTo(idx + 1)} className="truncate hover:text-text-primary">
                    {pageLabel(page)}
                  </button>
                )}
              </span>
            ))}
          </nav>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {top == null ? (
          <DashboardRoot assessmentId={assessmentId} onOpenList={onPush} />
        ) : top.type === 'list' ? (
          <EntityList key={drill.length} assessmentId={assessmentId} page={top} onOpenDetail={onNavigate} />
        ) : (
          <DetailPage assessmentId={assessmentId} focus={top.focus} onNavigate={(focus) => onNavigate(focus)} />
        )}
      </div>
    </div>
  )
}
