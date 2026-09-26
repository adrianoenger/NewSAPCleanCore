/**
 * BusinessRuleBrowser — Functional View: browse business rules discovered by the durable
 * pipeline's `business_rule_discovery` stage, with evidence drill-down and the validation hook
 * (Baseline: distinguish AI interpretation, evidence, and user-validated content).
 */

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ChevronRight, Scale, Sparkles } from 'lucide-react'
import { SapGuidancePanel } from '@/components/knowledge/SapGuidancePanel'
import { EvidencePanel, SOURCE_TYPE_LABELS } from '@/components/parsing/ObjectBrowser'
import {
  fetchBusinessRules,
  fetchSAPObject,
  validateBusinessRule,
  type BusinessRuleRecord,
} from '@/lib/api'
import type { ResultFocus } from '@/lib/resultNav'
import { cn } from '@/lib/utils'

interface Props {
  assessmentId: number
  focusRuleId?: number | null
  onNavigate?: (target: ResultFocus) => void
}

const RULE_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  VALIDATION: { label: 'Validação', color: 'text-brand' },
  CALCULATION: { label: 'Cálculo', color: 'text-purple-400' },
  AUTHORIZATION: { label: 'Autorização', color: 'text-amber-400' },
  WORKFLOW: { label: 'Workflow', color: 'text-cyan-400' },
  DATA_INTEGRITY: { label: 'Integridade de Dados', color: 'text-emerald-400' },
  OTHER: { label: 'Outro', color: 'text-text-tertiary' },
}

function RuleTypeBadge({ type }: { type: string }) {
  const cfg = RULE_TYPE_CONFIG[type] ?? RULE_TYPE_CONFIG.OTHER
  return (
    <span className={cn('inline-flex items-center gap-1 text-[11px] font-medium', cfg.color)}>
      <Scale className="h-3 w-3" strokeWidth={2} />
      {cfg.label}
    </span>
  )
}

function RuleObjectContext({
  assessmentId,
  objectId,
  onNavigate,
}: {
  assessmentId: number
  objectId: number
  onNavigate?: (target: ResultFocus) => void
}) {
  const { data, isLoading } = useQuery({
    queryKey: ['sap-object-detail', assessmentId, objectId],
    queryFn: () => fetchSAPObject(assessmentId, objectId),
  })

  if (isLoading) return <div className="text-[11px] text-text-tertiary">Carregando objeto de origem…</div>
  if (!data) return null

  return (
    <button
      type="button"
      onClick={() => onNavigate?.({ kind: 'sap_object', id: objectId })}
      disabled={!onNavigate}
      className="w-full rounded border border-border-soft bg-surface-elevated px-3 py-2 text-left text-[11px] hover:bg-surface-hover disabled:cursor-default disabled:hover:bg-surface-elevated"
    >
      <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Objeto de origem</div>
      <div className="mt-0.5 font-mono text-[12px] text-text-primary">{data.object_name}</div>
      <div className="text-text-tertiary">
        {data.object_type} · linhas {data.line_start}
        {data.line_end != null ? `–${data.line_end}` : '+'}
      </div>
    </button>
  )
}

