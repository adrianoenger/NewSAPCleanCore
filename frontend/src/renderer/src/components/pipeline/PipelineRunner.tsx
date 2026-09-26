/**
 * PipelineRunner — "3 - Processamento por IA": durable multi-stage processing
 * (ADR-005: scan → parse → detect dependencies), consolidated onto Step 1's
 * ingestion (SPRINT-07) — no directory picker here, it always processes the
 * current (latest completed) ingestion for this Assessment.
 *
 * Demonstrates: auto-detect current ingestion, start, pause, resume (including
 * after a backend restart, via orphan recovery on startup), retry of a
 * deliberately failed work item, and staleness after a newer ingestion.
 */

import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Loader2,
  Pause,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Inbox,
} from 'lucide-react'
import {
  fetchPipelineRuns,
  fetchPipelineWorkItems,
  fetchProcessingStatus,
  pausePipelineRun,
  resumePipelineRun,
  retryWorkItem,
  startPipelineRun,
  type PipelineRunRecord,
  type StageRunRecord,
} from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  assessmentId: number
}

const STAGE_LABELS: Record<string, string> = {
  scan: 'Scan de Arquivos',
  parse: 'Parsing de Objetos',
  detect_dependencies: 'Detecção de Dependências',
  object_understanding: 'Entendimento por IA',
  business_rule_discovery: 'Descoberta de Regras de Negócio',
  application_discovery: 'Descoberta de Aplicações',
  clean_core_analysis: 'Análise Clean Core',
}

const RUN_LABELS: Record<PipelineRunRecord['status'], string> = {
  pending: 'Aguardando início…',
  running: 'Em execução…',
  paused: 'Pausado',
  completed: 'Concluído',
  failed: 'Falhou',
}

function RunStatusIcon({ status }: { status: PipelineRunRecord['status'] }) {
  if (status === 'completed') return <CheckCircle2 className="h-4 w-4 text-success" />
  if (status === 'failed') return <XCircle className="h-4 w-4 text-risk" />
  if (status === 'paused') return <Pause className="h-4 w-4 text-text-tertiary" />
  return <Loader2 className="h-4 w-4 animate-spin text-brand" />
}

function StageProgress({ stage }: { stage: StageRunRecord }) {
  const pct = stage.total_items > 0 ? Math.round((stage.completed_items / stage.total_items) * 100) : 0
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-[12px]">
        <span className="font-medium text-text-primary">{STAGE_LABELS[stage.stage_key] ?? stage.stage_key}</span>
        <span
          className={cn(
            'rounded px-1.5 py-0.5 text-[10px] font-medium',
            stage.status === 'completed' && 'bg-success/15 text-success',
            stage.status === 'failed' && 'bg-risk/15 text-risk',
            stage.status === 'running' && 'bg-brand/15 text-brand-text',
            (stage.status === 'pending' || stage.status === 'paused' || stage.status === 'skipped') &&
              'bg-surface-elevated text-text-tertiary',
          )}
        >
          {stage.status}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated">
        <div
          className={cn('h-full rounded-full transition-all duration-300', stage.failed_items > 0 ? 'bg-risk' : 'bg-brand')}
          style={{ width: stage.total_items > 0 ? `${pct}%` : '0%' }}
        />
      </div>
      <div className="flex items-center gap-2 text-[11px] text-text-tertiary">
        <span className="font-mono text-text-secondary">
          {stage.completed_items}/{stage.total_items}
        </span>
        {stage.failed_items > 0 && <span className="text-risk">{stage.failed_items} com falha</span>}
      </div>
    </div>
  )
}

