/**
 * ATCImport — SPRINT-05 "2 - Análise ATC" workspace panel.
 *
 * Flow: select XLSX → inspect diagnostics → confirm import → view runs/findings.
 */
import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileSpreadsheet,
  Loader2,
  UploadCloud,
  XCircle,
} from 'lucide-react'
import {
  fetchATCRuns,
  fetchATCFindings,
  importATCFile,
  inspectATCFile,
  type ATCDiagnostics,
  type ATCRunRecord,
} from '@/lib/api'
import { ErrorState } from '@/components/shared/ErrorState'
import { cn } from '@/lib/utils'

interface Props {
  assessmentId: number
}

type Phase = 'idle' | 'inspecting' | 'inspected' | 'importing' | 'done' | 'error'

const STATUS_COLOR: Record<string, string> = {
  ACCEPTED_FULL: 'text-emerald-400',
  ACCEPTED_PARTIAL: 'text-amber-400',
  REJECTED: 'text-red-400',
}

const PRIORITY_COLOR: Record<number, string> = {
  1: 'bg-red-500/20 text-red-300',
  2: 'bg-amber-500/20 text-amber-300',
  3: 'bg-blue-500/20 text-blue-300',
}

function ValidationBadge({ status }: { status: string }) {
  const color = STATUS_COLOR[status] ?? 'text-text-secondary'
  const Icon = status === 'ACCEPTED_FULL' ? CheckCircle2 : status === 'REJECTED' ? XCircle : AlertTriangle
  const label = status === 'ACCEPTED_FULL' ? 'Full' : status === 'ACCEPTED_PARTIAL' ? 'Partial' : 'Rejected'
  return (
    <span className={cn('inline-flex items-center gap-1 text-[12px] font-semibold', color)}>
      <Icon className="h-3.5 w-3.5" />
      {label}
    </span>
  )
}

