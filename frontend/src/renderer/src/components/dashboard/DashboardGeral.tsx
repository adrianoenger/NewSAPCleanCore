/**
 * Dashboard Geral — cross-perspective synthesis and navigation entry point (ADR-009). Shows the
 * Baseline's Preliminary Processing Summary KPIs and a quick-nav card per result perspective;
 * deliberately does not repeat Executive View's risk/roadmap detail (Baseline: "must not
 * duplicate Executive View").
 */
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  BarChart2,
  Boxes,
  Code2,
  Network,
  ScrollText,
  Sparkles,
  TrendingUp,
} from 'lucide-react'
import { fetchDashboardSummary } from '@/lib/api'

interface Props {
  assessmentId: number
  onSelectView: (viewId: string) => void
}

function KpiCard({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType
  label: string
  value: number
}) {
  return (
    <div className="flex flex-col gap-2 rounded border border-border-soft bg-surface-elevated p-4">
      <Icon className="h-4 w-4 text-brand" strokeWidth={1.75} />
      <div className="text-[22px] font-semibold text-text-primary">{value}</div>
      <div className="text-[11px] text-text-tertiary">{label}</div>
    </div>
  )
}

const RESULT_VIEWS = [
  { id: 'executive', label: 'Executive View', description: 'Riscos, recomendações macro e roadmap', icon: BarChart2 },
  { id: 'technical', label: 'Technical View', description: 'Objetos, código, findings e evidência', icon: Code2 },
  { id: 'functional', label: 'Functional View', description: 'Regras de negócio e validação', icon: ScrollText },
  { id: 'architecture', label: 'Architecture View', description: 'Aplicações, dependências e guidance SAP', icon: Network },
]

export function DashboardGeral({ assessmentId, onSelectView }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-summary', assessmentId],
    queryFn: () => fetchDashboardSummary(assessmentId),
  })

  if (isLoading) {
    return <div className="flex h-full items-center justify-center text-[12px] text-text-tertiary">Carregando…</div>
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      {data?.is_stale && (
        <div className="flex items-start gap-2 rounded border border-attention/30 bg-attention/5 px-3 py-2 text-[11px] text-attention">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Dados desatualizados — reprocesse em &quot;3 - Processamento por IA&quot; para uma síntese atual.
        </div>
      )}

      <div>
        <div className="mb-2 text-[12px] font-medium text-text-secondary">Resumo do processamento</div>
        <div className="grid grid-cols-5 gap-3">
          <KpiCard icon={Boxes} label="Objetos analisados" value={data?.objects_analyzed ?? 0} />
          <KpiCard icon={Sparkles} label="Customizações identificadas" value={data?.customizations_identified ?? 0} />
          <KpiCard icon={AlertTriangle} label="Findings críticos" value={data?.critical_findings ?? 0} />
          <KpiCard icon={TrendingUp} label="Objetos com alto impacto" value={data?.high_impact_objects ?? 0} />
          <KpiCard icon={ScrollText} label="Regras de negócio identificadas" value={data?.business_rules_identified ?? 0} />
        </div>
      </div>

      <div>
        <div className="mb-2 text-[12px] font-medium text-text-secondary">Explorar</div>
        <div className="grid grid-cols-4 gap-3">
          {RESULT_VIEWS.map(({ id, label, description, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => onSelectView(id)}
              className="flex flex-col gap-2 rounded border border-border-soft bg-surface-elevated p-4 text-left transition-colors hover:bg-surface-hover"
            >
              <Icon className="h-4 w-4 text-brand" strokeWidth={1.75} />
              <div className="text-[13px] font-medium text-text-primary">{label}</div>
              <div className="text-[11px] text-text-tertiary">{description}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
