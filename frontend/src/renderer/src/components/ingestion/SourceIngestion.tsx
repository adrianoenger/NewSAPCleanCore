/**
 * SourceIngestion — directory picker, scan launcher, real-time progress and file inventory.
 *
 * Path mapping: Electron returns a host-OS path (e.g. C:\...). The backend runs in Docker
 * where the project root is mounted at /workspace. getProjectRoot() returns the host project
 * root so the renderer can translate picked paths to container-visible paths automatically.
 */

import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  FolderOpen,
  FolderSearch,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  ChevronRight,
} from 'lucide-react'
import {
  fetchScans,
  fetchScan,
  fetchSourceFiles,
  startScan,
  type CategoryCount,
  type ScanRecord,
} from '@/lib/api'
import { EvidenceDatasets } from '@/components/evidence/EvidenceDatasets'
import { cn } from '@/lib/utils'

interface Props {
  assessmentId: number
}

const CATEGORY_LABELS: Record<string, string> = {
  abap_source: 'ABAP Source',
  xml_metadata: 'XML Metadata',
  cds: 'CDS',
  ddic: 'DDIC',
  configuration: 'Configuration',
  documentation: 'Documentation',
  other: 'Other',
}

const CATEGORY_COLORS: Record<string, string> = {
  abap_source: 'bg-brand/80',
  xml_metadata: 'bg-purple-500/80',
  cds: 'bg-cyan-500/80',
  ddic: 'bg-amber-500/80',
  configuration: 'bg-emerald-500/80',
  documentation: 'bg-slate-400/80',
  other: 'bg-surface-elevated',
}

/** Translate a host-OS absolute path to its /workspace equivalent. */
function toContainerPath(hostPath: string, projectRoot: string): string | null {
  const fwd = (s: string) => s.replace(/\\/g, '/')
  const normalized = fwd(hostPath)
  const root = fwd(projectRoot)
  if (!normalized.startsWith(root)) return null
  return '/workspace' + normalized.slice(root.length)
}

function ScanStatusIcon({ status }: { status: ScanRecord['status'] }) {
  if (status === 'completed') return <CheckCircle2 className="h-4 w-4 text-success" />
  if (status === 'failed') return <XCircle className="h-4 w-4 text-risk" />
  return <Loader2 className="h-4 w-4 animate-spin text-brand" />
}

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated">
      <div
        className="h-full rounded-full bg-brand transition-all duration-300"
        style={{ width: max > 0 ? `${pct}%` : '100%', opacity: max > 0 ? 1 : 0.3 }}
      />
    </div>
  )
}

function CategoryBar({ counts, total }: { counts: CategoryCount[]; total: number }) {
  if (total === 0) return null
  return (
    <div className="flex h-3 w-full overflow-hidden rounded-full">
      {counts.map(({ category, count }) => (
        <div
          key={category}
          title={`${CATEGORY_LABELS[category] ?? category}: ${count}`}
          className={cn('h-full transition-all duration-300', CATEGORY_COLORS[category] ?? 'bg-surface-elevated')}
          style={{ width: `${(count / total) * 100}%` }}
        />
      ))}
    </div>
  )
}