function DiagnosticsCard({ diag }: { diag: ATCDiagnostics }) {
  return (
    <div className="rounded-control border border-border-default bg-surface-elevated p-4 space-y-3 text-[12px]">
      <div className="flex items-center justify-between">
        <span className="font-semibold text-text-primary text-[13px]">Diagnóstico do arquivo</span>
        <ValidationBadge status={diag.validation_status} />
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1">
        <Row label="Planilha" value={diag.worksheet || '—'} />
        <Row label="Linhas de dados" value={String(diag.total_rows)} />
        <Row label="Colunas reconhecidas" value={String(diag.recognized_columns.length)} />
        <Row label="Colunas desconhecidas" value={String(diag.unknown_columns.length)} />
      </div>
      {diag.missing_known_columns.length > 0 && (
        <Section title="Colunas ausentes" items={diag.missing_known_columns} color="text-amber-400" />
      )}
      {diag.unknown_columns.length > 0 && (
        <Section title="Colunas desconhecidas" items={diag.unknown_columns} color="text-text-secondary" />
      )}
      {diag.warnings.length > 0 && (
        <div>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-amber-400">Avisos</p>
          <ul className="space-y-0.5">
            {diag.warnings.slice(0, 5).map((w, i) => (
              <li key={i} className="text-text-tertiary">{w}</li>
            ))}
            {diag.warnings.length > 5 && (
              <li className="text-text-tertiary">+{diag.warnings.length - 5} mais…</li>
            )}
          </ul>
        </div>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span className="text-text-tertiary">{label}</span>
      <span className="font-medium text-text-primary">{value}</span>
    </>
  )
}

function Section({ title, items, color }: { title: string; items: string[]; color: string }) {
  return (
    <div>
      <p className={cn('mb-1 text-[10px] font-semibold uppercase tracking-wide', color)}>{title}</p>
      <div className="flex flex-wrap gap-1">
        {items.map((it) => (
          <span key={it} className="rounded bg-surface-background px-1.5 py-0.5 font-mono text-[11px] text-text-secondary">
            {it}
          </span>
        ))}
      </div>
    </div>
  )
}

function RunRow({ run, assessmentId }: { run: ATCRunRecord; assessmentId: number }) {
  const [expanded, setExpanded] = useState(false)
  const { data: findingsData, isLoading } = useQuery({
    queryKey: ['atc-findings', assessmentId, run.id],
    queryFn: () => fetchATCFindings(assessmentId, run.id, 50),
    enabled: expanded,
  })

  const date = new Date(run.imported_at).toLocaleString('pt-BR')

  return (
    <div className="rounded-control border border-border-default bg-surface-elevated">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-[12px]"
      >
        {expanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
        <FileSpreadsheet className="h-4 w-4 text-text-tertiary" />
        <span className="flex-1 truncate font-medium text-text-primary">{run.source_filename}</span>
        <ValidationBadge status={run.validation_status} />
        <span className="ml-4 text-text-tertiary">{run.imported_row_count} findings</span>
        <span className="ml-4 text-text-tertiary">{date}</span>
      </button>

      {expanded && (
        <div className="border-t border-border-soft px-4 pb-3">
          {/* Correlation summary */}
          {findingsData && (
            <div className="mt-3 mb-2 flex gap-3 text-[11px]">
              {Object.entries(findingsData.correlation_summary).map(([k, v]) => (
                <span key={k} className="rounded bg-surface-background px-2 py-0.5">
                  <span className="text-text-tertiary">{k}: </span>
                  <span className="font-semibold text-text-primary">{v}</span>
                </span>
              ))}
            </div>
          )}
          {/* Findings table */}
          {isLoading && <p className="py-2 text-[12px] text-text-tertiary">Carregando…</p>}
          {findingsData && findingsData.findings.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b border-border-soft text-text-tertiary">
                    <th className="py-1 pr-3 text-left font-medium">P</th>
                    <th className="py-1 pr-3 text-left font-medium">Objeto</th>
                    <th className="py-1 pr-3 text-left font-medium">Tipo</th>
                    <th className="py-1 pr-3 text-left font-medium">Check</th>
                    <th className="py-1 pr-3 text-left font-medium">Correlação</th>
                  </tr>
                </thead>
                <tbody>
                  {findingsData.findings.slice(0, 50).map((f) => (
                    <tr key={f.id} className="border-b border-border-soft/50 hover:bg-surface-hover">
                      <td className="py-1 pr-3">
                        {f.priority != null && (
                          <span className={cn('rounded px-1 py-0.5 text-[10px] font-bold', PRIORITY_COLOR[f.priority] ?? 'bg-surface-background text-text-secondary')}>
                            P{f.priority}
                          </span>
                        )}
                      </td>
                      <td className="py-1 pr-3 font-mono text-text-secondary">{f.object_name_raw ?? '—'}</td>
                      <td className="py-1 pr-3 text-text-tertiary">{f.object_type_raw ?? '—'}</td>
                      <td className="py-1 pr-3 text-text-secondary truncate max-w-[200px]">{f.check_title ?? '—'}</td>
                      <td className="py-1 pr-3">
                        <span className={cn('rounded px-1 py-0.5 text-[10px]', {
                          'bg-emerald-500/20 text-emerald-300': f.correlation_status === 'MATCHED_EXACT',
                          'bg-blue-500/20 text-blue-300': f.correlation_status === 'MATCHED_HEURISTIC',
                          'bg-surface-background text-text-tertiary': f.correlation_status === 'UNMATCHED',
                          'bg-amber-500/20 text-amber-300': f.correlation_status === 'AMBIGUOUS',
                        })}>
                          {f.correlation_status ?? '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {findingsData.total > 50 && (
                <p className="mt-2 text-[11px] text-text-tertiary">Mostrando 50 de {findingsData.total} findings</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function ATCImport({ assessmentId }: Props) {
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [diag, setDiag] = useState<ATCDiagnostics | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const { data: runsData, isLoading: runsLoading, isError: runsError, refetch: refetchRuns } = useQuery({
    queryKey: ['atc-runs', assessmentId],
    queryFn: () => fetchATCRuns(assessmentId),
  })

  const inspectMut = useMutation({
    mutationFn: (file: File) => inspectATCFile(assessmentId, file),
    onSuccess: (data) => {
      setDiag(data)
      setPhase('inspected')
    },
    onError: (e: Error) => {
      setErrorMsg(e.message)
      setPhase('error')
    },
  })

  const importMut = useMutation({
    mutationFn: (file: File) => importATCFile(assessmentId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['atc-runs', assessmentId] })
      setPhase('done')
      setDiag(null)
      setSelectedFile(null)
    },
    onError: (e: Error) => {
      setErrorMsg(e.message)
      setPhase('error')
    },
  })

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setSelectedFile(file)
    setPhase('inspecting')
    setErrorMsg(null)
    inspectMut.mutate(file)
  }

  function handleImport() {
    if (!selectedFile) return
    setPhase('importing')
    importMut.mutate(selectedFile)
  }

  function handleReset() {
    setPhase('idle')
    setDiag(null)
    setSelectedFile(null)
    setErrorMsg(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  const busy = phase === 'inspecting' || phase === 'importing'
  const canImport = phase === 'inspected' && diag?.validation_status !== 'REJECTED'

  return (
    <div className="h-full overflow-y-auto">
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="text-[15px] font-semibold text-text-primary">Análise ATC</h2>
        <p className="mt-1 text-[12px] text-text-tertiary">
          Importe relatórios ATC em formato XLSX para correlacionar findings com objetos SAP.
        </p>
      </div>

      {/* Upload section */}
      <div className="rounded-control border border-border-default bg-surface-elevated p-4 space-y-3">
        <div className="flex items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx"
            className="hidden"
            id="atc-file-input"
            onChange={handleFileChange}
            disabled={busy}
          />
          <label
            htmlFor="atc-file-input"
            className={cn(
              'inline-flex cursor-pointer items-center gap-2 rounded-control bg-brand px-3 py-1.5 text-[12px] font-medium text-white transition-opacity',
              busy && 'cursor-not-allowed opacity-50',
            )}
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <UploadCloud className="h-3.5 w-3.5" />}
            {phase === 'inspecting' ? 'Analisando…' : phase === 'importing' ? 'Importando…' : 'Selecionar arquivo .xlsx'}
          </label>
          {selectedFile && (
            <span className="text-[12px] text-text-secondary truncate max-w-[240px]">{selectedFile.name}</span>
          )}
          {(phase === 'inspected' || phase === 'error' || phase === 'done') && (
            <button type="button" onClick={handleReset} className="ml-auto text-[12px] text-text-tertiary hover:text-text-primary">
              Limpar
            </button>
          )}
        </div>

        {/* Diagnostics */}
        {diag && <DiagnosticsCard diag={diag} />}

        {/* Error */}
        {phase === 'error' && errorMsg && (
          <div className="rounded bg-red-500/10 px-3 py-2 text-[12px] text-red-300">
            <XCircle className="mr-1.5 inline h-3.5 w-3.5" />
            {errorMsg}
          </div>
        )}

        {/* Import button */}
        {canImport && (
          <button
            type="button"
            onClick={handleImport}
            className="inline-flex items-center gap-2 rounded-control bg-brand px-4 py-1.5 text-[12px] font-medium text-white"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            Confirmar importação
            {diag?.validation_status === 'ACCEPTED_PARTIAL' && (
              <span className="ml-1 text-amber-200">(parcial)</span>
            )}
          </button>
        )}

        {phase === 'done' && (
          <p className="text-[12px] text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Importação concluída com sucesso.
          </p>
        )}
      </div>

      {/* Existing runs */}
      <div className="space-y-2">
        <h3 className="text-[13px] font-semibold text-text-secondary">
          Histórico de importações
          {runsData && <span className="ml-2 text-text-tertiary font-normal">({runsData.total})</span>}
        </h3>
        {runsLoading && <p className="text-[12px] text-text-tertiary">Carregando…</p>}
        {runsError && <ErrorState message="Não foi possível carregar o histórico de importações." onRetry={refetchRuns} />}
        {runsData?.runs.length === 0 && !runsLoading && !runsError && (
          <p className="text-[12px] text-text-tertiary">Nenhuma importação realizada ainda.</p>
        )}
        {runsData?.runs.map((run) => (
          <RunRow key={run.id} run={run} assessmentId={assessmentId} />
        ))}
      </div>
    </div>
    </div>
  )
}
