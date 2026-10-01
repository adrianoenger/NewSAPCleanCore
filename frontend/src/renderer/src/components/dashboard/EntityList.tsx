/**
 * Full-page drill-down lists (SPRINT-18 CAP-003 / ADR-019). Objects and ATC findings are paginated
 * server-side (tens of thousands of findings on real assessments); applications and business rules
 * are small per assessment and filtered client-side. Rows open the entity's detail page.
 */
import { useMemo, useState, type ReactNode } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { createColumnHelper, tableFeatures, useTable } from '@tanstack/react-table'
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { RULE_TYPE_CONFIG, RuleTypeBadge } from '@/components/functional/BusinessRuleBrowser'
import { PriorityBadge, TYPE_CONFIG, TypeBadge } from '@/components/parsing/ObjectBrowser'
import {
  LevelBadge,
  RECOMMENDATION_CONFIG,
  RecommendationChip,
  UNCLASSIFIED,
  UNCLASSIFIED_CONFIG,
} from '@/components/shared/cleanCoreDisplay'
import { ErrorState } from '@/components/shared/ErrorState'
import {
  fetchApplications,
  fetchBusinessRules,
  fetchCurrentATCFindings,
  fetchObjectList,
  type ApplicationRecord,
  type ATCFindingListItemRecord,
  type BusinessRuleRecord,
  type ObjectListItemRecord,
} from '@/lib/api'
import type { DrillPage, ListFilter, ResultFocus } from '@/lib/resultNav'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 50
const features = tableFeatures({})

export type OpenDetail = (focus: ResultFocus, label: string) => void

interface Column<T> {
  id: string
  header: string
  cell: (row: T) => ReactNode
  className?: string
}

