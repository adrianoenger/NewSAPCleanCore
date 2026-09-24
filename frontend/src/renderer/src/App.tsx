import { useState } from 'react'
import { CopilotPanel } from '@/components/shell/CopilotPanel'
import { NAV_ITEMS, Sidebar } from '@/components/shell/Sidebar'
import { Workspace } from '@/components/shell/Workspace'
import { useHealth } from '@/lib/useHealth'

/** Permanent three-region shell: Sidebar | Main Workspace | AI Copilot. */
export function App() {
  const [activeView, setActiveView] = useState(NAV_ITEMS[0].id)
  const [copilotCollapsed, setCopilotCollapsed] = useState(false)
  const health = useHealth()
  const viewLabel = NAV_ITEMS.find((item) => item.id === activeView)?.label ?? activeView

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar
        activeId={activeView}
        onSelect={setActiveView}
        connectivity={health.connectivity}
      />
      <Workspace viewLabel={viewLabel} health={health} />
      <CopilotPanel
        collapsed={copilotCollapsed}
        onToggle={() => setCopilotCollapsed((value) => !value)}
        contextLabel={`view: ${activeView}`}
      />
    </div>
  )
}