function CategoryLegend({ counts, total }: { counts: CategoryCount[]; total: number }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-2">
      {counts.map(({ category, count }) => (
        <div key={category} className="flex items-center gap-1.5 text-[12px]">
          <span className={cn('h-2.5 w-2.5 rounded-sm', CATEGORY_COLORS[category] ?? 'bg-surface-elevated')} />
          <span className="text-text-secondary">{CATEGORY_LABELS[category] ?? category}</span>
          <span className="font-mono text-text-primary">{count}</span>
          <span className="text-text-tertiary">
            ({total > 0 ? Math.round((count / total) * 100) : 0}%)
          </span>
        </div>
      ))}
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

function CollapsibleSection({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: string
  subtitle?: string
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="rounded-card border border-border-default bg-surface-card p-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 text-left"
      >
        <ChevronRight className={cn('h-3.5 w-3.5 shrink-0 text-text-tertiary transition-transform', open && 'rotate-90')} />
        <h2 className="text-[14px] font-medium">
          {title}
          {subtitle && <span className="ml-2 font-normal text-text-tertiary">{subtitle}</span>}
        </h2>
      </button>
      {open && <div className="mt-3">{children}</div>}
    </section>
  )
}

export function SourceIngestion({ assessmentId }: Props) {
  const queryClient = useQueryClient()
  const [selectedPath, setSelectedPath] = useState<string>('')
  const [pickedHostPath, setPickedHostPath] = useState<string>('')
  const [activeScanId, setActiveScanId] = useState<number | null>(null)
  const [launching, setLaunching] = useState(false)
  const [launchError, setLaunchError] = useState<string | null>(null)

  const scans = useQuery({
    queryKey: ['scans', assessmentId],
    queryFn: () => fetchScans(assessmentId),
  })

  // Set activeScanId to the latest running or most recent scan
  useEffect(() => {
    if (!scans.data || scans.data.length === 0) return
    const running = scans.data.find((s) => s.status === 'pending' || s.status === 'scanning')
    setActiveScanId(running?.id ?? scans.data[0].id)
  }, [scans.data])

  const activeScanQuery = useQuery({
    queryKey: ['scan', assessmentId, activeScanId],
    queryFn: () => fetchScan(assessmentId, activeScanId!),
    enabled: activeScanId != null,
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === 'pending' || s === 'scanning' ? 1500 : false
    },
  })

  const activeScan = activeScanQuery.data

  const filesQuery = useQuery({
    queryKey: ['sourceFiles', assessmentId, activeScanId],
    queryFn: () => fetchSourceFiles(assessmentId, activeScanId ?? undefined),
    enabled: activeScan?.status === 'completed',
  })

  async function handleSelectDirectory() {
    const hostPath = await window.desktop?.selectDirectory()
    if (!hostPath) return

    setPickedHostPath(hostPath)

    // Try to map the host path to the container path
    if (window.desktop?.getProjectRoot) {
      const projectRoot = await window.desktop.getProjectRoot()
      const containerPath = toContainerPath(hostPath, projectRoot)
      if (containerPath) {
        setSelectedPath(containerPath)
        setLaunchError(null)
      } else {
        // Path is outside the project — show it and let user edit manually
        setSelectedPath(hostPath)
        setLaunchError(
          `O diretório selecionado está fora do projeto (${projectRoot}). ` +
          `Informe o caminho acessível pelo backend Docker (ex: /workspace/...).`
        )
      }
    } else {
      setSelectedPath(hostPath)
    }
  }

  async function handleStartScan() {
    if (!selectedPath.trim()) return
    setLaunching(true)
    setLaunchError(null)
    try {
      const scan = await startScan(assessmentId, selectedPath.trim())
      setActiveScanId(scan.id)
      await queryClient.invalidateQueries({ queryKey: ['scans', assessmentId] })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setLaunchError(`Não foi possível iniciar o scan: ${msg}`)
    } finally {
      setLaunching(false)
    }
  }

  const isScanning =
    activeScan?.status === 'pending' || activeScan?.status === 'scanning'

  return (
    <div className="h-full overflow-y-auto">
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-[22px] font-medium">Source Ingestion</h1>
        <p className="mt-0.5 text-[13px] text-text-tertiary">
          Selecione um diretório de fontes e inicie o scan para gerar o inventário de arquivos.
        </p>
      </div>

      {/* Directory picker */}
      <section className="rounded-card border border-border-default bg-surface-card p-4">
        <h2 className="mb-3 text-[14px] font-medium">Diretório de Origem</h2>
        <div className="flex gap-2">
          <div className="flex-1 flex flex-col gap-1">
            <input
              type="text"
              value={selectedPath}
              onChange={(e) => { setSelectedPath(e.target.value); setLaunchError(null) }}
              placeholder="/workspace/demo-source"
              className="w-full rounded-md border border-border-default bg-surface-background px-3 py-2 text-[13px] text-text-primary placeholder:text-text-tertiary focus:border-brand focus:outline-none"
            />
            {pickedHostPath && selectedPath !== pickedHostPath && (
              <p className="text-[11px] text-text-tertiary">
                Selecionado: <span className="font-mono">{pickedHostPath}</span>
                {' → '}
                <span className="font-mono text-success">{selectedPath}</span>
              </p>
            )}
          </div>
          {window.desktop?.selectDirectory && (
            <button
              type="button"
              onClick={handleSelectDirectory}
              className="flex items-center gap-1.5 rounded-md border border-border-default bg-surface-elevated px-3 py-2 text-[13px] text-text-secondary hover:border-brand/50 hover:text-text-primary"
            >
              <FolderOpen className="h-4 w-4" />
              Browse
            </button>
          )}
          <button
            type="button"
            onClick={handleStartScan}
            disabled={!selectedPath.trim() || launching || isScanning}
            className="flex items-center gap-1.5 rounded-md bg-brand px-4 py-2 text-[13px] font-medium text-white hover:bg-brand/90 disabled:opacity-50"
          >
            {launching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FolderSearch className="h-4 w-4" />
            )}
            {isScanning ? 'Scanning…' : 'Start Scan'}
          </button>
        </div>

        {/* Error message */}
        {launchError && (
          <div className="mt-2 flex items-start gap-2 rounded-md border border-risk/30 bg-risk/5 px-3 py-2">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-risk" />
            <p className="text-[12px] text-risk">{launchError}</p>
          </div>
        )}

      </section>

      {/* Active scan status */}
      {activeScan && (
        <section className="rounded-card border border-border-default bg-surface-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ScanStatusIcon status={activeScan.status} />
              <h2 className="text-[14px] font-medium">
                {activeScan.status === 'completed'
                  ? 'Scan Concluído'
                  : activeScan.status === 'failed'
                    ? 'Scan com Erro'
                    : activeScan.status === 'pending'
                      ? 'Aguardando início…'
                      : 'Scanning…'}
              </h2>
            </div>
            <button
              type="button"
              onClick={() =>
                queryClient.invalidateQueries({ queryKey: ['scan', assessmentId, activeScanId] })
              }
              className="text-text-tertiary hover:text-text-secondary"
              title="Atualizar"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>

          <p className="mb-2 font-mono text-[11px] text-text-tertiary">{activeScan.source_path}</p>

          {activeScan.status !== 'failed' && (
            <ProgressBar value={activeScan.scanned_files} max={activeScan.total_files} />
          )}

          <div className="mt-2 flex items-center gap-3 text-[12px] text-text-secondary">
            <span>
              <span className="font-mono text-text-primary">{activeScan.scanned_files}</span>
              {activeScan.total_files > 0 && (
                <>
                  {' / '}
                  <span className="font-mono text-text-primary">{activeScan.total_files}</span>
                </>
              )}{' '}
              arquivos
            </span>
            {activeScan.total_files > 0 && activeScan.scanned_files < activeScan.total_files && activeScan.status === 'scanning' && (
              <span className="text-text-tertiary">
                {Math.round((activeScan.scanned_files / activeScan.total_files) * 100)}%
              </span>
            )}
            {activeScan.completed_at && (
              <span className="text-text-tertiary">
                Concluído às {new Date(activeScan.completed_at).toLocaleTimeString()}
                {activeScan.duration_seconds != null && (
                  <> · <span className="font-mono text-text-primary">{formatDuration(activeScan.duration_seconds)}</span></>
                )}
              </span>
            )}
          </div>

          {activeScan.error && (
            <div className="mt-2 flex items-start gap-2 rounded-md border border-risk/30 bg-risk/5 px-3 py-2">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-risk" />
              <p className="text-[12px] text-risk">{activeScan.error}</p>
            </div>
          )}

          {activeScan.status === 'completed' && activeScan.category_counts.length > 0 && (
            <div className="mt-4">
              <CategoryBar counts={activeScan.category_counts} total={activeScan.total_files} />
              <CategoryLegend counts={activeScan.category_counts} total={activeScan.total_files} />
            </div>
          )}
        </section>
      )}

      {/* Scan history */}
      {scans.data && scans.data.length > 0 && (
        <CollapsibleSection title="Histórico de Scans" subtitle={`(${scans.data.length})`}>
          <div className="flex flex-col gap-1.5">
            {scans.data.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setActiveScanId(s.id)}
                className={cn(
                  'flex items-center gap-2 rounded-md px-3 py-2 text-left text-[12px] transition-colors',
                  s.id === activeScanId
                    ? 'bg-brand/10 text-brand-text'
                    : 'hover:bg-surface-elevated text-text-secondary',
                )}
              >
                <ScanStatusIcon status={s.status} />
                <span className="font-mono flex-1 truncate">{s.source_path}</span>
                <span className="text-text-tertiary">{s.scanned_files} arqs</span>
                {s.duration_seconds != null && (
                  <span className="font-mono text-text-tertiary">{formatDuration(s.duration_seconds)}</span>
                )}
              </button>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* File inventory table */}
      {filesQuery.data && filesQuery.data.length > 0 && (
        <CollapsibleSection title="Inventário de Arquivos" subtitle={`(${filesQuery.data.length} arquivos)`}>
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-border-soft text-left text-text-tertiary">
                  <th className="pb-2 pr-4 font-medium">Caminho</th>
                  <th className="pb-2 pr-4 font-medium">Categoria</th>
                  <th className="pb-2 pr-4 font-medium text-right">Tamanho</th>
                  <th className="pb-2 font-medium">SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {filesQuery.data.map((f) => (
                  <tr
                    key={f.id}
                    className="border-b border-border-soft/50 last:border-b-0 hover:bg-surface-elevated"
                  >
                    <td className="py-1.5 pr-4 font-mono text-text-primary">{f.rel_path}</td>
                    <td className="py-1.5 pr-4">
                      <span
                        className={cn(
                          'rounded px-1.5 py-0.5 text-[10px] font-medium text-white',
                          CATEGORY_COLORS[f.category] ?? 'bg-surface-elevated',
                        )}
                      >
                        {CATEGORY_LABELS[f.category] ?? f.category}
                      </span>
                    </td>
                    <td className="py-1.5 pr-4 text-right font-mono text-text-secondary">
                      {formatBytes(f.size_bytes)}
                    </td>
                    <td className="py-1.5 font-mono text-[10px] text-text-tertiary">
                      {f.sha256.slice(0, 12)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}

      <EvidenceDatasets assessmentId={assessmentId} />
    </div>
    </div>
  )
}
