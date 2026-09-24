/**
 * ObjectBrowser — browse SAP objects parsed from source files.
 * Shows object type filter, table of objects, and a side detail panel.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, Box, Boxes, ChevronRight, Code2, Database, RefreshCw } from 'lucide-react'
import { fetchSAPObject, fetchSAPObjects, fetchScans, triggerParse, type SAPObjectRecord } from '@/lib/api'
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
    <div className="flex h-full flex-col overflow-auto p-4 space-y-4">
      <div>
        <div className="text-[11px] text-text-tertiary uppercase tracking-wide">Object Name</div>
        <div className="mt-0.5 font-mono text-[14px] font-semibold text-text-primary">{data.object_name}</div>
      </div>
      <TypeBadge type={data.object_type} />
      <div className="text-[11px] text-text-tertiary">
        Lines {data.line_start}{data.line_end != null ? `–${data.line_end}` : '+'}
        {' · '}file #{data.source_file_id}
      </div>
      {Object.keys(data.attributes).length > 0 && (
        <div>
          <div className="mb-1.5 text-[11px] font-medium text-text-secondary">Attributes</div>
          <AttributeTable attrs={data.attributes} />
        </div>
      )}
    </div>
  )
}

export function ObjectBrowser({ assessmentId }: Props) {
  const [typeFilter, setTypeFilter] = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [parsing, setParsing] = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)

  const { data: objects = [], isLoading, refetch } = useQuery({
    queryKey: ['sap-objects', assessmentId, typeFilter],
    queryFn: () => fetchSAPObjects(assessmentId, typeFilter || undefined),
  })

  const { data: scans = [] } = useQuery({
    queryKey: ['scans', assessmentId],
    queryFn: () => fetchScans(assessmentId),
  })

  const latestCompletedScan = scans.find((s) => s.status === 'completed')

  async function handleParse() {
    if (!latestCompletedScan) return
    setParsing(true)
    setParseError(null)
    try {
      await triggerParse(assessmentId, latestCompletedScan.id)
      // Poll briefly then refetch
      await new Promise((r) => setTimeout(r, 2000))
      await refetch()
    } catch (e) {
      setParseError(e instanceof Error ? e.message : 'Parse failed')
    } finally {
      setParsing(false)
    }
  }

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

          {latestCompletedScan && (
            <button
              type="button"
              disabled={parsing}
              onClick={handleParse}
              className="rounded-control bg-brand px-3 py-1 text-[11px] font-medium text-white disabled:opacity-50 hover:bg-brand/90"
            >
              {parsing ? 'Parsing…' : 'Parse'}
            </button>
          )}
        </div>

        {parseError && (
          <div className="border-b border-border-soft bg-red-500/10 px-4 py-2 text-[11px] text-red-400">
            {parseError}
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
                {latestCompletedScan
                  ? 'No objects parsed yet. Click Parse to extract SAP objects.'
                  : 'Run a source scan first, then parse to extract SAP objects.'}
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