export function PipelineRunner({ assessmentId }: Props) {
  const queryClient = useQueryClient()
  const [activeRunId, setActiveRunId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const prevScanIdRef = useRef<number | null | undefined>(undefined)

  const isRunActive = (runs: PipelineRunRecord[]) =>
    runs.some((r) => r.status === 'running' || r.status === 'pending')

  const runsQuery = useQuery({
    queryKey: ['pipelineRuns', assessmentId],
    queryFn: () => fetchPipelineRuns(assessmentId),
    refetchInterval: (query) => (isRunActive(query.state.data?.runs ?? []) ? 1500 : false),
  })

  // Keep processing-status in sync while a run is active, so the "desatualizado"
  // banner clears as soon as the run it was waiting on finishes.
  const statusQuery = useQuery({
    queryKey: ['processingStatus', assessmentId],
    queryFn: () => fetchProcessingStatus(assessmentId),
    refetchInterval: isRunActive(runsQuery.data?.runs ?? []) ? 1500 : false,
  })
  const processingStatus = statusQuery.data

  // Whenever the current ingestion changes (a new scan supersedes the previous
  // one), drop the selection so the effect below re-picks the run for it.
  useEffect(() => {
    const currentScanId = processingStatus?.current_scan_id ?? null
    if (prevScanIdRef.current !== undefined && prevScanIdRef.current !== currentScanId) {
      setActiveRunId(null)
    }
    prevScanIdRef.current = currentScanId
  }, [processingStatus?.current_scan_id])

  useEffect(() => {
    if (activeRunId != null) return
    const runs = runsQuery.data?.runs ?? []
    if (runs.length === 0) return
    const currentScanId = processingStatus?.current_scan_id ?? null
    const preferred = currentScanId != null ? runs.find((r) => r.source_scan_id === currentScanId) : undefined
    setActiveRunId(preferred?.id ?? runs[0].id)
  }, [runsQuery.data, activeRunId, processingStatus?.current_scan_id])

  const activeRun = runsQuery.data?.runs.find((r) => r.id === activeRunId) ?? null

  const failedItemsQuery = useQuery({
    queryKey: ['pipelineFailedItems', assessmentId, activeRunId],
    queryFn: () => fetchPipelineWorkItems(assessmentId, activeRunId!, { status: 'failed' }),
    enabled: activeRunId != null && activeRun?.status === 'failed',
  })

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ['processingStatus', assessmentId] })
    await queryClient.invalidateQueries({ queryKey: ['pipelineRuns', assessmentId] })
    await queryClient.invalidateQueries({ queryKey: ['pipelineFailedItems', assessmentId, activeRunId] })
  }

  async function handleStart() {
    const sourcePath = processingStatus?.current_scan_source_path
    if (!sourcePath) return
    setBusy(true)
    setActionError(null)
    try {
      const run = await startPipelineRun(assessmentId, sourcePath)
      setActiveRunId(run.id)
      await refresh()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handlePause() {
    if (activeRunId == null) return
    setBusy(true)
    setActionError(null)
    try {
      await pausePipelineRun(assessmentId, activeRunId)
      await refresh()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleResume() {
    if (activeRunId == null) return
    setBusy(true)
    setActionError(null)
    try {
      await resumePipelineRun(assessmentId, activeRunId)
      await refresh()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleRetryItem(itemId: number) {
    if (activeRunId == null) return
    setBusy(true)
    setActionError(null)
    try {
      await retryWorkItem(assessmentId, activeRunId, itemId)
      await refresh()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const hasIngestion = processingStatus?.current_scan_id != null
  const canStart = !busy && hasIngestion && activeRun?.status !== 'running'
  const canPause = !busy && activeRun?.status === 'running'
  const canResume = !busy && (activeRun?.status === 'paused' || activeRun?.status === 'failed')
  const startLabel = processingStatus?.is_processed ? 'Reprocessar' : 'Iniciar Processamento'

  return (
    <div className="h-full overflow-y-auto">
      <div className="flex flex-col gap-6 p-6">
        <div>
          <h1 className="text-[22px] font-medium">3 - Processamento por IA</h1>
          <p className="mt-0.5 text-[13px] text-text-tertiary">
            Execução durável (scan → parsing → dependências → entendimento por IA) sobre a ingestão atual, com
            pausa, retomada e recuperação após reinício.
          </p>
        </div>

        {statusQuery.isLoading && (
          <p className="text-[13px] text-text-tertiary">Carregando status…</p>
        )}

        {!statusQuery.isLoading && !hasIngestion && (
          <section className="flex flex-col items-center gap-2 rounded-card border border-border-default bg-surface-card p-8 text-center">
            <Inbox className="h-6 w-6 text-text-tertiary" />
            <p className="text-[14px] font-medium text-text-secondary">Nenhuma ingestão concluída ainda</p>
            <p className="text-[12px] text-text-tertiary">
              Volte ao passo <span className="font-medium">1 - Ingestão dos dados</span> e escaneie um diretório
              antes de processar.
            </p>
          </section>
        )}

        {processingStatus && hasIngestion && (
          <section className="rounded-card border border-border-default bg-surface-card p-4">
            <h2 className="mb-3 text-[14px] font-medium">Ingestão Atual</h2>
            <p className="mb-3 font-mono text-[11px] text-text-tertiary">
              {processingStatus.current_scan_source_path}
            </p>

            {processingStatus.is_stale && (
              <div className="mb-3 flex items-start gap-2 rounded-md border border-attention/30 bg-attention/5 px-3 py-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-attention" />
                <p className="text-[12px] text-attention">
                  Desatualizado — esta ingestão ainda não foi processada. Inicie o processamento para atualizar os
                  resultados.
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={handleStart}
              disabled={!canStart}
              className="flex items-center gap-1.5 rounded-md bg-brand px-4 py-2 text-[13px] font-medium text-white hover:bg-brand/90 disabled:opacity-50"
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {startLabel}
            </button>

            {actionError && (
              <div className="mt-2 flex items-start gap-2 rounded-md border border-risk/30 bg-risk/5 px-3 py-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-risk" />
                <p className="text-[12px] text-risk">{actionError}</p>
              </div>
            )}
          </section>
        )}

        {/* Active run */}
        {activeRun && (
          <section className="rounded-card border border-border-default bg-surface-card p-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <RunStatusIcon status={activeRun.status} />
                <h2 className="text-[14px] font-medium">{RUN_LABELS[activeRun.status]}</h2>
              </div>
              <div className="flex items-center gap-2">
                {canPause && (
                  <button
                    type="button"
                    onClick={handlePause}
                    className="flex items-center gap-1.5 rounded-md border border-border-default px-3 py-1.5 text-[12px] text-text-secondary hover:border-brand/50 hover:text-text-primary"
                  >
                    <Pause className="h-3.5 w-3.5" />
                    Pausar
                  </button>
                )}
                {canResume && (
                  <button
                    type="button"
                    onClick={handleResume}
                    className="flex items-center gap-1.5 rounded-md bg-brand px-3 py-1.5 text-[12px] font-medium text-white hover:bg-brand/90"
                  >
                    <Play className="h-3.5 w-3.5" />
                    Retomar
                  </button>
                )}
              </div>
            </div>

            <p className="mb-3 font-mono text-[11px] text-text-tertiary">{activeRun.source_path}</p>

            <div className="flex flex-col gap-4">
              {activeRun.stages.map((stage) => (
                <StageProgress key={stage.id} stage={stage} />
              ))}
            </div>

            {activeRun.error && (
              <div className="mt-3 flex items-start gap-2 rounded-md border border-risk/30 bg-risk/5 px-3 py-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-risk" />
                <p className="text-[12px] text-risk">{activeRun.error}</p>
              </div>
            )}

            {/* Failed items */}
            {failedItemsQuery.data && failedItemsQuery.data.items.length > 0 && (
              <div className="mt-4 border-t border-border-soft pt-3">
                <h3 className="mb-2 text-[12px] font-medium text-text-secondary">
                  Itens com falha ({failedItemsQuery.data.total})
                </h3>
                <div className="flex flex-col gap-1.5">
                  {failedItemsQuery.data.items.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between gap-2 rounded-md border border-risk/20 bg-risk/5 px-3 py-2"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-mono text-[11px] text-text-primary">{item.item_key}</p>
                        {item.last_error && (
                          <p className="truncate text-[11px] text-risk">{item.last_error}</p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRetryItem(item.id)}
                        disabled={busy}
                        className="flex shrink-0 items-center gap-1 rounded-md border border-border-default px-2 py-1 text-[11px] text-text-secondary hover:border-brand/50 hover:text-text-primary disabled:opacity-50"
                      >
                        <RotateCcw className="h-3 w-3" />
                        Retry
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {/* Run history */}
        {runsQuery.data && runsQuery.data.runs.length > 1 && (
          <section className="rounded-card border border-border-default bg-surface-card p-4">
            <h2 className="mb-3 text-[14px] font-medium">Histórico de Execuções</h2>
            <div className="flex flex-col gap-1.5">
              {runsQuery.data.runs.map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => setActiveRunId(r.id)}
                  className={cn(
                    'flex items-center gap-2 rounded-md px-3 py-2 text-left text-[12px] transition-colors',
                    r.id === activeRunId
                      ? 'bg-brand/10 text-brand-text'
                      : 'hover:bg-surface-elevated text-text-secondary',
                  )}
                >
                  <RunStatusIcon status={r.status} />
                  <span className="font-mono flex-1 truncate">{r.source_path}</span>
                  <span className="text-text-tertiary">{RUN_LABELS[r.status]}</span>
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
