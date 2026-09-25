import {
  BarChart2,
  ChevronLeft,
  Code2,
  LayoutDashboard,
  Network,
  ScrollText,
  type LucideIcon,
  UploadCloud,
  Cpu,
  BarChart3,
} from 'lucide-react'
import type { AssessmentContext } from '@/lib/useClientContext'
import type { Connectivity } from '@/lib/useHealth'
import { cn } from '@/lib/utils'
import { ConnectionIndicator } from './ConnectionIndicator'

export interface NavItem {
  id: string
  label: string
  icon: LucideIcon
  group: 'clean-core' | 'resultado'
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'ingestion', label: '1 - Ingestão dos dados', icon: UploadCloud, group: 'clean-core' },
  { id: 'atc', label: '2 - Análise ATC', icon: ScrollText, group: 'clean-core' },
  { id: 'ai-processing', label: '3 - Processamento por IA', icon: Cpu, group: 'clean-core' },
  { id: 'dashboard', label: 'Dashboard Geral', icon: LayoutDashboard, group: 'resultado' },
  { id: 'executive', label: 'Executive View', icon: BarChart2, group: 'resultado' },
  { id: 'technical', label: 'Technical View', icon: Code2, group: 'resultado' },
  { id: 'functional', label: 'Functional View', icon: BarChart3, group: 'resultado' },
  { id: 'architecture', label: 'Architecture View', icon: Network, group: 'resultado' },
]

interface SidebarProps {
  activeId: string
  onSelect: (id: string) => void
  connectivity: Connectivity
  ctx: AssessmentContext
}

function GroupLabel({ label }: { label: string }) {
  return (
    <div className="px-2.5 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
      {label}
    </div>
  )
}

export function Sidebar({ activeId, onSelect, connectivity, ctx }: SidebarProps) {
  const { assessment, client } = ctx

  const cleanCoreItems = NAV_ITEMS.filter((i) => i.group === 'clean-core')
  const resultadoItems = NAV_ITEMS.filter((i) => i.group === 'resultado')

  return (
    <aside
      data-region="sidebar"
      className="flex w-[236px] shrink-0 flex-col border-r border-border-default bg-surface-sidebar"
    >
      {/* Logo / title — click to go home */}
      <button
        type="button"
        onClick={() => ctx.setAssessment(null)}
        className="flex h-14 w-full items-center gap-2.5 border-b border-border-soft px-4 hover:bg-surface-hover transition-colors"
        title="Voltar para lista de assessments"
      >
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control bg-brand text-[13px] font-medium">
          T
        </div>
        <div className="leading-tight text-left">
          <div className="text-[13.5px] font-medium">Clean Core Analyzer</div>
          <div className="text-[11px] text-text-tertiary">SAP · PoC</div>
        </div>
      </button>

      {/* Assessment context + back button */}
      <div className="border-b border-border-soft px-4 py-3">
        <button
          type="button"
          onClick={() => ctx.setAssessment(null)}
          className="mb-2 flex items-center gap-1 text-[11px] text-text-tertiary hover:text-text-primary transition-colors"
        >
          <ChevronLeft className="h-3 w-3" strokeWidth={2} />
          Todos os assessments
        </button>
        <div
          data-testid="sidebar-context"
          className="truncate text-[12px] font-medium text-text-primary"
        >
          {assessment?.name ?? '—'}
        </div>
        <div className="truncate text-[11px] text-text-tertiary">{client?.name ?? ''}</div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-2" aria-label="Assessment">
        <GroupLabel label="Clean Core" />
        {cleanCoreItems.map(({ id, label, icon: Icon }) => {
          const active = id === activeId
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id)}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'relative flex h-8 w-full items-center gap-2.5 rounded-control px-2.5 text-left text-[13px] transition-colors',
                active
                  ? 'bg-surface-elevated text-text-primary'
                  : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary',
              )}
            >
              {active && (
                <span className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full bg-brand" />
              )}
              <Icon className={cn('h-4 w-4 shrink-0', active && 'text-brand-text')} strokeWidth={1.75} />
              <span className="truncate">{label}</span>
            </button>
          )
        })}

        <GroupLabel label="Resultado" />
        {resultadoItems.map(({ id, label, icon: Icon }) => {
          const active = id === activeId
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSelect(id)}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'relative flex h-8 w-full items-center gap-2.5 rounded-control px-2.5 text-left text-[13px] transition-colors',
                active
                  ? 'bg-surface-elevated text-text-primary'
                  : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary',
              )}
            >
              {active && (
                <span className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full bg-brand" />
              )}
              <Icon className={cn('h-4 w-4 shrink-0', active && 'text-brand-text')} strokeWidth={1.75} />
              <span className="truncate">{label}</span>
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-border-soft px-4 py-3">
        <ConnectionIndicator connectivity={connectivity} />
      </div>
    </aside>
  )
}
