/**
 * SAP object detail page (Dashboard drill-down, ADR-019): source, AI understanding, dependencies,
 * supplemental evidence, the owning Application's Clean Core conclusion (objects inherit it,
 * ADR-018), the object's ATC findings from the current run and its business rules.
 */

import { useQuery } from '@tanstack/react-query'
import { BookOpen, Box, Boxes, Code2, Database, Layers, Sparkles } from 'lucide-react'
import { RuleTypeBadge } from '@/components/functional/BusinessRuleBrowser'
import { CleanCorePanel, RecommendationChip } from '@/components/shared/cleanCoreDisplay'
import { SOURCE_TYPE_LABELS } from '@/components/shared/evidenceLabels'
import { ErrorState } from '@/components/shared/ErrorState'
import { DependencyGraph } from '@/components/parsing/DependencyGraph'
import { SourceViewer } from '@/components/parsing/SourceViewer'
import {
  fetchApplication,
  fetchBusinessRules,
  fetchCurrentATCFindings,
  fetchObjectEvidenceCorrelations,
  fetchSAPObject,
  type ObjectUnderstandingRecord,
} from '@/lib/api'
import type { ResultFocus } from '@/lib/resultNav'
import { cn } from '@/lib/utils'

export const TYPE_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  class:            { label: 'Classe',          color: 'text-brand',         icon: Box },
  function_module:  { label: 'Módulo de função', color: 'text-purple-400',    icon: Code2 },
  report:           { label: 'Programa',        color: 'text-amber-400',     icon: BookOpen },
  ddic_table:       { label: 'Tabela DDIC',     color: 'text-emerald-400',   icon: Database },
  ddic_domain:      { label: 'Domínio DDIC',    color: 'text-cyan-400',      icon: Boxes },
}

export function TypeBadge({ type }: { type: string }) {
  const cfg = TYPE_CONFIG[type]
  const Icon = cfg?.icon ?? Box
  return (
    <span className={cn('inline-flex items-center gap-1 text-[11px] font-medium', cfg?.color ?? 'text-text-secondary')}>
      <Icon className="h-3 w-3" strokeWidth={2} />
      {cfg?.label ?? type}
    </span>
  )
}

