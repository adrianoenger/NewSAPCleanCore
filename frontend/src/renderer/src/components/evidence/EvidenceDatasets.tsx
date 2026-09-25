/**
 * EvidenceDatasets — "Fontes complementares / Evidências adicionais" section, embedded
 * inside Step 1 (Ingestão dos dados) per ADR-017. Optional Panaya/Signavio/HANA Sizing/
 * Readiness Check package upload, with durable import progress and correlation summary —
 * no fourth top-level step.
 */
import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Loader2,
  Trash2,
  UploadCloud,
  XCircle,
} from 'lucide-react'
import {
  createEvidenceDataset,
  deleteEvidenceDataset,
  fetchEvidenceDatasets,
  type EvidenceDatasetRecord,
  type EvidenceDatasetStatus,
} from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  assessmentId: number
}

const DATASET_TYPE_LABELS: Record<string, string> = {
  PANAYA_ETL: 'Panaya ETL',
  SIGNAVIO_PROCESS_INSIGHTS: 'SAP Signavio Process Insights',
  HANA_SIZING_REPORT: 'HANA Sizing Report',
  SAP_READINESS_CHECK: 'SAP Readiness Check',
  OTHER: 'Formato não reconhecido',
}

const STATUS_CONFIG: Record<EvidenceDatasetStatus, { label: string; color: string; icon: React.ElementType }> = {
  INSPECTED: { label: 'Inspecionado', color: 'text-text-tertiary', icon: Loader2 },
  IMPORTING: { label: 'Importando…', color: 'text-brand', icon: Loader2 },
  IMPORTED_FULL: { label: 'Importado', color: 'text-success', icon: CheckCircle2 },
  IMPORTED_PARTIAL: { label: 'Importado (parcial)', color: 'text-amber-400', icon: AlertTriangle },
  FAILED: { label: 'Falhou', color: 'text-risk', icon: XCircle },
}

const CORRELATION_LABELS: Record<string, string> = {
  MATCHED_EXACT: 'Exato',
  MATCHED_HEURISTIC: 'Heurístico',
  UNMATCHED: 'Sem correspondência',
  AMBIGUOUS: 'Ambíguo',
  NOT_APPLICABLE: 'Não aplicável',
}

const CORRELATION_COLORS: Record<string, string> = {
  MATCHED_EXACT: 'bg-emerald-500/20 text-emerald-300',
  MATCHED_HEURISTIC: 'bg-amber-500/20 text-amber-300',
  UNMATCHED: 'bg-surface-elevated text-text-tertiary',
  AMBIGUOUS: 'bg-purple-500/20 text-purple-300',
  NOT_APPLICABLE: 'bg-surface-elevated text-text-tertiary',
}

