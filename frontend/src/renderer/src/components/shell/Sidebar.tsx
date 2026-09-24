import {
  Activity,
  Boxes,
  Code2,
  LayoutDashboard,
  Network,
  ScrollText,
  Settings,
  type LucideIcon
} from 'lucide-react'
import type { Connectivity } from '@/lib/useHealth'
import { cn } from '@/lib/utils'
import { ConnectionIndicator } from './ConnectionIndicator'

export interface NavItem {
  id: string
  label: string
  icon: LucideIcon
}

// Navigation from docs/design/application-shell.md; views are implemented in later sprints.
export const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Applications / Dashboard', icon: LayoutDashboard },
  { id: 'discovery', label: 'Application Discovery', icon: Boxes },
  { id: 'architecture', label: 'Architecture & Clean Core', icon: Network },
  { id: 'rules', label: 'Business Rules', icon: ScrollText },
  { id: 'engineering', label: 'Engineering', icon: Code2 },
  { id: 'runs', label: 'Analysis Runs', icon: Activity },
  { id: 'settings', label: 'Settings', icon: Settings }
]

interface SidebarProps {
  activeId: string
  onSelect: (id: string) => void
  connectivity: Connectivity
}

export function Sidebar({ activeId, onSelect, connectivity }: SidebarProps) {
  return (
    <aside
      data-region="sidebar"
      className="flex w-[236px] shrink-0 flex-col border-r border-border-default bg-surface-sidebar"
    >
      <div className="flex h-14 items-center gap-2.5 border-b border-border-soft px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-control bg-brand text-[13px] font-medium">
          T
        </div>
        <div className="leading-tight">
          <div className="text-[13.5px] font-medium">Clean Core Analyzer</div>
          <div className="text-[11px] text-text-tertiary">SAP · PoC</div>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 p-2" aria-label="Primary">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
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
                  : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary'
              )}
            >
              {active && (
                <span className="absolute top-1.5 bottom-1.5 left-0 w-0.5 rounded-full bg-brand" />
              )}
              <Icon className={cn('h-4 w-4', active && 'text-brand-text')} strokeWidth={1.75} />
              <span className="truncate">{label}</span>
            </button>
          )
        })}
      </nav>

      <div className="space-y-1.5 border-t border-border-soft px-4 py-3">
        <div className="text-[10.5px] tracking-wide text-text-tertiary uppercase">
          No SAP system selected
        </div>
        <ConnectionIndicator connectivity={connectivity} />
      </div>
    </aside>
  )
}