function AttributeTable({ attrs }: { attrs: Record<string, unknown> }) {
  return (
    <div className="space-y-2 text-[12px]">
      {Object.entries(attrs).map(([key, val]) => (
        <div key={key}>
          <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">{key}</div>
          {Array.isArray(val) ? (
            <ul className="mt-0.5 space-y-0.5">
              {(val as string[]).map((v, i) => (
                <li key={i} className="rounded bg-surface-elevated px-2 py-0.5 font-mono text-text-secondary">
                  {v}
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-0.5 rounded bg-surface-elevated px-2 py-0.5 font-mono text-text-secondary">
              {String(val)}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

const CORRELATION_LABELS: Record<string, string> = {
  MATCHED_EXACT: 'Exato',
  MATCHED_HEURISTIC: 'Heurístico',
  UNMATCHED: 'Sem correspondência',
  AMBIGUOUS: 'Ambíguo',
  NOT_APPLICABLE: 'Não aplicável',
}

const DATASET_TYPE_LABELS: Record<string, string> = {
  PANAYA_ETL: 'Panaya ETL',
  SIGNAVIO_PROCESS_INSIGHTS: 'SAP Signavio Process Insights',
  HANA_SIZING_REPORT: 'HANA Sizing Report',
  SAP_READINESS_CHECK: 'SAP Readiness Check',
  OTHER: 'Evidência complementar',
}

export function EvidencePanel({ assessmentId, objectId }: { assessmentId: number; objectId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['object-evidence-correlations', assessmentId, objectId],
    queryFn: () => fetchObjectEvidenceCorrelations(assessmentId, objectId),
  })

  if (isLoading) return <div className="text-[11px] text-text-tertiary">Carregando evidências…</div>
  if (!data || data.total === 0) return null

  return (
    <div>
      <div className="mb-1.5 text-[11px] font-medium text-text-secondary">Evidência Suplementar ({data.total})</div>
      <div className="space-y-1">
        {data.correlations.map((corr) => (
          <div key={corr.id} className="rounded bg-surface-elevated px-2 py-1.5 text-[11px]">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-text-primary">
                {DATASET_TYPE_LABELS[corr.dataset_type] ?? corr.dataset_type}
              </span>
              <span className="shrink-0 text-[10px] text-text-tertiary">
                {CORRELATION_LABELS[corr.status] ?? corr.status}
              </span>
            </div>
            <div className="mt-0.5 font-mono text-[10px] text-text-tertiary">
              {corr.evidence_record.record_type} · {corr.evidence_record.capability}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}


function UnderstandingPanel({ understanding }: { understanding: ObjectUnderstandingRecord | null }) {
  if (understanding == null) {
    return (
      <div className="rounded border border-border-soft bg-surface-elevated px-3 py-2 text-[11px] text-text-tertiary">
        Ainda não processado por IA. Execute &quot;3 - Processamento por IA&quot;.
      </div>
    )
  }

  if (understanding.status === 'FAILED') {
    return (
      <div className="rounded border border-risk/30 bg-risk/5 px-3 py-2 text-[11px] text-risk">
        Falha ao gerar entendimento por IA: {understanding.error ?? 'erro desconhecido'}
      </div>
    )
  }

  if (understanding.status === 'INSUFFICIENT_CONTEXT') {
    return (
      <div className="rounded border border-attention/30 bg-attention/5 px-3 py-2 text-[11px] text-attention">
        Evidência insuficiente para o provedor de IA determinar a finalidade deste objeto.
      </div>
    )
  }

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary">
          <Sparkles className="h-3.5 w-3.5 text-brand" strokeWidth={2} />
          Entendimento por IA
        </div>
        {understanding.confidence != null && (
          <span className="rounded-full bg-surface-elevated px-2 py-0.5 text-[10px] font-mono text-text-tertiary">
            confiança {Math.round(understanding.confidence * 100)}%
          </span>
        )}
      </div>

      {understanding.functional_purpose && (
        <div>
          <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Propósito Funcional</div>
          <div className="mt-0.5 text-[12px] text-text-primary">{understanding.functional_purpose}</div>
        </div>
      )}
      {understanding.technical_purpose && (
        <div>
          <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Propósito Técnico</div>
          <div className="mt-0.5 text-[12px] text-text-primary">{understanding.technical_purpose}</div>
        </div>
      )}
      {understanding.concepts.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {understanding.concepts.map((c) => (
            <span key={c} className="rounded-full border border-border-soft px-2 py-0.5 text-[10px] text-text-secondary">
              {c}
            </span>
          ))}
        </div>
      )}
      {understanding.rationale && (
        <div className="text-[11px] italic text-text-tertiary">{understanding.rationale}</div>
      )}
      {understanding.evidence_refs.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {understanding.evidence_refs.map((ref) => (
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
      <div className="text-[10px] text-text-tertiary">
        {understanding.provider} / {understanding.model_id} · prompt {understanding.prompt_capability}@
        {understanding.prompt_version}
      </div>
    </div>
  )
}

const PRIORITY_CONFIG: Record<number, { label: string; color: string }> = {
  1: { label: 'P1', color: 'bg-[#c0392b]/15 text-[#e74c3c]' },
  2: { label: 'P2', color: 'bg-[#d68910]/15 text-[#f39c12]' },
  3: { label: 'P3', color: 'bg-[#7f8c8d]/15 text-[#95a5a6]' },
}

export function PriorityBadge({ priority }: { priority: number | null }) {
  const cfg = priority != null ? PRIORITY_CONFIG[priority] : undefined
  return (
    <span
      className={cn(
        'inline-block rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold',
        cfg?.color ?? 'bg-surface-elevated text-text-tertiary',
      )}
    >
      {cfg?.label ?? 'P?'}
    </span>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <div className="mb-1.5 text-[11px] font-medium text-text-secondary">{children}</div>
}

/** The owning Application's Clean Core conclusion — objects inherit it (ADR-018), so this surfaces
 * the application's evidence-bound assessment rather than a second, competing AI field. */
function ApplicationCleanCore({
  assessmentId,
  applicationId,
  onNavigate,
}: {
  assessmentId: number
  applicationId: number
  onNavigate?: (target: ResultFocus) => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['application-detail', assessmentId, applicationId],
    queryFn: () => fetchApplication(assessmentId, applicationId),
  })
  if (isLoading) return <div className="text-[11px] text-text-tertiary">Carregando aplicação…</div>
  if (!data) return null

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => onNavigate?.({ kind: 'application', id: applicationId })}
        disabled={!onNavigate}
        className="flex w-full items-center justify-between gap-2 rounded border border-border-soft bg-surface-elevated px-3 py-2 text-left text-[11px] hover:bg-surface-hover disabled:cursor-default disabled:hover:bg-surface-elevated"
      >
        <span className="flex min-w-0 items-center gap-1.5">
          <Layers className="h-3.5 w-3.5 shrink-0 text-brand" strokeWidth={2} />
          <span className="text-text-tertiary">Aplicação:</span>
          <span className="truncate font-medium text-text-primary">{data.name || `Aplicação #${applicationId}`}</span>
        </span>
        <RecommendationChip recommendation={data.clean_core?.recommendation ?? null} />
      </button>
      <CleanCorePanel cleanCore={data.clean_core} />
    </div>
  )
}

function ObjectATCFindings({
  assessmentId,
  objectId,
  onNavigate,
}: {
  assessmentId: number
  objectId: number
  onNavigate?: (target: ResultFocus) => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['atc-findings', assessmentId, { object_id: objectId }],
    queryFn: () => fetchCurrentATCFindings(assessmentId, { object_id: objectId, limit: 200 }),
  })
  if (isLoading) return <div className="text-[11px] text-text-tertiary">Carregando findings ATC…</div>
  if (!data || data.total === 0)
    return (
      <div>
        <SectionTitle>Findings ATC</SectionTitle>
        <div className="text-[11px] text-text-tertiary">Nenhum finding ATC correlacionado a este objeto.</div>
      </div>
    )

  return (
    <div>
      <SectionTitle>
        Findings ATC ({data.total}
        {data.total > data.items.length ? `, exibindo ${data.items.length}` : ''})
      </SectionTitle>
      <div className="max-h-[360px] space-y-1 overflow-y-auto">
        {data.items.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => onNavigate?.({ kind: 'atc_finding', id: f.id })}
            disabled={!onNavigate}
            className="flex w-full items-start gap-2 rounded bg-surface-elevated px-2 py-1.5 text-left text-[11px] hover:bg-surface-hover disabled:cursor-default disabled:hover:bg-surface-elevated"
          >
            <PriorityBadge priority={f.priority} />
            <span className="min-w-0">
              <span className="font-medium text-text-primary">{f.check_title ?? 'Finding ATC'}</span>
              {f.check_message && <span className="block truncate text-text-tertiary">{f.check_message}</span>}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}

function ObjectBusinessRules({
  assessmentId,
  objectId,
  onNavigate,
}: {
  assessmentId: number
  objectId: number
  onNavigate?: (target: ResultFocus) => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['business-rules', assessmentId, objectId],
    queryFn: () => fetchBusinessRules(assessmentId, objectId),
  })
  if (isLoading) return <div className="text-[11px] text-text-tertiary">Carregando regras de negócio…</div>
  if (!data || data.rules.length === 0) return null

  return (
    <div>
      <SectionTitle>Regras de negócio ({data.rules.length})</SectionTitle>
      <div className="space-y-1">
        {data.rules.map((r) => (
          <button
            key={r.id}
            type="button"
            onClick={() => onNavigate?.({ kind: 'business_rule', id: r.id })}
            disabled={!onNavigate}
            className="block w-full rounded bg-surface-elevated px-2 py-1.5 text-left text-[11px] hover:bg-surface-hover disabled:cursor-default disabled:hover:bg-surface-elevated"
          >
            <RuleTypeBadge type={r.rule_type} />
            <div className="mt-0.5">
              <span className="text-text-primary">{r.condition}</span>
              <span className="text-text-tertiary"> → {r.action}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

export function ObjectDetail({
  assessmentId,
  objectId,
  onNavigate,
}: {
  assessmentId: number
  objectId: number
  onNavigate?: (target: ResultFocus) => void
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['sap-object-detail', assessmentId, objectId],
    queryFn: () => fetchSAPObject(assessmentId, objectId),
  })

  if (isLoading) return <div className="p-6 text-[12px] text-text-tertiary">Carregando…</div>
  if (isError) return <ErrorState message="Não foi possível carregar o objeto SAP." onRetry={refetch} />
  if (!data) return null

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-6">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-text-tertiary">Nome do objeto</div>
        <div className="mt-0.5 font-mono text-[16px] font-semibold text-text-primary">{data.object_name}</div>
        <div className="mt-1 flex items-center gap-3">
          <TypeBadge type={data.object_type} />
          <span className="text-[11px] text-text-tertiary">
            Linhas {data.line_start}
            {data.line_end != null ? `–${data.line_end}` : '+'}
            {' · '}arquivo #{data.source_file_id}
          </span>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="space-y-5">
          <UnderstandingPanel understanding={data.understanding} />
          {data.application_id != null ? (
            <ApplicationCleanCore
              assessmentId={assessmentId}
              applicationId={data.application_id}
              onNavigate={onNavigate}
            />
          ) : (
            <div className="rounded border border-border-soft bg-surface-elevated px-3 py-2 text-[11px] text-text-tertiary">
              Objeto não agrupado em uma aplicação — sem classificação Clean Core.
            </div>
          )}
        </div>
        <div className="space-y-5">
          <ObjectATCFindings assessmentId={assessmentId} objectId={objectId} onNavigate={onNavigate} />
          <ObjectBusinessRules assessmentId={assessmentId} objectId={objectId} onNavigate={onNavigate} />
          <EvidencePanel assessmentId={assessmentId} objectId={objectId} />
          {Object.keys(data.attributes).length > 0 && (
            <div>
              <SectionTitle>Atributos</SectionTitle>
              <AttributeTable attrs={data.attributes} />
            </div>
          )}
        </div>
      </div>

      <SourceViewer assessmentId={assessmentId} objectId={objectId} />
      <DependencyGraph assessmentId={assessmentId} object={data} />
    </div>
  )
}
