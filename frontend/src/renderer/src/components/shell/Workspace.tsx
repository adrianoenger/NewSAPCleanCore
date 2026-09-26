import { ApplicationBrowser } from '@/components/architecture/ApplicationBrowser'
import { ATCImport } from '@/components/atc/ATCImport'
import { DashboardGeral } from '@/components/dashboard/DashboardGeral'
import { ExecutiveView } from '@/components/dashboard/ExecutiveView'
import { SemanticSearchPanel } from '@/components/debug/SemanticSearchPanel'
import { BusinessRuleBrowser } from '@/components/functional/BusinessRuleBrowser'
import { SourceIngestion } from '@/components/ingestion/SourceIngestion'
import { ObjectBrowser } from '@/components/parsing/ObjectBrowser'
import { PipelineRunner } from '@/components/pipeline/PipelineRunner'
import type { AssessmentContext } from '@/lib/useClientContext'
import type { useHealth } from '@/lib/useHealth'
import type { ResultFocus } from '@/lib/resultNav'
import { ConnectionIndicator } from './ConnectionIndicator'
import { NAV_ITEMS } from './Sidebar'

interface WorkspaceProps {
  activeView: string
  focus: ResultFocus | null
  onNavigate: (target: ResultFocus) => void
  onSelectView: (viewId: string) => void
  health: ReturnType<typeof useHealth>
  ctx: AssessmentContext
}

/** Center workspace — rendered only when an assessment is open. */
export function Workspace({ activeView, focus, onNavigate, onSelectView, health, ctx }: WorkspaceProps) {
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
        {activeView === 'technical' && (
          <ObjectBrowser
            assessmentId={assessment.id}
            focusObjectId={focus?.kind === 'sap_object' ? focus.id : null}
            onNavigate={onNavigate}
          />
        )}
        {activeView === 'atc' && <ATCImport assessmentId={assessment.id} />}
        {activeView === 'ai-processing' && <PipelineRunner assessmentId={assessment.id} />}
        {activeView === 'dashboard' && (
          <DashboardGeral assessmentId={assessment.id} onSelectView={onSelectView} />
        )}
        {activeView === 'executive' && (
          <ExecutiveView assessmentId={assessment.id} onNavigate={onNavigate} />
        )}
        {activeView === 'functional' && (
          <BusinessRuleBrowser
            assessmentId={assessment.id}
            focusRuleId={focus?.kind === 'business_rule' ? focus.id : null}
            onNavigate={onNavigate}
          />
        )}
        {activeView === 'architecture' && (
          <ApplicationBrowser
            assessmentId={assessment.id}
            focusApplicationId={focus?.kind === 'application' ? focus.id : null}
            onNavigate={onNavigate}
          />
        )}
        {activeView === 'semantic-search' && <SemanticSearchPanel assessmentId={assessment.id} />}
      </div>
    </main>
  )
}
