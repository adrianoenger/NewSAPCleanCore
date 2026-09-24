import type { ReactNode } from 'react'
import { BACKEND_URL } from '@/lib/api'
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
          ok === undefined ? 'text-text-primary' : ok ? 'text-success' : 'text-risk'
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
}

/** Center workspace placeholder. Views per navigation perspective arrive in later sprints. */
export function Workspace({ viewLabel, health }: WorkspaceProps) {
  const { data, connectivity, isError, dataUpdatedAt } = health
  const db = data?.database

  return (
    <main data-region="workspace" className="flex min-w-0 flex-1 flex-col bg-surface-background">
      <div className="flex h-14 items-center justify-between border-b border-border-soft px-6">
        <div className="text-[12px] text-text-tertiary">
          Workspace <span className="px-1">/</span>
          <span className="text-text-secondary">{viewLabel}</span>
        </div>
        <ConnectionIndicator connectivity={connectivity} />
      </div>

      <div className="flex-1 overflow-auto p-6">
        <h1 className="text-[24px] font-medium">{viewLabel}</h1>
        <p className="mt-1 text-text-secondary">
          Select a client, SAP system and assessment to begin. Analysis views are delivered in
          upcoming sprints.
        </p>

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
          <StatusRow label="pgvector" value={db ? String(db.pgvector) : '—'} ok={db?.pgvector} />
          <StatusRow label="Schema revision" value={db?.migration_revision ?? '—'} />
          <StatusRow
            label="Last check"
            value={dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : '—'}
          />
        </section>
      </div>
    </main>
  )
}
