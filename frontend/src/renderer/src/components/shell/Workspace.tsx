import { ATCImport } from '@/components/atc/ATCImport'
import { DashboardGeral } from '@/components/dashboard/DashboardGeral'
import { ExecutiveSummaryView } from '@/components/dashboard/ExecutiveSummaryView'
import { SemanticSearchPanel } from '@/components/debug/SemanticSearchPanel'
import { SourceIngestion } from '@/components/ingestion/SourceIngestion'
import { PipelineRunner } from '@/components/pipeline/PipelineRunner'
import type { AssessmentContext } from '@/lib/useClientContext'
import type { useHealth } from '@/lib/useHealth'
import type { DrillPage } from '@/lib/resultNav'
import { ConnectionIndicator } from './ConnectionIndicator'
import { NAV_ITEMS } from './Sidebar'

interface WorkspaceProps {
  activeView: string
  drill: DrillPage[]
  onDrillPush: (page: DrillPage) => void
  onDrillPopTo: (depth: number) => void
  health: ReturnType<typeof useHealth>
  ctx: AssessmentContext
}

/** Center workspace — rendered only when an assessment is open. */
export function Workspace({
  activeView,
  drill,
  onDrillPush,
  onDrillPopTo,
  health,
  ctx,
}: WorkspaceProps) {
  const { connectivity } = health
  const assessment = ctx.assessment!

  const viewLabel = NAV_ITEMS.find((i) => i.id === activeView)?.label ?? activeView
  const contextLine = `${ctx.client?.name ?? ''} / ${assessment.name}`

  return (
    <main data-region="workspace" className="flex min-w-0 flex-1 flex-col bg-surface-background">
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-border-soft px-6">
        <div className="flex items-center gap-2 text-[12px] text-text-tertiary">
          <span>Workspace</span>
          <span>/</span>
          <span className="text-text-secondary">{viewLabel}</span>
          <span>/</span>
          <span data-testid="context-breadcrumb" className="font-medium text-text-primary">
            {contextLine}
          </span>
        </div>
        <ConnectionIndicator connectivity={connectivity} />
      </div>

      <div className="flex-1 overflow-hidden">
        {activeView === 'ingestion' && <SourceIngestion assessmentId={assessment.id} />}
        {activeView === 'atc' && <ATCImport assessmentId={assessment.id} />}
        {activeView === 'ai-processing' && <PipelineRunner assessmentId={assessment.id} />}
        {activeView === 'dashboard' && (
          <DashboardGeral assessmentId={assessment.id} drill={drill} onPush={onDrillPush} onPopTo={onDrillPopTo} />
        )}
        {activeView === 'executive-summary' && <ExecutiveSummaryView assessmentId={assessment.id} />}
        {activeView === 'semantic-search' && <SemanticSearchPanel assessmentId={assessment.id} />}
      </div>
    </main>
  )
}