function DataTable<T extends object>({
  rows,
  columns,
  rowKey,
  onRowClick,
}: {
  rows: T[]
  columns: Column<T>[]
  rowKey: (row: T) => string
  onRowClick: (row: T) => void
}) {
  const tableColumns = useMemo(() => {
    const helper = createColumnHelper<typeof features, T>()
    return helper.columns(
      columns.map((c) => helper.display({ id: c.id, header: c.header, cell: ({ row }) => c.cell(row.original) })),
    )
  }, [columns])
  const table = useTable({ features, columns: tableColumns, data: rows, getRowId: rowKey })
  const classById = Object.fromEntries(columns.map((c) => [c.id, c.className ?? '']))

  return (
    <table className="w-full border-collapse text-[12px]">
      <thead>
        {table.getHeaderGroups().map((group) => (
          <tr key={group.id} className="border-b border-border-soft">
            {group.headers.map((header) => (
              <th
                key={header.id}
                className={cn(
                  'px-3 py-2 text-left text-[10px] font-medium uppercase tracking-wide text-text-tertiary',
                  classById[header.column.id],
                )}
              >
                {header.isPlaceholder ? null : <table.FlexRender header={header} />}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((row) => (
          <tr
            key={row.id}
            onClick={() => onRowClick(row.original)}
            className="cursor-pointer border-b border-border-soft/60 hover:bg-surface-hover"
          >
            {row.getAllCells().map((cell) => (
              <td key={cell.id} className={cn('px-3 py-2 align-top', classById[cell.column.id])}>
                <table.FlexRender cell={cell} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Toolbar({ q, onQ, children }: { q: string; onQ: (v: string) => void; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex min-w-[240px] flex-1 items-center gap-2 rounded-control border border-border-default bg-surface-sidebar px-2">
        <Search className="h-3.5 w-3.5 text-text-tertiary" strokeWidth={2} />
        <input
          value={q}
          onChange={(e) => onQ(e.target.value)}
          placeholder="Buscar…"
          className="w-full bg-transparent py-1.5 text-[12px] text-text-primary outline-none"
        />
      </div>
      {children}
    </div>
  )
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-control border border-border-default bg-surface-sidebar px-2 py-1.5 text-[12px] text-text-primary outline-none focus:border-brand"
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

const RECOMMENDATION_OPTIONS = [
  { value: '', label: 'Todas as classificações' },
  ...Object.entries(RECOMMENDATION_CONFIG).map(([value, { label }]) => ({ value, label })),
  { value: UNCLASSIFIED, label: UNCLASSIFIED_CONFIG.label },
]

// Panaya usage/repository XLSX profile (SPRINT-20) — the only levels observed in the real
// export; the filter still accepts any value typed via URL/drill-down, this is just the picker.
const USAGE_LEVEL_OPTIONS = [
  { value: '', label: 'Qualquer uso' },
  { value: 'Unused', label: 'Sem uso' },
  { value: 'Unknown', label: 'Uso desconhecido' },
  { value: 'Normally Used', label: 'Uso normal' },
  { value: 'Frequently Used', label: 'Uso frequente' },
  { value: 'Rarely Used', label: 'Uso raro' },
]

function Pager({ total, offset, onOffset }: { total: number; offset: number; onOffset: (o: number) => void }) {
  if (total <= PAGE_SIZE) return <div className="text-[11px] text-text-tertiary">{total.toLocaleString('pt-BR')} itens</div>
  const page = Math.floor(offset / PAGE_SIZE) + 1
  const pages = Math.ceil(total / PAGE_SIZE)
  return (
    <div className="flex items-center justify-between text-[11px] text-text-tertiary">
      <span>
        {(offset + 1).toLocaleString('pt-BR')}–{Math.min(offset + PAGE_SIZE, total).toLocaleString('pt-BR')} de{' '}
        {total.toLocaleString('pt-BR')}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => onOffset(Math.max(0, offset - PAGE_SIZE))}
          className="rounded-control p-1 hover:bg-surface-hover disabled:opacity-30"
          title="Página anterior"
        >
          <ChevronLeft className="h-3.5 w-3.5" strokeWidth={2} />
        </button>
        <span>
          Página {page} de {pages}
        </span>
        <button
          type="button"
          disabled={offset + PAGE_SIZE >= total}
          onClick={() => onOffset(offset + PAGE_SIZE)}
          className="rounded-control p-1 hover:bg-surface-hover disabled:opacity-30"
          title="Próxima página"
        >
          <ChevronRight className="h-3.5 w-3.5" strokeWidth={2} />
        </button>
      </div>
    </div>
  )
}

function ListFrame({
  isLoading,
  isError,
  refetch,
  empty,
  children,
}: {
  isLoading: boolean
  isError: boolean
  refetch: () => void
  empty: boolean
  children: ReactNode
}) {
  if (isError) return <ErrorState message="Não foi possível carregar a lista." onRetry={refetch} />
  if (isLoading) return <div className="py-8 text-center text-[12px] text-text-tertiary">Carregando…</div>
  if (empty) return <div className="py-8 text-center text-[12px] text-text-tertiary">Nenhum item encontrado.</div>
  return <div className="overflow-x-auto rounded border border-border-soft bg-surface-elevated">{children}</div>
}

// ---------------------------------------------------------------------------

const OBJECT_COLUMNS: Column<ObjectListItemRecord>[] = [
  { id: 'name', header: 'Objeto', cell: (o) => <span className="font-mono text-text-primary">{o.object_name}</span> },
  { id: 'type', header: 'Tipo', cell: (o) => <TypeBadge type={o.object_type} /> },
  {
    id: 'application',
    header: 'Aplicação',
    cell: (o) => (
      <span className="text-text-secondary">
        {o.application_name ||
          (o.application_id ? <span className="text-text-tertiary">Aplicação #{o.application_id} (sem nome)</span> : '—')}
      </span>
    ),
  },
  { id: 'recommendation', header: 'Classificação', cell: (o) => <RecommendationChip recommendation={o.recommendation} /> },
  { id: 'risk', header: 'Risco técnico', cell: (o) => <LevelBadge level={o.technical_risk} title="Risco técnico" /> },
  {
    id: 'atc',
    header: 'Findings ATC',
    className: 'text-right',
    cell: (o) => <span className="font-mono text-text-secondary">{o.atc_findings.toLocaleString('pt-BR')}</span>,
  },
  {
    id: 'usage',
    header: 'Uso (Panaya)',
    cell: (o) => <span className="text-text-secondary">{o.usage_level ?? <span className="text-text-tertiary">—</span>}</span>,
  },
]

const TYPE_OPTIONS = [
  { value: '', label: 'Todos os tipos' },
  ...Object.entries(TYPE_CONFIG).map(([value, { label }]) => ({ value, label })),
]

function ObjectsList({ assessmentId, initial, onOpenDetail }: { assessmentId: number; initial: ListFilter; onOpenDetail: OpenDetail }) {
  const [q, setQ] = useState('')
  const [objectType, setObjectType] = useState(initial.object_type ?? '')
  const [recommendation, setRecommendation] = useState(initial.recommendation ?? '')
  const [customOnly, setCustomOnly] = useState(initial.custom_only ?? false)
  const [usageLevel, setUsageLevel] = useState(initial.usage_level ?? '')
  const [offset, setOffset] = useState(0)
  const filter = {
    object_type: objectType || undefined,
    recommendation: recommendation || undefined,
    custom_only: customOnly,
    high_impact: initial.high_impact,
    application_id: initial.application_id,
    usage_level: usageLevel || undefined,
    q: q.trim() || undefined,
    limit: PAGE_SIZE,
    offset,
  }
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['object-list', assessmentId, filter],
    queryFn: () => fetchObjectList(assessmentId, filter),
    placeholderData: keepPreviousData,
  })
  const reset = <V,>(setter: (v: V) => void) => (v: V) => {
    setter(v)
    setOffset(0)
  }

  return (
    <div className="space-y-3">
      <Toolbar q={q} onQ={reset(setQ)}>
        <Select value={objectType} onChange={reset(setObjectType)} options={TYPE_OPTIONS} />
        <Select value={recommendation} onChange={reset(setRecommendation)} options={RECOMMENDATION_OPTIONS} />
        <Select value={usageLevel} onChange={reset(setUsageLevel)} options={USAGE_LEVEL_OPTIONS} />
        <label className="flex items-center gap-1.5 text-[12px] text-text-secondary">
          <input type="checkbox" checked={customOnly} onChange={(e) => reset(setCustomOnly)(e.target.checked)} />
          Somente customizados
        </label>
      </Toolbar>
      {initial.high_impact && (
        <div className="text-[11px] text-text-tertiary">Filtro: objetos de aplicações com risco técnico alto ou crítico.</div>
      )}
      <ListFrame isLoading={isLoading} isError={isError} refetch={refetch} empty={(data?.items.length ?? 0) === 0}>
        <DataTable
          rows={data?.items ?? []}
          columns={OBJECT_COLUMNS}
          rowKey={(o) => String(o.id)}
          onRowClick={(o) => onOpenDetail({ kind: 'sap_object', id: o.id }, o.object_name)}
        />
      </ListFrame>
      <Pager total={data?.total ?? 0} offset={offset} onOffset={setOffset} />
    </div>
  )
}

// ---------------------------------------------------------------------------

const ATC_COLUMNS: Column<ATCFindingListItemRecord>[] = [
  { id: 'priority', header: 'Prioridade', cell: (f) => <PriorityBadge priority={f.priority} /> },
  { id: 'check', header: 'Check', cell: (f) => <span className="text-text-primary">{f.check_title ?? 'Finding ATC'}</span> },
  {
    id: 'message',
    header: 'Mensagem',
    cell: (f) => <span className="line-clamp-2 text-text-secondary">{f.check_message ?? '—'}</span>,
  },
  {
    id: 'object',
    header: 'Objeto',
    cell: (f) => (
      <span className="font-mono text-text-secondary">
        {f.object_name_raw ?? '—'}
        {f.correlated_object_id == null && <span className="ml-1 font-sans text-[10px] text-text-tertiary">(não correlacionado)</span>}
      </span>
    ),
  },
  { id: 'package', header: 'Pacote', cell: (f) => <span className="font-mono text-text-tertiary">{f.package_name_raw ?? '—'}</span> },
]

const PRIORITY_OPTIONS = [
  { value: '', label: 'Todas as prioridades' },
  { value: '1', label: 'Prioridade 1' },
  { value: '2', label: 'Prioridade 2' },
  { value: '3', label: 'Prioridade 3' },
]

function ATCFindingsList({ assessmentId, initial, onOpenDetail }: { assessmentId: number; initial: ListFilter; onOpenDetail: OpenDetail }) {
  const [q, setQ] = useState('')
  const [priority, setPriority] = useState(initial.priority != null ? String(initial.priority) : '')
  const [offset, setOffset] = useState(0)
  const filter = {
    priority: priority ? Number(priority) : undefined,
    object_id: initial.object_id,
    q: q.trim() || undefined,
    limit: PAGE_SIZE,
    offset,
  }
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['atc-findings', assessmentId, filter],
    queryFn: () => fetchCurrentATCFindings(assessmentId, filter),
    placeholderData: keepPreviousData,
  })

  return (
    <div className="space-y-3">
      <Toolbar
        q={q}
        onQ={(v) => {
          setQ(v)
          setOffset(0)
        }}
      >
        <Select
          value={priority}
          onChange={(v) => {
            setPriority(v)
            setOffset(0)
          }}
          options={PRIORITY_OPTIONS}
        />
      </Toolbar>
      <ListFrame isLoading={isLoading} isError={isError} refetch={refetch} empty={(data?.items.length ?? 0) === 0}>
        <DataTable
          rows={data?.items ?? []}
          columns={ATC_COLUMNS}
          rowKey={(f) => String(f.id)}
          onRowClick={(f) => onOpenDetail({ kind: 'atc_finding', id: f.id }, f.check_title ?? `Finding #${f.id}`)}
        />
      </ListFrame>
      <Pager total={data?.total ?? 0} offset={offset} onOffset={setOffset} />
    </div>
  )
}

// ---------------------------------------------------------------------------

const APPLICATION_COLUMNS: Column<ApplicationRecord>[] = [
  {
    id: 'name',
    header: 'Aplicação',
    cell: (a) => (
      <div>
        <div className="text-text-primary">{a.name || `Aplicação #${a.id}`}</div>
        {a.description && <div className="line-clamp-1 text-[11px] text-text-tertiary">{a.description}</div>}
      </div>
    ),
  },
  { id: 'domain', header: 'Domínio', cell: (a) => <span className="text-text-secondary">{a.domain || '—'}</span> },
  { id: 'members', header: 'Objetos', className: 'text-right', cell: (a) => <span className="font-mono text-text-secondary">{a.member_count}</span> },
  { id: 'recommendation', header: 'Classificação', cell: (a) => <RecommendationChip recommendation={a.clean_core?.recommendation ?? null} /> },
  { id: 'risk', header: 'Risco técnico', cell: (a) => <LevelBadge level={a.clean_core?.technical_risk ?? null} title="Risco técnico" /> },
  {
    id: 'importance',
    header: 'Importância',
    cell: (a) => <LevelBadge level={a.clean_core?.business_importance ?? null} title="Importância de negócio" />,
  },
]

function ApplicationsList({ assessmentId, initial, onOpenDetail }: { assessmentId: number; initial: ListFilter; onOpenDetail: OpenDetail }) {
  const [q, setQ] = useState('')
  const [recommendation, setRecommendation] = useState(initial.recommendation ?? '')
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['applications', assessmentId],
    queryFn: () => fetchApplications(assessmentId),
  })
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return (data?.applications ?? []).filter((a) => {
      if (a.status === 'MERGED') return false
      if (recommendation) {
        const rec = a.clean_core?.recommendation ?? UNCLASSIFIED
        if (rec !== recommendation) return false
      }
      if (!needle) return true
      return [a.name, a.domain, a.description].some((v) => v?.toLowerCase().includes(needle))
    })
  }, [data, q, recommendation])

  return (
    <div className="space-y-3">
      <Toolbar q={q} onQ={setQ}>
        <Select value={recommendation} onChange={setRecommendation} options={RECOMMENDATION_OPTIONS} />
      </Toolbar>
      <ListFrame isLoading={isLoading} isError={isError} refetch={refetch} empty={rows.length === 0}>
        <DataTable
          rows={rows}
          columns={APPLICATION_COLUMNS}
          rowKey={(a) => String(a.id)}
          onRowClick={(a) => onOpenDetail({ kind: 'application', id: a.id }, a.name || `Aplicação #${a.id}`)}
        />
      </ListFrame>
      <div className="text-[11px] text-text-tertiary">{rows.length} aplicações</div>
    </div>
  )
}

// ---------------------------------------------------------------------------

const RULE_COLUMNS: Column<BusinessRuleRecord>[] = [
  { id: 'type', header: 'Tipo', cell: (r) => <RuleTypeBadge type={r.rule_type} /> },
  { id: 'condition', header: 'Condição', cell: (r) => <span className="line-clamp-2 text-text-primary">{r.condition}</span> },
  { id: 'action', header: 'Ação', cell: (r) => <span className="line-clamp-2 text-text-secondary">{r.action}</span> },
  {
    id: 'confidence',
    header: 'Confiança',
    className: 'text-right',
    cell: (r) => <span className="font-mono text-text-secondary">{Math.round(r.confidence * 100)}%</span>,
  },
  {
    id: 'validated',
    header: 'Validada',
    cell: (r) => (r.user_validated ? <span className="text-emerald-400">Sim</span> : <span className="text-text-tertiary">—</span>),
  },
]

const RULE_TYPE_OPTIONS = [
  { value: '', label: 'Todos os tipos' },
  ...Object.entries(RULE_TYPE_CONFIG).map(([value, { label }]) => ({ value, label })),
]

function BusinessRulesList({ assessmentId, onOpenDetail }: { assessmentId: number; onOpenDetail: OpenDetail }) {
  const [q, setQ] = useState('')
  const [ruleType, setRuleType] = useState('')
  const [offset, setOffset] = useState(0)
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['business-rules', assessmentId],
    queryFn: () => fetchBusinessRules(assessmentId),
  })
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return (data?.rules ?? []).filter(
      (r) =>
        (!ruleType || r.rule_type === ruleType) &&
        (!needle || r.condition.toLowerCase().includes(needle) || r.action.toLowerCase().includes(needle)),
    )
  }, [data, q, ruleType])

  return (
    <div className="space-y-3">
      <Toolbar
        q={q}
        onQ={(v) => {
          setQ(v)
          setOffset(0)
        }}
      >
        <Select
          value={ruleType}
          onChange={(v) => {
            setRuleType(v)
            setOffset(0)
          }}
          options={RULE_TYPE_OPTIONS}
        />
      </Toolbar>
      <ListFrame isLoading={isLoading} isError={isError} refetch={refetch} empty={rows.length === 0}>
        <DataTable
          rows={rows.slice(offset, offset + PAGE_SIZE)}
          columns={RULE_COLUMNS}
          rowKey={(r) => String(r.id)}
          onRowClick={(r) => onOpenDetail({ kind: 'business_rule', id: r.id }, `Regra #${r.id}`)}
        />
      </ListFrame>
      <Pager total={rows.length} offset={offset} onOffset={setOffset} />
    </div>
  )
}

// ---------------------------------------------------------------------------

export function EntityList({
  assessmentId,
  page,
  onOpenDetail,
}: {
  assessmentId: number
  page: Extract<DrillPage, { type: 'list' }>
  onOpenDetail: OpenDetail
}) {
  return (
    <div className="mx-auto max-w-7xl space-y-4 p-6">
      <div className="text-[15px] font-medium text-text-primary">{page.title}</div>
      {page.entity === 'objects' && <ObjectsList assessmentId={assessmentId} initial={page.filter} onOpenDetail={onOpenDetail} />}
      {page.entity === 'atc_findings' && (
        <ATCFindingsList assessmentId={assessmentId} initial={page.filter} onOpenDetail={onOpenDetail} />
      )}
      {page.entity === 'applications' && (
        <ApplicationsList assessmentId={assessmentId} initial={page.filter} onOpenDetail={onOpenDetail} />
      )}
      {page.entity === 'business_rules' && <BusinessRulesList assessmentId={assessmentId} onOpenDetail={onOpenDetail} />}
    </div>
  )
}
