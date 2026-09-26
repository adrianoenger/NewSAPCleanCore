/**
 * SemanticSearchPanel — debug UI for SPRINT-14's assessment-scoped semantic search.
 *
 * Deliberately not one of the canonical Dashboard Geral + 4-perspective result views (Baseline
 * core rule 15) — this is the sprint's own "simple semantic search UI/debug endpoint" capability,
 * surfaced under a separate "Debug" sidebar group so it never competes with or replaces those.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, Sparkles } from 'lucide-react'
import {
  fetchSemanticSearch,
  type SemanticEntityType,
  type SemanticSearchHitRecord,
} from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  assessmentId: number
}

const ENTITY_TYPE_LABELS: Record<SemanticEntityType, string> = {
  SAP_OBJECT: 'Objeto SAP',
  APPLICATION: 'Aplicação',
  BUSINESS_RULE: 'Regra de negócio',
  EVIDENCE_RECORD: 'Evidência de processo/uso',
}

const ALL_ENTITY_TYPES = Object.keys(ENTITY_TYPE_LABELS) as SemanticEntityType[]

function EntityTypeBadge({ type }: { type: SemanticEntityType }) {
  return (
    <span className="rounded-full bg-surface-elevated px-2 py-0.5 text-[10px] font-medium text-text-tertiary">
      {ENTITY_TYPE_LABELS[type] ?? type}
    </span>
  )
}

function HitCard({ hit }: { hit: SemanticSearchHitRecord }) {
  return (
    <div className="rounded border border-border-soft bg-surface-elevated p-3">
      <div className="flex items-center justify-between gap-2">
        <EntityTypeBadge type={hit.entity_type} />
        <span className="font-mono text-[10px] text-text-tertiary">
          score {hit.score.toFixed(3)}
        </span>
      </div>
      <div className="mt-1.5 whitespace-pre-wrap text-[12px] text-text-primary">{hit.content_text}</div>
      {Object.keys(hit.metadata).length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {Object.entries(hit.metadata)
            .filter(([, v]) => v != null && v !== '')
            .map(([k, v]) => (
              <span
                key={k}
                className="rounded bg-surface-sidebar px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary"
              >
                {k}={String(v)}
              </span>
            ))}
        </div>
      )}
    </div>
  )
}

export function SemanticSearchPanel({ assessmentId }: Props) {
  const [query, setQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<SemanticEntityType[]>([])

  const { data, isFetching, error } = useQuery({
    queryKey: ['semantic-search', assessmentId, submittedQuery, typeFilter],
    queryFn: () => fetchSemanticSearch(assessmentId, submittedQuery, typeFilter),
    enabled: submittedQuery.length > 0,
  })

  const toggleType = (type: SemanticEntityType) => {
    setTypeFilter((prev) => (prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]))
  }

  return (
    <div className="flex h-full flex-col overflow-hidden p-4">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          setSubmittedQuery(query.trim())
        }}
        className="flex items-center gap-2"
      >
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-tertiary" strokeWidth={2} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por conceito de negócio (ex.: aprovação de crédito)…"
            className="w-full rounded-control border border-border-default bg-surface-sidebar py-1.5 pl-8 pr-2 text-[13px] text-text-primary outline-none focus:border-brand"
          />
        </div>
        <button
          type="submit"
          className="flex items-center gap-1.5 rounded-control border border-brand/40 px-3 py-1.5 text-[12px] font-medium text-brand hover:bg-brand/10"
        >
          <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
          Buscar
        </button>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {ALL_ENTITY_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => toggleType(type)}
            className={cn(
              'rounded-full border px-2 py-0.5 text-[11px] transition-colors',
              typeFilter.includes(type)
                ? 'border-brand/40 bg-brand/10 text-brand'
                : 'border-border-soft text-text-tertiary hover:text-text-primary',
            )}
          >
            {ENTITY_TYPE_LABELS[type]}
          </button>
        ))}
      </div>

      <div className="mt-4 flex-1 space-y-2 overflow-y-auto">
        {submittedQuery === '' ? (
          <div className="flex h-full items-center justify-center text-[12px] text-text-tertiary">
            Digite um conceito de negócio para buscar regras, aplicações, objetos e evidências de
            processo/uso desta assessment.
          </div>
        ) : isFetching ? (
          <div className="flex h-full items-center justify-center text-[12px] text-text-tertiary">
            Buscando…
          </div>
        ) : error ? (
          <div className="flex h-full items-center justify-center text-[12px] text-red-400">
            {(error as Error).message}
          </div>
        ) : data && data.results.length > 0 ? (
          data.results.map((hit) => (
            <HitCard key={`${hit.entity_type}-${hit.entity_id}`} hit={hit} />
          ))
        ) : (
          <div className="flex h-full items-center justify-center text-[12px] text-text-tertiary">
            Nenhum resultado para &quot;{submittedQuery}&quot; nesta assessment.
          </div>
        )}
      </div>
    </div>
  )
}
