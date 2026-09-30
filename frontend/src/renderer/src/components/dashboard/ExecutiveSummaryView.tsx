/**
 * Resumo Executivo (SPRINT-18 CAP-005) — the pt-BR markdown summary persisted by the
 * `executive_summary` pipeline stage, rendered formatted, with a synchronous "Regerar" action.
 * A FAILED regeneration keeps the last good markdown visible and shows the error above it.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, FileText, Info, RefreshCw } from 'lucide-react'
import { ErrorState } from '@/components/shared/ErrorState'
import { Markdown } from '@/components/shared/Markdown'
import { fetchExecutiveSummary, regenerateExecutiveSummary } from '@/lib/api'
import { cn } from '@/lib/utils'

export function ExecutiveSummaryView({ assessmentId }: { assessmentId: number }) {
  const queryClient = useQueryClient()
  const queryKey = ['executive-summary', assessmentId]
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey,
    queryFn: () => fetchExecutiveSummary(assessmentId),
  })
  const regenerate = useMutation({
    mutationFn: () => regenerateExecutiveSummary(assessmentId),
    onSuccess: (row) => queryClient.setQueryData(queryKey, row),
  })

  if (isLoading) return <div className="flex h-full items-center justify-center text-[12px] text-text-tertiary">Carregando…</div>
  if (isError) return <ErrorState message="Não foi possível carregar o resumo executivo." onRetry={refetch} />

  const generatedAt = data ? new Date(data.generated_at).toLocaleString('pt-BR') : null

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl space-y-4 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[15px] font-semibold text-text-primary">
              <FileText className="h-4 w-4 text-brand" strokeWidth={1.75} />
              Resumo Executivo
            </div>
            <div data-testid="executive-summary-meta" className="mt-1 text-[11px] text-text-tertiary">
              {data
                ? `Gerado em ${generatedAt} · ${data.provider ?? '—'} / ${data.model_id ?? '—'} · prompt ${data.prompt_version ?? '—'}`
                : 'Ainda não gerado — é produzido na etapa "Resumo Executivo" do processamento por IA.'}
            </div>
          </div>
          <button
            type="button"
            onClick={() => regenerate.mutate()}
            disabled={regenerate.isPending}
            className="flex h-8 shrink-0 items-center gap-1.5 rounded-control border border-border-default px-3 text-[12px] text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-60"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', regenerate.isPending && 'animate-spin')} strokeWidth={2} />
            {regenerate.isPending ? 'Gerando…' : 'Regerar'}
          </button>
        </div>

        {regenerate.isError && (
          <div className="flex items-start gap-2 rounded border border-risk/30 bg-risk/5 px-3 py-2 text-[11px] text-risk">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Falha ao regerar: {(regenerate.error as Error).message}
          </div>
        )}
        {data?.status === 'FAILED' && (
          <div className="flex items-start gap-2 rounded border border-risk/30 bg-risk/5 px-3 py-2 text-[11px] text-risk">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              A última geração falhou{data.markdown ? ' — exibindo o resumo anterior' : ''}. {data.error}
            </span>
          </div>
        )}
        {data?.status === 'INSUFFICIENT_CONTEXT' && (
          <div className="flex items-start gap-2 rounded border border-attention/30 bg-attention/5 px-3 py-2 text-[11px] text-attention">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Sem evidência suficiente para um resumo — processe o assessment primeiro.
          </div>
        )}

        {data?.markdown ? (
          <div
            data-testid="executive-summary-markdown"
            className="rounded border border-border-soft bg-surface-elevated p-6 text-[13px] text-text-secondary"
          >
            <Markdown>{data.markdown}</Markdown>
          </div>
        ) : (
          !regenerate.isPending && (
            <div className="rounded border border-dashed border-border-default p-8 text-center text-[12px] text-text-tertiary">
              Nenhum resumo disponível. Clique em &quot;Regerar&quot; para gerar agora.
            </div>
          )
        )}
      </div>
    </div>
  )
}
