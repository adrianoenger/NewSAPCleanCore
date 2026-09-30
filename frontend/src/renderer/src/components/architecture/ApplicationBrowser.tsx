/**
 * Application detail page (Dashboard drill-down, ADR-019): one custom application discovered by
 * the `application_discovery` stage — Clean Core conclusion, clustering rationale, member objects,
 * business rules and ATC findings — plus manual rename/move-object/merge actions (Baseline:
 * distinguish AI interpretation, evidence, and user-corrected content).
 */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { GitMerge, Pencil } from 'lucide-react'
import { SapGuidancePanel } from '@/components/knowledge/SapGuidancePanel'
import { SOURCE_TYPE_LABELS } from '@/components/shared/evidenceLabels'
import { CleanCorePanel } from '@/components/shared/cleanCoreDisplay'
import { ErrorState } from '@/components/shared/ErrorState'
import {
  fetchApplication,
  fetchApplications,
  mergeApplications,
  moveApplicationObject,
  renameApplication,
  type ApplicationDetailRecord,
  type ApplicationRecord,
} from '@/lib/api'
import type { ResultFocus } from '@/lib/resultNav'
import { cn } from '@/lib/utils'

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  CANDIDATE: { label: 'Candidata', color: 'text-text-tertiary' },
  AI_NAMED: { label: 'Nomeada pela IA', color: 'text-brand' },
  USER_RENAMED: { label: 'Renomeada pelo usuário', color: 'text-emerald-400' },
  MERGED: { label: 'Mesclada', color: 'text-text-tertiary' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, color: 'text-text-tertiary' }
  return <span className={cn('text-[10px] font-medium', cfg.color)}>{cfg.label}</span>
}

const MAX_FINDINGS_SHOWN = 100

const SIGNAL_LABELS: Record<string, string> = {
  dependency: 'dependência',
  shared_package: 'pacote comum',
  // shared_concept is no longer produced by clustering (SPRINT-18: AI concepts collapsed the
  // Rodobens cluster into one 421-object application) — kept only to render pre-existing rows.
  shared_concept: 'conceito comum',
}

function RenameForm({
  assessmentId,
  application,
  onDone,
}: {
  assessmentId: number
  application: ApplicationRecord
  onDone: () => void
}) {
  const [name, setName] = useState(application.name)
  const [description, setDescription] = useState(application.description)
  const queryClient = useQueryClient()

  const renameMutation = useMutation({
    mutationFn: () => renameApplication(assessmentId, application.id, name, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications', assessmentId] })
      queryClient.invalidateQueries({ queryKey: ['application-detail', assessmentId] })
      onDone()
    },
  })

  return (
    <div className="space-y-2 rounded border border-border-soft bg-surface-elevated p-2">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Nome da aplicação"
        className="w-full rounded-control border border-border-default bg-surface-sidebar px-2 py-1 text-[12px] text-text-primary outline-none focus:border-brand"
      />
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Descrição"
        rows={2}
        className="w-full rounded-control border border-border-default bg-surface-sidebar px-2 py-1 text-[12px] text-text-primary outline-none focus:border-brand"
      />
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onDone}
          className="rounded-control px-2 py-1 text-[11px] text-text-tertiary hover:bg-surface-hover"
        >
          Cancelar
        </button>
        <button
          type="button"
          onClick={() => renameMutation.mutate()}
          className="rounded-control border border-brand/40 px-2 py-1 text-[11px] font-medium text-brand hover:bg-brand/10"
        >
          Salvar
        </button>
      </div>
    </div>
  )
}

