/**
 * SapGuidancePanel — SPRINT-12 "SAP Guidance" block for a finding/application detail view
 * (Baseline: SAP knowledge via MCP enriches local analysis, ADR-007). The fetch is always an
 * explicit user action ("Consultar orientação SAP") — never automatic on every open, so browsing
 * an assessment never triggers indiscriminate MCP calls.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpen, Loader2, RefreshCw } from 'lucide-react'
import {
  fetchSapGuidance,
  requestSapGuidance,
  type SapKnowledgeTargetKind,
} from '@/lib/api'

interface Props {
  assessmentId: number
  targetKind: SapKnowledgeTargetKind
  targetId: number
}

export function SapGuidancePanel({ assessmentId, targetKind, targetId }: Props) {
  const queryClient = useQueryClient()
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const queryKey = ['sap-guidance', assessmentId, targetKind, targetId]

  const { data, isLoading } = useQuery({
    queryKey,
    queryFn: () => fetchSapGuidance(assessmentId, targetKind, targetId),
  })

  const requestMutation = useMutation({
    mutationFn: () => requestSapGuidance(assessmentId, targetKind, targetId),
    onSuccess: (result) => {
      setErrorMsg(null)
      queryClient.setQueryData(queryKey, result)
    },
    onError: (e: Error) => setErrorMsg(e.message),
  })

  const references = data?.references ?? []

  return (
    <div className="border-t border-border-soft pt-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
          <BookOpen className="h-3 w-3" strokeWidth={2} />
          Orientação SAP
        </div>
        <button
          type="button"
          onClick={() => requestMutation.mutate()}
          disabled={requestMutation.isPending}
          className="flex items-center gap-1.5 rounded-control border border-border-default px-2 py-1 text-[11px] text-text-secondary hover:bg-surface-hover disabled:opacity-50"
        >
          {requestMutation.isPending ? (
            <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
          ) : (
            <RefreshCw className="h-3 w-3" strokeWidth={2} />
          )}
          Consultar SAP Docs
        </button>
      </div>

      {isLoading && <p className="text-[11px] text-text-tertiary">Carregando…</p>}

      {!isLoading && references.length === 0 && !requestMutation.isPending && (
        <p className="text-[11px] text-text-tertiary">
          Nenhuma orientação consultada ainda. Use &quot;Consultar SAP Docs&quot; para enriquecer
          com mcp-sap-docs/mcp-abap.
        </p>
      )}

      {errorMsg && <p className="text-[11px] text-red-300">{errorMsg}</p>}

      {references.length > 0 && (
        <div className="space-y-1.5">
          {references.map((ref) => (
            <div key={ref.id} className="rounded bg-surface-elevated px-2 py-1.5 text-[11px]">
              <div className="font-medium text-text-primary">{ref.title}</div>
              {ref.summary && <div className="mt-0.5 text-text-tertiary">{ref.summary}</div>}
              <div className="mt-1 text-[10px] text-text-tertiary">
                {ref.provider} · {ref.reference} · {new Date(ref.retrieved_at).toLocaleString('pt-BR')}
                {ref.reused && ' · reaproveitado'}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
