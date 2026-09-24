import { ClientHub } from '@/components/hub/ClientHub'
import { SourceIngestion } from '@/components/ingestion/SourceIngestion'
import type { ClientContext } from '@/lib/useClientContext'
import type { useHealth } from '@/lib/useHealth'
import { ConnectionIndicator } from './ConnectionIndicator'

interface WorkspaceProps {
  viewLabel: string
  health: ReturnType<typeof useHealth>
  ctx: ClientContext
}

/** Center workspace. Shows Client Hub until an assessment is selected; then shows the active view. */
export function Workspace({ viewLabel, health, ctx }: WorkspaceProps) {
  const { connectivity } = health

  const contextLine = ctx.assessment
    ? `${ctx.client?.name} / ${ctx.system?.name} / ${ctx.assessment.name}`
    : ctx.system
      ? `${ctx.client?.name} / ${ctx.system.name}`
      : ctx.client
        ? ctx.client.name
        : null

  return (
    <main data-region="workspace" className="flex min-w-0 flex-1 flex-col bg-surface-background">
      <div className="flex h-14 items-center justify-between border-b border-border-soft px-6">
        <div className="flex items-center gap-2 text-[12px] text-text-tertiary">
          <span>Workspace</span>
          <span>/</span>
          <span className="text-text-secondary">{viewLabel}</span>
          {contextLine && (
            <>
              <span>/</span>
              <span data-testid="context-breadcrumb" className="text-text-primary font-medium">
                {contextLine}
              </span>
            </>
          )}
        </div>
        <ConnectionIndicator connectivity={connectivity} />
      </div>

      <div className="flex-1 overflow-auto">
        {!ctx.assessment ? (
          <ClientHub ctx={ctx} />
        ) : (
          <SourceIngestion assessmentId={ctx.assessment.id} />
        )}
      </div>
    </main>
  )
}
