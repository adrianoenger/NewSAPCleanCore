/**
 * ApplicationBrowser — Architecture View: browse custom applications discovered by the durable
 * pipeline's `application_discovery` stage (objects, business rules, findings, confidence
 * rationale), plus manual rename/move-object/merge actions (Baseline: distinguish AI
 * interpretation, evidence, and user-corrected content).
 */

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Boxes, ChevronRight, GitMerge, Pencil, Sparkles } from 'lucide-react'
import { SapGuidancePanel } from '@/components/knowledge/SapGuidancePanel'
import { SOURCE_TYPE_LABELS } from '@/components/parsing/ObjectBrowser'
import { LevelBadge, RecommendationChip, countByRecommendation } from '@/components/shared/cleanCoreDisplay'
import {
  fetchApplication,
  fetchApplications,
  mergeApplications,
  moveApplicationObject,
  renameApplication,
  type ApplicationDetailRecord,
  type ApplicationRecord,
  type CleanCoreAssessmentRecord,
} from '@/lib/api'
import type { ResultFocus } from '@/lib/resultNav'
import { cn } from '@/lib/utils'

interface Props {
  assessmentId: number
  focusApplicationId?: number | null
  onNavigate?: (target: ResultFocus) => void
  onSelectEntity?: (target: ResultFocus | null) => void
}

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

