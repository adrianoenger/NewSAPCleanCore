import { useState } from 'react'
import { AssessmentsHome } from '@/components/home/AssessmentsHome'
import { CopilotPanel } from '@/components/shell/CopilotPanel'
import { NAV_ITEMS, Sidebar } from '@/components/shell/Sidebar'
import { Workspace } from '@/components/shell/Workspace'
import type { AssessmentListItem, ClientRecord } from '@/lib/api'
import { FOCUS_VIEW, type ResultFocus } from '@/lib/resultNav'
import type { AssessmentContext } from '@/lib/useClientContext'
import { useHealth } from '@/lib/useHealth'

/** Permanent two/three-region shell: [Sidebar?] | Main | Copilot. */
export function App() {
  const [activeView, setActiveView] = useState(NAV_ITEMS[0].id)
  const [focus, setFocus] = useState<ResultFocus | null>(null)
  // Plain in-view selection (SPRINT-16/ADR-010) — distinct from `focus`: clicking an object/rule/
  // application in its own browser publishes Copilot context without triggering a cross-view
  // drill-down or clearing on a manual sidebar switch's own focus reset.
  const [selection, setSelection] = useState<ResultFocus | null>(null)
  const [copilotCollapsed, setCopilotCollapsed] = useState(false)
  const health = useHealth()

  const [client, setClientState] = useState<ClientRecord | null>(null)
  const [assessment, setAssessmentState] = useState<AssessmentListItem | null>(null)

  // Sidebar navigation is a plain view switch (SPRINT-15/ADR-009); drill-down navigation
  // (navigateToFocus) additionally carries which entity the target view should pre-select.
  const selectView = (id: string) => {
    setActiveView(id)
    setFocus(null)
    setSelection(null)
  }

  const navigateToFocus = (target: ResultFocus) => {
    setFocus(target)
    setSelection(target)
    setActiveView(FOCUS_VIEW[target.kind])
  }

  const ctx: AssessmentContext = {
    client,
    assessment,
    setClient: (c) => {
      setClientState(c)
      if (!c) setAssessmentState(null)
    },
    setAssessment: (a) => {
      setAssessmentState(a)
      setFocus(null)
      setSelection(null)
      if (a) setActiveView(NAV_ITEMS[0].id)
    },
  }

  const copilotContext = assessment
    ? `assessment: ${assessment.name} · ${NAV_ITEMS.find((i) => i.id === activeView)?.label ?? activeView}`
    : `home`

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar only when an assessment is open */}
      {assessment && (
        <Sidebar
          activeId={activeView}
          onSelect={selectView}
          connectivity={health.connectivity}
          ctx={ctx}
        />
      )}

      {/* Center region */}
      {assessment ? (
        <Workspace
          activeView={activeView}
          focus={focus}
          onNavigate={navigateToFocus}
          onSelectView={selectView}
          onSelectEntity={setSelection}
          health={health}
          ctx={ctx}
        />
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
        assessmentId={assessment?.id ?? null}
        view={activeView}
        selection={selection}
        onNavigate={navigateToFocus}
      />
    </div>
  )
}