function RuleDetail({
  assessmentId,
  rule,
  onNavigate,
}: {
  assessmentId: number
  rule: BusinessRuleRecord
  onNavigate?: (target: ResultFocus) => void
}) {
  const queryClient = useQueryClient()
  const [notes, setNotes] = useState(rule.user_notes ?? '')

  const validateMutation = useMutation({
    mutationFn: (userValidated: boolean) =>
      validateBusinessRule(assessmentId, rule.id, userValidated, notes || null),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['business-rules', assessmentId] }),
  })

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <RuleTypeBadge type={rule.rule_type} />
        <span className="rounded-full bg-surface-elevated px-2 py-0.5 text-[10px] font-mono text-text-tertiary">
          confiança {Math.round(rule.confidence * 100)}%
        </span>
      </div>

      <div>
        <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Condição</div>
        <div className="mt-0.5 text-[13px] text-text-primary">{rule.condition}</div>
      </div>
      <div>
        <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Ação</div>
        <div className="mt-0.5 text-[13px] text-text-primary">{rule.action}</div>
      </div>
      {rule.rationale && <div className="text-[11px] italic text-text-tertiary">{rule.rationale}</div>}

      {rule.evidence_refs.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {rule.evidence_refs.map((ref) => (
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

      <RuleObjectContext assessmentId={assessmentId} objectId={rule.sap_object_id} onNavigate={onNavigate} />
      <EvidencePanel assessmentId={assessmentId} objectId={rule.sap_object_id} />
      <SapGuidancePanel assessmentId={assessmentId} targetKind="business-rules" targetId={rule.id} />

      <div className="text-[10px] text-text-tertiary">
        {rule.provider} / {rule.model_id} · prompt {rule.prompt_capability}@{rule.prompt_version}
      </div>

      <div className="space-y-2 border-t border-border-soft pt-3">
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notas de validação (opcional)"
          rows={2}
          className="w-full rounded-control border border-border-default bg-surface-sidebar px-2 py-1 text-[12px] text-text-primary outline-none focus:border-brand"
        />
        {rule.user_validated ? (
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-[11px] text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} />
              Validado pelo usuário
            </span>
            <button
              type="button"
              onClick={() => validateMutation.mutate(false)}
              className="rounded-control px-2 py-1 text-[11px] text-text-tertiary hover:bg-surface-hover hover:text-text-primary"
            >
              Remover validação
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => validateMutation.mutate(true)}
            className="flex items-center gap-1.5 rounded-control border border-brand/40 px-3 py-1.5 text-[11px] font-medium text-brand hover:bg-brand/10"
          >
            <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={2} />
            Marcar como validado
          </button>
        )}
      </div>
    </div>
  )
}

export function BusinessRuleBrowser({ assessmentId, focusRuleId, onNavigate }: Props) {
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [typeFilter, setTypeFilter] = useState('')

  useEffect(() => {
    if (focusRuleId != null) {
      setSelectedId(focusRuleId)
      setTypeFilter('')
    }
  }, [focusRuleId])

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['business-rules', assessmentId],
    queryFn: () => fetchBusinessRules(assessmentId),
  })

  const rules = data?.rules ?? []
  const filtered = typeFilter ? rules.filter((r) => r.rule_type === typeFilter) : rules
  const selected = filtered.find((r) => r.id === selectedId) ?? null

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: filter + list */}
      <div className="flex w-[420px] shrink-0 flex-col border-r border-border-default">
        <div className="flex items-center gap-2 border-b border-border-soft px-4 py-3">
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value)
              setSelectedId(null)
            }}
            className="flex-1 rounded-control border border-border-default bg-surface-sidebar px-2 py-1 text-[12px] text-text-primary outline-none focus:border-brand"
          >
            <option value="">Todos os tipos</option>
            {Object.entries(RULE_TYPE_CONFIG).map(([value, { label }]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <button
            type="button"
            title="Atualizar"
            onClick={() => refetch()}
            className="rounded-control p-1.5 text-text-tertiary hover:bg-surface-hover hover:text-text-primary"
          >
            <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>

        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-[12px] text-text-tertiary">
              Carregando regras…
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-12 text-center">
              <Scale className="h-8 w-8 text-text-tertiary/40" strokeWidth={1.25} />
              <div className="text-[12px] text-text-tertiary">
                Nenhuma regra de negócio descoberta ainda. Execute &quot;3 - Processamento por
                IA&quot;.
              </div>
            </div>
          ) : (
            <div className="divide-y divide-border-soft">
              {filtered.map((rule) => (
                <button
                  key={rule.id}
                  type="button"
                  onClick={() => setSelectedId(rule.id === selectedId ? null : rule.id)}
                  className={cn(
                    'flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors',
                    selectedId === rule.id ? 'bg-surface-elevated' : 'hover:bg-surface-hover',
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12px] font-medium text-text-primary">
                      {rule.condition}
                    </div>
                    <div className="flex items-center gap-2">
                      <RuleTypeBadge type={rule.rule_type} />
                      {rule.user_validated && (
                        <CheckCircle2 className="h-3 w-3 text-emerald-400" strokeWidth={2} />
                      )}
                    </div>
                  </div>
                  <ChevronRight
                    className={cn(
                      'h-3.5 w-3.5 shrink-0 text-text-tertiary transition-transform',
                      selectedId === rule.id && 'rotate-90',
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
        {selected == null ? (
          <div className="flex flex-1 items-center justify-center text-[12px] text-text-tertiary">
            Selecione uma regra para ver os detalhes
          </div>
        ) : (
          <RuleDetail assessmentId={assessmentId} rule={selected} onNavigate={onNavigate} />
        )}
      </div>
    </div>
  )
}