function MergeControl({
  assessmentId,
  application,
  candidates,
}: {
  assessmentId: number
  application: ApplicationRecord
  candidates: ApplicationRecord[]
}) {
  const [targetId, setTargetId] = useState<number | ''>('')
  const queryClient = useQueryClient()

  const mergeMutation = useMutation({
    mutationFn: (targetApplicationId: number) => mergeApplications(assessmentId, application.id, targetApplicationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications', assessmentId] })
      queryClient.invalidateQueries({ queryKey: ['application-detail', assessmentId] })
      setTargetId('')
    },
  })

  const options = candidates.filter((c) => c.id !== application.id)
  if (options.length === 0) return null

  return (
    <div className="flex items-center gap-2">
      <select
        value={targetId}
        onChange={(e) => setTargetId(e.target.value === '' ? '' : Number(e.target.value))}
        className="flex-1 rounded-control border border-border-default bg-surface-sidebar px-2 py-1 text-[11px] text-text-primary outline-none focus:border-brand"
      >
        <option value="">Mesclar com…</option>
        {options.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name || `Aplicação #${c.id}`}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={targetId === ''}
        onClick={() => targetId !== '' && mergeMutation.mutate(targetId)}
        className="flex shrink-0 items-center gap-1 rounded-control border border-border-default px-2 py-1 text-[11px] text-text-secondary hover:bg-surface-hover disabled:opacity-40"
      >
        <GitMerge className="h-3 w-3" strokeWidth={2} />
        Mesclar
      </button>
    </div>
  )
}

function MemberRow({
  assessmentId,
  member,
  currentApplicationId,
  candidates,
  onNavigate,
}: {
  assessmentId: number
  member: { id: number; object_type: string; object_name: string }
  currentApplicationId: number
  candidates: ApplicationRecord[]
  onNavigate?: (target: ResultFocus) => void
}) {
  const queryClient = useQueryClient()
  const moveMutation = useMutation({
    mutationFn: (targetApplicationId: number | null) =>
      moveApplicationObject(assessmentId, member.id, targetApplicationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['applications', assessmentId] })
      queryClient.invalidateQueries({ queryKey: ['application-detail', assessmentId] })
    },
  })

  return (
    <div className="flex items-center justify-between gap-2 rounded bg-surface-elevated px-2 py-1.5 text-[11px]">
      <button
        type="button"
        onClick={() => onNavigate?.({ kind: 'sap_object', id: member.id })}
        disabled={!onNavigate}
        className="min-w-0 truncate text-left hover:underline disabled:hover:no-underline"
      >
        <span className="font-mono text-text-primary">{member.object_name}</span>
        <span className="ml-1.5 text-text-tertiary">{member.object_type}</span>
      </button>
      <select
        value=""
        onChange={(e) => {
          if (!e.target.value) return
          moveMutation.mutate(e.target.value === 'none' ? null : Number(e.target.value))
        }}
        className="rounded-control border border-border-default bg-surface-sidebar px-1 py-0.5 text-[10px] text-text-tertiary outline-none focus:border-brand"
      >
        <option value="">Mover para…</option>
        <option value="none">Nenhuma (desagrupar)</option>
        {candidates
          .filter((c) => c.id !== currentApplicationId)
          .map((c) => (
            <option key={c.id} value={c.id}>
              {c.name || `Aplicação #${c.id}`}
            </option>
          ))}
      </select>
    </div>
  )
}