function CleanCorePanel({ cleanCore }: { cleanCore: CleanCoreAssessmentRecord | null }) {
  if (cleanCore == null) {
    return (
      <div className="rounded border border-border-soft bg-surface-elevated px-3 py-2 text-[11px] text-text-tertiary">
        Ainda não analisado pelo Clean Core. Execute &quot;3 - Processamento por IA&quot;.
      </div>
    )
  }

  if (cleanCore.status === 'FAILED') {
    return (
      <div className="rounded border border-risk/30 bg-risk/5 px-3 py-2 text-[11px] text-risk">
        Falha ao gerar a análise Clean Core: {cleanCore.error ?? 'erro desconhecido'}
      </div>
    )
  }

  return (
    <div className="space-y-3 rounded border border-border-soft bg-surface-elevated p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary">
          <Sparkles className="h-3.5 w-3.5 text-brand" strokeWidth={2} />
          Clean Core
        </div>
        {cleanCore.confidence != null && (
          <span className="rounded-full bg-surface-hover px-2 py-0.5 text-[10px] font-mono text-text-tertiary">
            confiança {Math.round(cleanCore.confidence * 100)}%
          </span>
        )}
      </div>

      {cleanCore.status === 'INSUFFICIENT_CONTEXT' && (
        <div className="rounded border border-attention/30 bg-attention/5 px-2 py-1.5 text-[11px] text-attention">
          Evidência insuficiente para determinar risco/importância.
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Risco Técnico</div>
          <div className="mt-0.5">
            <LevelBadge level={cleanCore.technical_risk} title="Risco Técnico" />
          </div>
          {cleanCore.technical_risk_rationale && (
            <div className="mt-1 text-[11px] text-text-secondary">{cleanCore.technical_risk_rationale}</div>
          )}
          {cleanCore.technical_risk_evidence_refs.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {cleanCore.technical_risk_evidence_refs.map((ref) => (
                <span
                  key={ref.ref_id}
                  title={SOURCE_TYPE_LABELS[ref.source_type] ?? ref.source_type}
                  className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary"
                >
                  {ref.ref_id}
                </span>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
            Importância de Negócio
          </div>
          <div className="mt-0.5">
            <LevelBadge level={cleanCore.business_importance} title="Importância de Negócio" />
          </div>
          {cleanCore.business_importance_rationale && (
            <div className="mt-1 text-[11px] text-text-secondary">{cleanCore.business_importance_rationale}</div>
          )}
          {cleanCore.business_importance_evidence_refs.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {cleanCore.business_importance_evidence_refs.map((ref) => (
                <span
                  key={ref.ref_id}
                  title={SOURCE_TYPE_LABELS[ref.source_type] ?? ref.source_type}
                  className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary"
                >
                  {ref.ref_id}
                </span>
              ))}
            </div>
          )}
          <div className="mt-1 text-[10px] text-text-tertiary">
            {cleanCore.business_importance_uses_process_usage_evidence
              ? '✓ considera sinais de processo/uso/perfil correlacionados'
              : 'baseada apenas na identidade dos objetos — sem sinais de processo/uso correlacionados'}
          </div>
        </div>
      </div>

      <div className="border-t border-border-soft pt-2">
        <div className="flex items-center gap-2">
          <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Recomendação</div>
          <RecommendationChip recommendation={cleanCore.recommendation} />
        </div>
        {cleanCore.recommendation_rationale && (
          <div className="mt-1 text-[11px] text-text-secondary">{cleanCore.recommendation_rationale}</div>
        )}
        {cleanCore.recommendation_evidence_refs.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {cleanCore.recommendation_evidence_refs.map((ref) => (
              <span
                key={ref.ref_id}
                title={SOURCE_TYPE_LABELS[ref.source_type] ?? ref.source_type}
                className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary"
              >
                {ref.ref_id}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function CleanCoreDistribution({ applications }: { applications: ApplicationRecord[] }) {
  const counts = countByRecommendation(applications)
  const analyzed = Object.values(counts).reduce((sum, c) => sum + c, 0)
  if (analyzed === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-1.5 border-b border-border-soft px-4 py-2">
      {Object.entries(counts).map(([recommendation, count]) => (
        <span key={recommendation} className="flex items-center gap-1">
          <RecommendationChip recommendation={recommendation} />
          <span className="text-[10px] text-text-tertiary">{count}</span>
        </span>
      ))}
    </div>
  )
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
}: {
  assessmentId: number
  member: { id: number; object_type: string; object_name: string }
  currentApplicationId: number
  candidates: ApplicationRecord[]
}) {
  const queryClient = useQueryClient()
  const moveMutation = useMutation({
    mutationFn: (targetApplicationId: number | null) =>
      moveApplicationObject(assessmentId, member.id, targetApplicationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['applications', assessmentId] }),
  })

  return (
    <div className="flex items-center justify-between gap-2 rounded bg-surface-elevated px-2 py-1.5 text-[11px]">
      <div>
        <span className="font-mono text-text-primary">{member.object_name}</span>
        <span className="ml-1.5 text-text-tertiary">{member.object_type}</span>
      </div>
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

function ApplicationDetail({
  assessmentId,
  applicationId,
  candidates,
  onNavigate,
}: {
  assessmentId: number
  applicationId: number
  candidates: ApplicationRecord[]
  onNavigate?: (target: ResultFocus) => void
}) {
  const [editing, setEditing] = useState(false)
  const { data } = useQuery<ApplicationDetailRecord>({
    queryKey: ['application-detail', assessmentId, applicationId],
    queryFn: () => fetchApplication(assessmentId, applicationId),
  })

  if (!data) return <div className="p-4 text-[12px] text-text-tertiary">Carregando…</div>

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
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
                <span className="text-text-tertiary">[{s.signal_type}]</span> {s.description}
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
            Findings ({data.findings.length})
          </div>
          <div className="space-y-1">
            {data.findings.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => onNavigate?.({ kind: 'sap_object', id: f.object_id })}
                disabled={!onNavigate}
                className="block w-full rounded bg-surface-elevated px-2 py-1.5 text-left text-[11px] hover:bg-surface-hover disabled:cursor-default disabled:hover:bg-surface-elevated"
              >
                <span className="font-medium text-text-primary">{f.check_title ?? 'Achado ATC'}</span>
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

export function ApplicationBrowser({ assessmentId, focusApplicationId, onNavigate, onSelectEntity }: Props) {
  const [selectedId, setSelectedId] = useState<number | null>(null)

  useEffect(() => {
    if (focusApplicationId != null) setSelectedId(focusApplicationId)
  }, [focusApplicationId])

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['applications', assessmentId],
    queryFn: () => fetchApplications(assessmentId),
  })

  const applications = data?.applications ?? []

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: list */}
      <div className="flex w-[420px] shrink-0 flex-col border-r border-border-default">
        <div className="flex items-center justify-between border-b border-border-soft px-4 py-3">
          <span className="text-[12px] font-medium text-text-secondary">
            Aplicações descobertas ({applications.length})
          </span>
          <button
            type="button"
            title="Atualizar"
            onClick={() => refetch()}
            className="rounded-control p-1.5 text-text-tertiary hover:bg-surface-hover hover:text-text-primary"
          >
            <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>

        <CleanCoreDistribution applications={applications} />

        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-[12px] text-text-tertiary">
              Carregando aplicações…
            </div>
          ) : applications.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
              <Boxes className="h-8 w-8 text-text-tertiary/40" strokeWidth={1.25} />
              <div className="text-[12px] text-text-tertiary">
                Nenhuma aplicação descoberta ainda. Execute &quot;3 - Processamento por IA&quot;.
              </div>
            </div>
          ) : (
            <div className="divide-y divide-border-soft">
              {applications.map((app) => (
                <button
                  key={app.id}
                  type="button"
                  onClick={() => {
                    const next = app.id === selectedId ? null : app.id
                    setSelectedId(next)
                    onSelectEntity?.(next != null ? { kind: 'application', id: next } : null)
                  }}
                  className={cn(
                    'flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors',
                    selectedId === app.id ? 'bg-surface-elevated' : 'hover:bg-surface-hover',
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12px] font-medium text-text-primary">
                      {app.name || `Aplicação #${app.id} (sem nome)`}
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={app.status} />
                      <span className="text-[10px] text-text-tertiary">{app.member_count} objeto(s)</span>
                      {app.clean_core && app.clean_core.status !== 'FAILED' && (
                        <RecommendationChip recommendation={app.clean_core.recommendation} />
                      )}
                    </div>
                  </div>
                  <ChevronRight
                    className={cn(
                      'h-3.5 w-3.5 shrink-0 text-text-tertiary transition-transform',
                      selectedId === app.id && 'rotate-90',
                    )}
                    strokeWidth={2}
                  />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Right: detail panel */}
      <div className="flex min-w-0 flex-1 flex-col bg-surface-background">
        {selectedId == null ? (
          <div className="flex flex-1 items-center justify-center text-[12px] text-text-tertiary">
            Selecione uma aplicação para ver os detalhes
          </div>
        ) : (
          <ApplicationDetail
            assessmentId={assessmentId}
            applicationId={selectedId}
            candidates={applications}
            onNavigate={onNavigate}
          />
        )}
      </div>
    </div>
  )
}
