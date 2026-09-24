import { useState } from 'react'
import { CopilotPanel } from '@/components/shell/CopilotPanel'
import { NAV_ITEMS, Sidebar } from '@/components/shell/Sidebar'
import { Workspace } from '@/components/shell/Workspace'
import type { AssessmentRecord, ClientRecord, SAPSystemRecord } from '@/lib/api'
import type { ClientContext } from '@/lib/useClientContext'
import { useHealth } from '@/lib/useHealth'

/** Permanent three-region shell: Sidebar | Main Workspace | AI Copilot. */
export function App() {
  const [activeView, setActiveView] = useState(NAV_ITEMS[0].id)
  const [copilotCollapsed, setCopilotCollapsed] = useState(false)
  const health = useHealth()
  const viewLabel = NAV_ITEMS.find((item) => item.id === activeView)?.label ?? activeView

  // Client / SAP System / Assessment selection state (SPRINT-01)
  const [client, setClientState] = useState<ClientRecord | null>(null)
  const [system, setSystemState] = useState<SAPSystemRecord | null>(null)
  const [assessment, setAssessmentState] = useState<AssessmentRecord | null>(null)

  const ctx: ClientContext = {
    client,
    system,
    assessment,
    setClient: (c) => {
      setClientState(c)
      if (!c) {
        setSystemState(null)
        setAssessmentState(null)
      }
    },
    setSystem: (s) => {
      setSystemState(s)
      if (!s) setAssessmentState(null)
    },
    setAssessment: setAssessmentState,
  }

  return (
    <div className="flex h-full overflow-hidden">
      <Sidebar
        activeId={activeView}
        onSelect={setActiveView}
        connectivity={health.connectivity}
        ctx={ctx}
      />
      <Workspace viewLabel={viewLabel} health={health} ctx={ctx} />
      <CopilotPanel
        collapsed={copilotCollapsed}
        onToggle={() => setCopilotCollapsed((value) => !value)}
        contextLabel={
          assessment
            ? `assessment: ${assessment.name}`
            : system
              ? `system: ${system.name}`
              : client
                ? `client: ${client.name}`
                : `view: ${activeView}`
        }
      />
    </div>
  )
}