export function ApplicationDetail({
  assessmentId,
  applicationId,
  onNavigate,
}: {
  assessmentId: number
  applicationId: number
  onNavigate?: (target: ResultFocus) => void
}) {
  const [editing, setEditing] = useState(false)
  const { data, isError, refetch } = useQuery<ApplicationDetailRecord>({
    queryKey: ['application-detail', assessmentId, applicationId],
    queryFn: () => fetchApplication(assessmentId, applicationId),
  })
  const { data: list } = useQuery({
    queryKey: ['applications', assessmentId],
    queryFn: () => fetchApplications(assessmentId),
  })
  const candidates = (list?.applications ?? []).filter((c) => c.status !== 'MERGED')

  if (isError) return <ErrorState message="Não foi possível carregar a aplicação." onRetry={refetch} />
  if (!data) return <div className="p-4 text-[12px] text-text-tertiary">Carregando…</div>

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-6">
      <div className="flex items-center justify-between">
        <StatusBadge status={data.status} />
        {data.confidence != null && (
          <span className="rounded-full bg-surface-elevated px-2 py-0.5 text-[10px] font-mono text-text-tertiary">
            confiança {Math.round(data.confidence * 100)}%
          </span>
        )}
      </div>

      {editing ? (
        <RenameForm assessmentId={assessmentId} application={data} onDone={() => setEditing(false)} />
      ) : (
        <div>
          <div className="flex items-center gap-2">
            <div className="text-[15px] font-medium text-text-primary">
              {data.name || 'Aplicação sem nome (contexto insuficiente)'}
            </div>
            {data.status !== 'MERGED' && (
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="text-text-tertiary hover:text-text-primary"
                title="Renomear"
              >
                <Pencil className="h-3.5 w-3.5" strokeWidth={2} />
              </button>
            )}
          </div>
          {data.domain && <div className="text-[11px] text-text-tertiary">{data.domain}</div>}
          {data.description && <div className="mt-1 text-[13px] text-text-secondary">{data.description}</div>}
        </div>
      )}

      {data.rationale && <div className="text-[11px] italic text-text-tertiary">{data.rationale}</div>}

      <CleanCorePanel cleanCore={data.clean_core} />

      {data.clustering_signals.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
            Sinais de agrupamento
          </div>
          <ul className="space-y-0.5 text-[11px] text-text-secondary">
            {data.clustering_signals.map((s, idx) => (
              <li key={idx}>
                <span className="text-text-tertiary">[{SIGNAL_LABELS[s.signal_type] ?? s.signal_type}]</span> {s.description}
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.evidence_refs.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {data.evidence_refs.map((ref) => (
            <span
              key={ref.ref_id}
              title={SOURCE_TYPE_LABELS[ref.source_type] ?? ref.source_type}
              className="rounded bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary"
            >
              {ref.ref_id}
            </span>
          ))}
        </div>
      )}

      <div>
        <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
          Objetos ({data.member_count})
        </div>
        <div className="space-y-1">
          {data.members.map((m) => (
            <MemberRow
              key={m.id}
              assessmentId={assessmentId}
              member={m}
              currentApplicationId={data.id}
              candidates={candidates}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      </div>

      {data.business_rules.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
            Regras de negócio ({data.business_rules.length})
          </div>
          <div className="space-y-1">
            {data.business_rules.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => onNavigate?.({ kind: 'business_rule', id: r.id })}
                disabled={!onNavigate}
                className="block w-full rounded bg-surface-elevated px-2 py-1.5 text-left text-[11px] hover:bg-surface-hover disabled:cursor-default disabled:hover:bg-surface-elevated"
              >
                <span className="text-text-primary">{r.condition}</span>
                <span className="text-text-tertiary"> → {r.action}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {data.findings.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
            Findings ATC ({data.findings.length}
            {data.findings.length > MAX_FINDINGS_SHOWN ? `, exibindo ${MAX_FINDINGS_SHOWN}` : ''})
          </div>
          <div className="max-h-[420px] space-y-1 overflow-y-auto">
            {data.findings.slice(0, MAX_FINDINGS_SHOWN).map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => onNavigate?.({ kind: 'atc_finding', id: f.id })}
                disabled={!onNavigate}
                className="block w-full rounded bg-surface-elevated px-2 py-1.5 text-left text-[11px] hover:bg-surface-hover disabled:cursor-default disabled:hover:bg-surface-elevated"
              >
                <span className="font-medium text-text-primary">{f.check_title ?? 'Finding ATC'}</span>
                <span className="text-text-tertiary"> — {f.object_name}</span>
                {f.check_message && <div className="mt-0.5 text-text-tertiary">{f.check_message}</div>}
              </button>
            ))}
          </div>
        </div>
      )}

      {data.status !== 'MERGED' && (
        <div className="border-t border-border-soft pt-3">
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
            Mesclar aplicações
          </div>
          <MergeControl assessmentId={assessmentId} application={data} candidates={candidates} />
        </div>
      )}

      <SapGuidancePanel assessmentId={assessmentId} targetKind="applications" targetId={data.id} />

      {data.error && (
        <div className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[11px] text-amber-400">
          {data.error}
        </div>
      )}

      {data.provider && (
        <div className="text-[10px] text-text-tertiary">
          {data.provider} / {data.model_id} · prompt {data.prompt_capability}@{data.prompt_version}
        </div>
      )}
    </div>
  )
}
