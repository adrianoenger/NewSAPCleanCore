/**
 * ClientHub — three-step selector for Client → SAP System → Assessment.
 * Mounted in the Workspace when no assessment context is active.
 */

import { useQuery } from '@tanstack/react-query'
import { Building2, ChevronRight, Database, FileSearch } from 'lucide-react'
import {
  fetchAssessments,
  fetchClients,
  fetchSystems,
  type AssessmentRecord,
  type ClientRecord,
  type SAPSystemRecord,
} from '@/lib/api'
import type { ClientContext } from '@/lib/useClientContext'
import { cn } from '@/lib/utils'

interface ClientHubProps {
  ctx: ClientContext
}

function Card({
  active,
  onClick,
  children,
}: {
  active?: boolean
  onClick?: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full rounded-card border px-4 py-3 text-left transition-colors',
        active
          ? 'border-brand bg-surface-elevated'
          : 'border-border-default bg-surface-card hover:border-brand/40 hover:bg-surface-elevated',
      )}
    >
      {children}
    </button>
  )
}

function Section({
  icon: Icon,
  title,
  children,
  disabled,
}: {
  icon: typeof Building2
  title: string
  children: React.ReactNode
  disabled?: boolean
}) {
  return (
    <div className={cn('flex flex-col gap-2', disabled && 'pointer-events-none opacity-40')}>
      <div className="flex items-center gap-2 text-[13px] font-medium text-text-secondary">
        <Icon className="h-4 w-4" strokeWidth={1.75} />
        {title}
      </div>
      {children}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    created: 'bg-surface-elevated text-text-secondary',
    in_progress: 'bg-brand/10 text-brand-text',
    completed: 'bg-success/10 text-success',
    failed: 'bg-risk/10 text-risk',
  }
  return (
    <span
      className={cn(
        'rounded px-1.5 py-0.5 text-[11px] font-medium',
        colors[status] ?? colors.created,
      )}
    >
      {status.replace('_', ' ')}
    </span>
  )
}

export function ClientHub({ ctx }: ClientHubProps) {
  const { client, system, assessment, setClient, setSystem, setAssessment } = ctx

  const clients = useQuery({ queryKey: ['clients'], queryFn: fetchClients })
  const systems = useQuery({
    queryKey: ['systems', client?.id],
    queryFn: () => fetchSystems(client!.id),
    enabled: client != null,
  })
  const assessments = useQuery({
    queryKey: ['assessments', client?.id, system?.id],
    queryFn: () => fetchAssessments(client!.id, system!.id),
    enabled: client != null && system != null,
  })

  function pickClient(c: ClientRecord) {
    if (c.id === client?.id) return
    setClient(c)
    setSystem(null)
    setAssessment(null)
  }

  function pickSystem(s: SAPSystemRecord) {
    if (s.id === system?.id) return
    setSystem(s)
    setAssessment(null)
  }

  function pickAssessment(a: AssessmentRecord) {
    setAssessment(a)
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-[22px] font-medium">Client Hub</h1>
        <p className="mt-0.5 text-[13px] text-text-tertiary">
          Choose a client, SAP system and assessment to begin analysis.
        </p>
      </div>

      {/* Breadcrumb trail */}
      {(client || system || assessment) && (
        <div className="flex items-center gap-1 text-[12px] text-text-tertiary">
          {client && <span className="text-text-secondary">{client.name}</span>}
          {system && (
            <>
              <ChevronRight className="h-3 w-3" />
              <span className="text-text-secondary">{system.name}</span>
            </>
          )}
          {assessment && (
            <>
              <ChevronRight className="h-3 w-3" />
              <span className="text-text-primary font-medium">{assessment.name}</span>
            </>
          )}
        </div>
      )}

      <div className="grid grid-cols-[1fr_1fr_1fr] gap-4">
        {/* Step 1 — Client */}
        <Section icon={Building2} title="1. Client">
          {clients.isLoading && (
            <p className="text-[12px] text-text-tertiary">Loading…</p>
          )}
          {clients.isError && (
            <p className="text-[12px] text-risk">Failed to load clients</p>
          )}
          {clients.data?.map((c) => (
            <Card key={c.id} active={c.id === client?.id} onClick={() => pickClient(c)}>
              <div className="text-[13px] font-medium">{c.name}</div>
              {c.description && (
                <div className="mt-0.5 truncate text-[11px] text-text-tertiary">
                  {c.description}
                </div>
              )}
            </Card>
          ))}
          {clients.data?.length === 0 && (
            <p className="text-[12px] text-text-tertiary">No clients found</p>
          )}
        </Section>

        {/* Step 2 — SAP System */}
        <Section icon={Database} title="2. SAP System" disabled={!client}>
          {systems.isLoading && client && (
            <p className="text-[12px] text-text-tertiary">Loading…</p>
          )}
          {systems.data?.map((s) => (
            <Card key={s.id} active={s.id === system?.id} onClick={() => pickSystem(s)}>
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[13px] font-medium">{s.name}</span>
                {s.sid && (
                  <span className="font-mono text-[11px] text-text-tertiary">{s.sid}</span>
                )}
              </div>
              {s.description && (
                <div className="mt-0.5 truncate text-[11px] text-text-tertiary">
                  {s.description}
                </div>
              )}
            </Card>
          ))}
          {systems.data?.length === 0 && client && (
            <p className="text-[12px] text-text-tertiary">No systems found</p>
          )}
        </Section>

        {/* Step 3 — Assessment */}
        <Section icon={FileSearch} title="3. Assessment" disabled={!system}>
          {assessments.isLoading && system && (
            <p className="text-[12px] text-text-tertiary">Loading…</p>
          )}
          {assessments.data?.map((a) => (
            <Card
              key={a.id}
              active={a.id === assessment?.id}
              onClick={() => pickAssessment(a)}
            >
              <div className="text-[13px] font-medium">{a.name}</div>
              <div className="mt-1 flex items-center gap-1.5">
                <StatusBadge status={a.status} />
              </div>
              {a.description && (
                <div className="mt-0.5 truncate text-[11px] text-text-tertiary">
                  {a.description}
                </div>
              )}
            </Card>
          ))}
          {assessments.data?.length === 0 && system && (
            <p className="text-[12px] text-text-tertiary">No assessments found</p>
          )}
        </Section>
      </div>
    </div>
  )
}
