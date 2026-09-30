/**
 * Business rule detail page (Dashboard drill-down, ADR-019): one rule discovered by the
 * `business_rule_discovery` stage, with evidence drill-down and the validation hook (Baseline:
 * distinguish AI interpretation, evidence, and user-validated content).
 */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Scale } from 'lucide-react'
import { SapGuidancePanel } from '@/components/knowledge/SapGuidancePanel'
import { EvidencePanel } from '@/components/parsing/ObjectBrowser'
import { SOURCE_TYPE_LABELS } from '@/components/shared/evidenceLabels'
import { ErrorState } from '@/components/shared/ErrorState'
import {
  fetchBusinessRules,
  fetchSAPObject,
  validateBusinessRule,
  type BusinessRuleRecord,
} from '@/lib/api'
import type { ResultFocus } from '@/lib/resultNav'
import { cn } from '@/lib/utils'

export const RULE_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  VALIDATION: { label: 'Validação', color: 'text-brand' },
  CALCULATION: { label: 'Cálculo', color: 'text-purple-400' },
  AUTHORIZATION: { label: 'Autorização', color: 'text-amber-400' },
  WORKFLOW: { label: 'Workflow', color: 'text-cyan-400' },
  DATA_INTEGRITY: { label: 'Integridade de Dados', color: 'text-emerald-400' },
  OTHER: { label: 'Outro', color: 'text-text-tertiary' },
}

export function RuleTypeBadge({ type }: { type: string }) {
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
    <div className="mx-auto max-w-5xl space-y-4 p-6">
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

export function RuleDetailPage({
  assessmentId,
  ruleId,
  onNavigate,
}: {
  assessmentId: number
  ruleId: number
  onNavigate?: (target: ResultFocus) => void
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['business-rules', assessmentId],
    queryFn: () => fetchBusinessRules(assessmentId),
  })
  if (isLoading) return <div className="p-6 text-[12px] text-text-tertiary">Carregando…</div>
  if (isError) return <ErrorState message="Não foi possível carregar a regra de negócio." onRetry={refetch} />
  const rule = data?.rules.find((r) => r.id === ruleId)
  if (!rule) return <div className="p-6 text-[12px] text-text-tertiary">Regra não encontrada (pode ter sido consolidada).</div>
  return <RuleDetail key={rule.id} assessmentId={assessmentId} rule={rule} onNavigate={onNavigate} />
}
