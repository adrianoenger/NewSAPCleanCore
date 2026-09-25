import { useState } from 'react'
import { AssessmentsHome } from '@/components/home/AssessmentsHome'
import { CopilotPanel } from '@/components/shell/CopilotPanel'
import { NAV_ITEMS, Sidebar } from '@/components/shell/Sidebar'
import { Workspace } from '@/components/shell/Workspace'
import type { AssessmentListItem, ClientRecord } from '@/lib/api'
import type { AssessmentContext } from '@/lib/useClientContext'
import { useHealth } from '@/lib/useHealth'

/** Permanent two/three-region shell: [Sidebar?] | Main | Copilot. */
export function App() {
  const [activeView, setActiveView] = useState(NAV_ITEMS[0].id)
  const [copilotCollapsed, setCopilotCollapsed] = useState(false)
  const health = useHealth()

  const [client, setClientState] = useState<ClientRecord | null>(null)
  const [assessment, setAssessmentState] = useState<AssessmentListItem | null>(null)

  const ctx: AssessmentContext = {
    client,
    assessment,
    setClient: (c) => {
      setClientState(c)
      if (!c) setAssessmentState(null)
    },
    setAssessment: (a) => {
      setAssessmentState(a)
      if (a) setActiveView(NAV_ITEMS[0].id)
    },
  }

  const copilotContext = assessment
    ? `assessment: ${assessment.name}`
    : `home`

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar only when an assessment is open */}
      {assessment && (
        <Sidebar
          activeId={activeView}
          onSelect={setActiveView}
          connectivity={health.connectivity}
          ctx={ctx}
        />
      )}

      {/* Center region */}
      {assessment ? (
        <Workspace activeView={activeView} health={health} ctx={ctx} />
      ) : (
        <main
          data-region="workspace"
          className="flex min-w-0 flex-1 flex-col overflow-hidden bg-surface-background"
        >
          <AssessmentsHome ctx={ctx} />
        </main>
      )}

      <CopilotPanel
        collapsed={copilotCollapsed}
        onToggle={() => setCopilotCollapsed((v) => !v)}
        contextLabel={copilotContext}
      />
    </div>
  )
}
