import type { ReactNode } from 'react'
import { ClientHub } from '@/components/hub/ClientHub'
import { BACKEND_URL } from '@/lib/api'
import type { ClientContext } from '@/lib/useClientContext'
import type { useHealth } from '@/lib/useHealth'
import { cn } from '@/lib/utils'
import { ConnectionIndicator } from './ConnectionIndicator'

function StatusRow({ label, value, ok }: { label: string; value: ReactNode; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-border-soft py-2 last:border-b-0">
      <span className="text-text-secondary">{label}</span>
      <span
        className={cn(
          'font-mono text-[12px]',
          ok === undefined ? 'text-text-primary' : ok ? 'text-success' : 'text-risk',
        )}
      >
        {value}
      </span>
    </div>
  )
}

interface WorkspaceProps {
  viewLabel: string
  health: ReturnType<typeof useHealth>
  ctx: ClientContext
}

/** Center workspace. Shows Client Hub until an assessment is selected; then shows the active view. */
export function Workspace({ viewLabel, health, ctx }: WorkspaceProps) {
  const { data, connectivity, isError, dataUpdatedAt } = health
  const db = data?.database

  // Top context breadcrumb
  const contextLine = ctx.assessment
    ? `${ctx.client?.name} / ${ctx.system?.name} / ${ctx.assessment.name}`
    : ctx.system
      ? `${ctx.client?.name} / ${ctx.system.name}`
      : ctx.client
        ? ctx.client.name
        : null

  return (
    <main data-region="workspace" className="flex min-w-0 flex-1 flex-col bg-surface-background">
      {/* Top bar */}
      <div className="flex h-14 items-center justify-between border-b border-border-soft px-6">
        <div className="flex items-center gap-2 text-[12px] text-text-tertiary">
          <span>Workspace</span>
          <span>/</span>
          <span className="text-text-secondary">{viewLabel}</span>
          {contextLine && (
            <>
              <span>/</span>
              <span
                data-testid="context-breadcrumb"
                className="text-text-primary font-medium"
              >
                {contextLine}
              </span>
            </>
          )}
        </div>
        <ConnectionIndicator connectivity={connectivity} />
      </div>

      <div className="flex-1 overflow-auto">
        {/* No assessment selected → show Client Hub */}
        {!ctx.assessment ? (
          <ClientHub ctx={ctx} />
        ) : (
          /* Assessment selected → placeholder for future sprint views */
          <div className="p-6">
            <h1 className="text-[24px] font-medium">{viewLabel}</h1>
            <p className="mt-1 text-text-secondary">
              Assessment: <strong>{ctx.assessment.name}</strong>
              {' · '}
              {ctx.system?.name}
              {' · '}
              {ctx.client?.name}
            </p>
            <p className="mt-2 text-[13px] text-text-tertiary">
              Analysis views for this perspective are delivered in upcoming sprints.
            </p>

            {/* Platform health card (always visible as foundation reference) */}
            <section
              data-testid="health-card"
              className="mt-6 max-w-xl rounded-card border border-border-default bg-surface-card p-4"
            >
              <h2 className="mb-2 text-[14px] font-medium">Platform health</h2>
              <StatusRow label="Backend" value={BACKEND_URL} ok={connectivity !== 'offline'} />
              <StatusRow
                label="API"
                value={data ? `${data.service} v${data.version}` : isError ? 'unreachable' : '…'}
                ok={data ? true : isError ? false : undefined}
              />
              <StatusRow
                label="Database"
                value={db?.status ?? '—'}
                ok={db ? db.status === 'ok' : undefined}
              />
              <StatusRow
                label="pgvector"
                value={db ? String(db.pgvector) : '—'}
                ok={db?.pgvector}
              />
              <StatusRow label="Schema revision" value={db?.migration_revision ?? '—'} />
              <StatusRow
                label="Last check"
                value={dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : '—'}
              />
            </section>
          </div>
        )}
      </div>
    </main>
  )
}
