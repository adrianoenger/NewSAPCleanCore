import { useState } from 'react'
import { AssessmentsHome } from '@/components/home/AssessmentsHome'
import { CopilotPanel } from '@/components/shell/CopilotPanel'
import { ResizeHandle } from '@/components/shell/ResizeHandle'
import { NAV_ITEMS, Sidebar } from '@/components/shell/Sidebar'
import { Workspace } from '@/components/shell/Workspace'
import type { AssessmentListItem, ClientRecord } from '@/lib/api'
import { COPILOT_SELECTION_KINDS, type DrillPage, type ResultFocus } from '@/lib/resultNav'
import type { AssessmentContext } from '@/lib/useClientContext'
import { useHealth } from '@/lib/useHealth'
import { useResizableWidth } from '@/lib/useResizableWidth'

/** Permanent two/three-region shell: [Sidebar?] | Main | Copilot. */
export function App() {
  const [activeView, setActiveView] = useState('dashboard')
  // Dashboard drill-down stack (SPRINT-18/ADR-019): lives here, not in DashboardGeral, so Copilot
  // navigation from any view can open a detail page inside the Dashboard.
  const [drill, setDrill] = useState<DrillPage[]>([])
  const [copilotCollapsed, setCopilotCollapsed] = useState(false)
  const health = useHealth()

  const sidebar = useResizableWidth({
    storageKey: 'cca.layout.sidebarWidth',
    defaultWidth: 236,
    min: 200,
    max: 400,
    direction: 'left',
  })
  const copilot = useResizableWidth({
    storageKey: 'cca.layout.copilotWidth',
    defaultWidth: 400,
    min: 320,
    max: 640,
    direction: 'right',
  })

  const [client, setClientState] = useState<ClientRecord | null>(null)
  const [assessment, setAssessmentState] = useState<AssessmentListItem | null>(null)

  const selectView = (id: string) => {
    setActiveView(id)
    setDrill([])
  }

  const pushDrill = (page: DrillPage) => {
    setDrill((stack) => {
      const top = stack[stack.length - 1]
      if (top?.type === 'detail' && page.type === 'detail' && top.focus.kind === page.focus.kind && top.focus.id === page.focus.id)
        return stack
      return [...stack, page]
    })
  }

  const navigateToFocus = (target: ResultFocus) => {
    if (activeView !== 'dashboard') {
      setActiveView('dashboard')
      setDrill([{ type: 'detail', focus: target }])
    } else {
      pushDrill({ type: 'detail', focus: target })
    }
  }

  // Copilot context = the detail page currently open in the Dashboard, when the Copilot's context
  // builder understands that entity kind (ai/copilot/context.py).
  const topPage = drill[drill.length - 1]
  const selection =
    activeView === 'dashboard' && topPage?.type === 'detail' && COPILOT_SELECTION_KINDS.has(topPage.focus.kind)
      ? topPage.focus
      : null

  const ctx: AssessmentContext = {
    client,
    assessment,
    setClient: (c) => {
      setClientState(c)
      if (!c) setAssessmentState(null)
    },
    setAssessment: (a) => {
      setAssessmentState(a)
      setDrill([])
      if (a) setActiveView('dashboard')
    },
  }

  const copilotContext = assessment
    ? `assessment: ${assessment.name} · ${NAV_ITEMS.find((i) => i.id === activeView)?.label ?? activeView}`
    : `home`

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar only when an assessment is open */}
      {assessment && (
        <>
          <Sidebar
            activeId={activeView}
            onSelect={selectView}
            connectivity={health.connectivity}
            ctx={ctx}
            width={sidebar.width}
          />
          <ResizeHandle
            onPointerDown={sidebar.onPointerDown}
            isDragging={sidebar.isDragging}
            label="Redimensionar barra lateral"
          />
        </>
      )}

      {/* Center region */}
      {assessment ? (
        <Workspace
          activeView={activeView}
          drill={drill}
          onDrillPush={pushDrill}
          onDrillPopTo={(depth) => setDrill((stack) => stack.slice(0, depth))}
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

      {!copilotCollapsed && (
        <ResizeHandle
          onPointerDown={copilot.onPointerDown}
          isDragging={copilot.isDragging}
          label="Redimensionar painel do Copilot"
        />
      )}
      <CopilotPanel
        collapsed={copilotCollapsed}
        onToggle={() => setCopilotCollapsed((v) => !v)}
        contextLabel={copilotContext}
        assessmentId={assessment?.id ?? null}
        view={activeView}
        selection={selection}
        onNavigate={navigateToFocus}
        width={copilot.width}
      />
    </div>
  )
}
