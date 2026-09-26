/**
 * ObjectBrowser — browse SAP objects parsed from the current ingestion (read-only).
 * Shows object type filter, table of objects, and a side detail panel. Parsing itself
 * only happens via "3 - Processamento por IA" (SPRINT-07 consolidation).
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BookOpen, Box, Boxes, ChevronRight, Code2, Database, RefreshCw, Sparkles } from 'lucide-react'
import {
  fetchObjectDependencies,
  fetchObjectEvidenceCorrelations,
  fetchProcessingStatus,
  fetchSAPObject,
  fetchSAPObjects,
  type ObjectUnderstandingRecord,
  type SAPObjectRecord,
} from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  assessmentId: number
}

const TYPE_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  class:            { label: 'Class',           color: 'text-brand',         icon: Box },
  function_module:  { label: 'Function Module', color: 'text-purple-400',    icon: Code2 },
  report:           { label: 'Report',          color: 'text-amber-400',     icon: BookOpen },
  ddic_table:       { label: 'DDIC Table',      color: 'text-emerald-400',   icon: Database },
  ddic_domain:      { label: 'DDIC Domain',     color: 'text-cyan-400',      icon: Boxes },
}

const TYPE_FILTER_OPTIONS = [
  { value: '', label: 'All Types' },
  ...Object.entries(TYPE_CONFIG).map(([value, { label }]) => ({ value, label })),
]

function TypeBadge({ type }: { type: string }) {
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

const DEP_TYPE_LABEL: Record<string, string> = {
  CALL_FUNCTION: 'CALL FUNCTION',
  INCLUDE: 'INCLUDE',
  INHERITS_FROM: 'INHERITS FROM',
  USES_TABLE: 'USES TABLE',
}

const DEP_TYPE_COLOR: Record<string, string> = {
  CALL_FUNCTION: 'text-purple-400',
  INCLUDE: 'text-cyan-400',
  INHERITS_FROM: 'text-amber-400',
  USES_TABLE: 'text-emerald-400',
}

function DependenciesPanel({ assessmentId, objectId }: { assessmentId: number; objectId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['dependencies', assessmentId, objectId],
    queryFn: () => fetchObjectDependencies(assessmentId, objectId),
  })

  if (isLoading) return <div className="text-[11px] text-text-tertiary">Loading dependencies…</div>
  if (!data || data.total === 0) return null

  return (
    <div>
      <div className="mb-1.5 text-[11px] font-medium text-text-secondary">Dependencies ({data.total})</div>
      <div className="space-y-1">
        {data.dependencies.map((dep) => (
          <div key={dep.id} className="flex items-center gap-2 rounded bg-surface-elevated px-2 py-1 text-[11px]">
            <span className={cn('w-28 shrink-0 font-mono text-[10px]', DEP_TYPE_COLOR[dep.dep_type] ?? 'text-text-tertiary')}>
              {DEP_TYPE_LABEL[dep.dep_type] ?? dep.dep_type}
            </span>
            <span className="font-mono text-text-primary">{dep.target_name}</span>
            {dep.source_line != null && (
              <span className="ml-auto text-text-tertiary">:{dep.source_line}</span>
            )}
          </div>
        ))}
      </div>
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

  if (isLoading) return <div className="text-[11px] text-text-tertiary">Loading evidence…</div>
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

export const SOURCE_TYPE_LABELS: Record<string, string> = {
  SOURCE_CODE: 'Código-fonte',
  ATC_FINDING: 'Achado ATC',
  SUPPLEMENTAL_EVIDENCE: 'Evidência complementar',
  SAP_OBJECT: 'Objeto SAP',
  DEPENDENCY: 'Dependência detectada',
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

function ObjectDetail({ assessmentId, objectId }: { assessmentId: number; objectId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ['sap-object-detail', assessmentId, objectId],
    queryFn: () => fetchSAPObject(assessmentId, objectId),
  })

  if (isLoading)
    return <div className="p-4 text-[12px] text-text-tertiary">Loading…</div>
  if (!data)
    return null

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div>
        <div className="text-[11px] text-text-tertiary uppercase tracking-wide">Object Name</div>
        <div className="mt-0.5 font-mono text-[14px] font-semibold text-text-primary">{data.object_name}</div>
      </div>
      <TypeBadge type={data.object_type} />
      <div className="text-[11px] text-text-tertiary">
        Lines {data.line_start}{data.line_end != null ? `–${data.line_end}` : '+'}
        {' · '}file #{data.source_file_id}
      </div>
      <UnderstandingPanel understanding={data.understanding} />
      {Object.keys(data.attributes).length > 0 && (
        <div>
          <div className="mb-1.5 text-[11px] font-medium text-text-secondary">Attributes</div>
          <AttributeTable attrs={data.attributes} />
        </div>
      )}
      <DependenciesPanel assessmentId={assessmentId} objectId={objectId} />
      <EvidencePanel assessmentId={assessmentId} objectId={objectId} />
    </div>
  )
}

export function ObjectBrowser({ assessmentId }: Props) {
  const [typeFilter, setTypeFilter] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data: objects = [], isLoading, refetch } = useQuery({
    queryKey: ['sap-objects', assessmentId, typeFilter],
    queryFn: () => fetchSAPObjects(assessmentId, typeFilter || undefined),
  })

  const { data: processingStatus } = useQuery({
    queryKey: ['processingStatus', assessmentId],
    queryFn: () => fetchProcessingStatus(assessmentId),
  })

  const hasIngestion = processingStatus?.current_scan_id != null

  const grouped = TYPE_FILTER_OPTIONS.slice(1).reduce<Record<string, SAPObjectRecord[]>>((acc, { value }) => {
    acc[value] = objects.filter((o) => o.object_type === value)
    return acc
  }, {})

  const displayObjects = typeFilter ? objects : objects

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: filter + list */}
      <div className="flex w-[420px] shrink-0 flex-col border-r border-border-default">
        {/* Toolbar */}
        <div className="flex items-center gap-2 border-b border-border-soft px-4 py-3">
          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setSelectedId(null) }}
            className="flex-1 rounded-control border border-border-default bg-surface-sidebar px-2 py-1 text-[12px] text-text-primary outline-none focus:border-brand"
          >
            {TYPE_FILTER_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>

          <button
            type="button"
            title="Refresh"
            onClick={() => refetch()}
            className="rounded-control p-1.5 text-text-tertiary hover:bg-surface-hover hover:text-text-primary"
          >
            <RefreshCw className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>

        {processingStatus?.is_stale && (
          <div className="flex items-start gap-2 border-b border-border-soft bg-attention/5 px-4 py-2 text-[11px] text-attention">
            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
            Dados desatualizados — reprocesse em &quot;3 - Processamento por IA&quot;.
          </div>
        )}

        {/* Stats */}
        {objects.length > 0 && (
          <div className="flex flex-wrap gap-2 border-b border-border-soft px-4 py-2">
            {Object.entries(grouped)
              .filter(([, items]) => items.length > 0)
              .map(([type, items]) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setTypeFilter(typeFilter === type ? '' : type)}
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] transition-colors',
                    typeFilter === type
                      ? 'border-brand bg-brand/10 text-brand'
                      : 'border-border-soft text-text-tertiary hover:border-brand/50',
                  )}
                >
                  {TYPE_CONFIG[type]?.label ?? type}
                  <span className="font-mono">{items.length}</span>
                </button>
              ))}
          </div>
        )}

        {/* List */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-[12px] text-text-tertiary">
              Loading objects…
            </div>
          ) : displayObjects.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
              <Boxes className="h-8 w-8 text-text-tertiary/40" strokeWidth={1.25} />
              <div className="text-[12px] text-text-tertiary">
                {hasIngestion
                  ? 'Nenhum objeto processado ainda. Execute "3 - Processamento por IA".'
                  : 'Execute a ingestão (Passo 1) e o processamento (Passo 3) primeiro.'}
              </div>
            </div>
          ) : (
            <div className="divide-y divide-border-soft">
              {displayObjects.map((obj) => (
                <button
                  key={obj.id}
                  type="button"
                  onClick={() => setSelectedId(obj.id === selectedId ? null : obj.id)}
                  className={cn(
                    'flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors',
                    selectedId === obj.id
                      ? 'bg-surface-elevated'
                      : 'hover:bg-surface-hover',
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-mono text-[12px] font-medium text-text-primary">
                      {obj.object_name}
                    </div>
                    <TypeBadge type={obj.object_type} />
                  </div>
                  <ChevronRight
                    className={cn(
                      'h-3.5 w-3.5 shrink-0 text-text-tertiary transition-transform',
                      selectedId === obj.id && 'rotate-90',
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
            Select an object to view details
          </div>
        ) : (
          <ObjectDetail assessmentId={assessmentId} objectId={selectedId} />
        )}
      </div>
    </div>
  )
}