function StatusBadge({ status }: { status: EvidenceDatasetStatus }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.FAILED
  const Icon = cfg.icon
  const spinning = status === 'IMPORTING' || status === 'INSPECTED'
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-[12px] font-medium', cfg.color)}>
      <Icon className={cn('h-3.5 w-3.5', spinning && 'animate-spin')} />
      {cfg.label}
    </span>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function DatasetRow({ assessmentId, dataset }: { assessmentId: number; dataset: EvidenceDatasetRecord }) {
  const qc = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const correlationEntries = Object.entries(dataset.correlation_summary).filter(([, n]) => n > 0)

  const deleteMut = useMutation({
    mutationFn: () => deleteEvidenceDataset(assessmentId, dataset.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['evidence-datasets', assessmentId] })
    },
  })

  return (
    <div className="border-b border-border-soft last:border-b-0">
      <div className="flex w-full items-center gap-3 px-4 py-2.5 hover:bg-surface-hover">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
        >
          <ChevronRight className={cn('h-3.5 w-3.5 shrink-0 text-text-tertiary transition-transform', expanded && 'rotate-90')} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-[13px] font-medium text-text-primary">{dataset.display_name}</span>
              <span className="shrink-0 rounded bg-surface-elevated px-1.5 py-0.5 text-[10px] text-text-tertiary">
                {DATASET_TYPE_LABELS[dataset.dataset_type] ?? dataset.dataset_type}
              </span>
            </div>
            <div className="mt-0.5 text-[11px] text-text-tertiary">
              {formatBytes(dataset.source_size_bytes)} · {dataset.records_count} registros
            </div>
          </div>
        </button>
        <StatusBadge status={dataset.status} />

        {confirmingDelete ? (
          <div className="flex shrink-0 items-center gap-1.5">
            <span className="text-[11px] text-text-tertiary">Excluir?</span>
            <button
              type="button"
              onClick={() => deleteMut.mutate()}
              disabled={deleteMut.isPending}
              className="rounded px-1.5 py-0.5 text-[11px] font-medium text-risk hover:bg-risk/10"
            >
              Sim
            </button>
            <button
              type="button"
              onClick={() => setConfirmingDelete(false)}
              className="rounded px-1.5 py-0.5 text-[11px] text-text-tertiary hover:bg-surface-elevated"
            >
              Não
            </button>
          </div>
        ) : (
          <button
            type="button"
            title="Excluir fonte"
            onClick={() => setConfirmingDelete(true)}
            className="shrink-0 rounded p-1 text-text-tertiary hover:bg-risk/10 hover:text-risk"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {expanded && (
        <div className="px-4 pb-3 pl-10 text-[12px] space-y-2">
          {dataset.error && (
            <div className="flex items-start gap-2 rounded-md border border-risk/30 bg-risk/5 px-3 py-2">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-risk" />
              <p className="text-risk">{dataset.error}</p>
            </div>
          )}

          {dataset.capabilities.length > 0 && (
            <div>
              <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
                Capacidades detectadas
              </div>
              <div className="flex flex-wrap gap-1.5">
                {dataset.capabilities.map((cap) => (
                  <span key={cap} className="rounded bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-text-secondary">
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          )}

          {correlationEntries.length > 0 && (
            <div>
              <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
                Correlação com objetos SAP
              </div>
              <div className="flex flex-wrap gap-1.5">
                {correlationEntries.map(([status, count]) => (
                  <span
                    key={status}
                    className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', CORRELATION_COLORS[status] ?? 'bg-surface-elevated text-text-tertiary')}
                  >
                    {CORRELATION_LABELS[status] ?? status}: {count}
                  </span>
                ))}
              </div>
            </div>
          )}

          {dataset.warning_summary.length > 0 && (
            <div>
              <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-amber-400">Avisos</div>
              <ul className="space-y-0.5 text-text-tertiary">
                {dataset.warning_summary.slice(0, 5).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
                {dataset.warning_summary.length > 5 && <li>+{dataset.warning_summary.length - 5} mais…</li>}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function EvidenceDatasets({ assessmentId }: Props) {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['evidence-datasets', assessmentId],
    queryFn: () => fetchEvidenceDatasets(assessmentId),
    refetchInterval: (query) => {
      const datasets = query.state.data?.datasets ?? []
      const active = datasets.some((d) => d.status === 'INSPECTED' || d.status === 'IMPORTING')
      return active ? 1500 : false
    },
  })

  const uploadMut = useMutation({
    mutationFn: (file: File) => createEvidenceDataset(assessmentId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['evidence-datasets', assessmentId] })
    },
    onError: (e: Error) => setUploadError(e.message),
  })

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadError(null)
    uploadMut.mutate(file)
    if (fileRef.current) fileRef.current.value = ''
  }

  const datasets = data?.datasets ?? []

  return (
    <section className="rounded-card border border-border-default bg-surface-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-[14px] font-medium">Fontes Complementares</h2>
          <p className="mt-0.5 text-[11px] text-text-tertiary">
            Evidências adicionais opcionais — Panaya ETL, SAP Signavio Process Insights,
            HANA Sizing Report, SAP Readiness Check.
          </p>
        </div>
        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".zip,.txt,.docx"
            className="hidden"
            id="evidence-file-input"
            onChange={handleFileChange}
            disabled={uploadMut.isPending}
          />
          <label
            htmlFor="evidence-file-input"
            className={cn(
              'flex cursor-pointer items-center gap-1.5 rounded-md border border-border-default bg-surface-elevated px-3 py-1.5 text-[12px] text-text-secondary hover:border-brand/50 hover:text-text-primary',
              uploadMut.isPending && 'opacity-50 cursor-not-allowed',
            )}
          >
            {uploadMut.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <UploadCloud className="h-3.5 w-3.5" />}
            Importar pacote
          </label>
        </div>
      </div>

      {uploadError && (
        <div className="mb-3 flex items-start gap-2 rounded-md border border-risk/30 bg-risk/5 px-3 py-2">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-risk" />
          <p className="text-[12px] text-risk">{uploadError}</p>
        </div>
      )}

      {isLoading ? (
        <div className="py-6 text-center text-[12px] text-text-tertiary">Carregando…</div>
      ) : datasets.length === 0 ? (
        <div className="py-6 text-center text-[12px] text-text-tertiary">
          Nenhuma evidência complementar importada ainda.
        </div>
      ) : (
        <div className="rounded-control border border-border-soft">
          {datasets.map((d) => (
            <DatasetRow key={d.id} assessmentId={assessmentId} dataset={d} />
          ))}
        </div>
      )}
    </section>
  )
}
