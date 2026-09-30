/**
 * Dashboard Geral panels mirroring the reference dashboard (SPRINT-18 CAP-003 / ADR-019): object
 * inventory, ATC findings by priority, Clean Core distribution donut and the ATC priority bar
 * chart. Every row/slice/bar is a drill-down entry point (`onOpenList`).
 */
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { TYPE_CONFIG } from '@/components/parsing/ObjectBrowser'
import { RECOMMENDATION_CONFIG, UNCLASSIFIED, recommendationConfig } from '@/components/shared/cleanCoreDisplay'
import type { DashboardOverviewRecord } from '@/lib/api'
import type { DrillPage } from '@/lib/resultNav'

type OpenList = (page: Extract<DrillPage, { type: 'list' }>) => void

// SAP TADIR-style short codes shown next to the parsed object type (reference dashboard layout).
const TYPE_CODE: Record<string, string> = {
  report: 'PROG',
  class: 'CLAS',
  function_module: 'FUNC',
  ddic_table: 'TABL',
  ddic_domain: 'DOMA',
}

export const PRIORITY_COLORS: Record<string, string> = { '1': '#c0392b', '2': '#d68910', '3': '#7f8c8d' }
const PRIORITY_LABELS: Record<string, string> = {
  '1': 'Prioridade 1 (Erro)',
  '2': 'Prioridade 2 (Aviso)',
  '3': 'Prioridade 3 (Informação)',
}

const fmt = (n: number) => n.toLocaleString('pt-BR')

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col rounded border border-border-soft bg-surface-elevated p-4">
      <div className="mb-3 text-[12px] font-medium text-text-secondary">{title}</div>
      {children}
    </div>
  )
}

function Row({
  label,
  value,
  onClick,
  bold,
  indent,
}: {
  label: React.ReactNode
  value: number
  onClick?: () => void
  bold?: boolean
  indent?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[12px] hover:bg-surface-hover disabled:cursor-default disabled:hover:bg-transparent"
    >
      <span className={indent ? 'pl-3 text-text-secondary' : bold ? 'font-medium text-text-primary' : 'text-text-primary'}>
        {label}
      </span>
      <span className={bold ? 'font-mono font-semibold text-text-primary' : 'font-mono text-text-secondary'}>
        {fmt(value)}
      </span>
    </button>
  )
}

export function InventoryPanel({ data, onOpenList }: { data: DashboardOverviewRecord; onOpenList: OpenList }) {
  const types = Object.entries(data.objects_by_type).sort((a, b) => b[1] - a[1])
  return (
    <Panel title="Inventário de Objetos">
      <Row
        label="Objetos customizados (Z/Y)"
        value={data.objects_custom}
        onClick={() => onOpenList({ type: 'list', entity: 'objects', filter: { custom_only: true }, title: 'Objetos customizados' })}
      />
      <Row
        label="Total de objetos"
        value={data.objects_total}
        bold
        onClick={() => onOpenList({ type: 'list', entity: 'objects', filter: {}, title: 'Objetos analisados' })}
      />
      <div className="my-1 border-t border-border-soft" />
      {types.map(([type, count]) => {
        const label = TYPE_CONFIG[type]?.label ?? type
        return (
          <Row
            key={type}
            indent
            label={
              <>
                <span className="mr-2 font-mono text-[10px] text-text-tertiary">{TYPE_CODE[type] ?? type.toUpperCase()}</span>
                {label}
              </>
            }
            value={count}
            onClick={() => onOpenList({ type: 'list', entity: 'objects', filter: { object_type: type }, title: `Objetos — ${label}` })}
          />
        )
      })}
    </Panel>
  )
}

export function AtcPanel({ data, onOpenList }: { data: DashboardOverviewRecord; onOpenList: OpenList }) {
  if (data.atc_run_id == null) {
    return (
      <Panel title="Findings ATC">
        <div className="text-[12px] text-text-tertiary">Nenhuma importação ATC para este assessment (passo 2).</div>
      </Panel>
    )
  }
  return (
    <Panel title="Findings ATC">
      <Row
        label="Total de findings"
        value={data.atc_total}
        bold
        onClick={() => onOpenList({ type: 'list', entity: 'atc_findings', filter: {}, title: 'Findings ATC' })}
      />
      <div className="my-1 border-t border-border-soft" />
      {['1', '2', '3'].map((p) => (
        <Row
          key={p}
          indent
          label={
            <span className="inline-flex items-center gap-2">
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: PRIORITY_COLORS[p] }} />
              {PRIORITY_LABELS[p]}
            </span>
          }
          value={data.atc_by_priority[p] ?? 0}
          onClick={() =>
            onOpenList({
              type: 'list',
              entity: 'atc_findings',
              filter: { priority: Number(p) },
              title: `Findings ATC — ${PRIORITY_LABELS[p]}`,
            })
          }
        />
      ))}
    </Panel>
  )
}

export function CleanCoreDonut({ data, onOpenList }: { data: DashboardOverviewRecord; onOpenList: OpenList }) {
  const keys = [...Object.keys(RECOMMENDATION_CONFIG), UNCLASSIFIED]
  const slices = keys
    .map((key) => ({ key, label: recommendationConfig(key).label, hex: recommendationConfig(key).hex, value: data.clean_core_objects[key] ?? 0 }))
    .filter((s) => s.value > 0)
  const total = slices.reduce((acc, s) => acc + s.value, 0)

  const open = (key: string) =>
    onOpenList({
      type: 'list',
      entity: 'objects',
      filter: { recommendation: key },
      title: `Objetos — ${recommendationConfig(key).label}`,
    })

  return (
    <Panel title="Distribuição Clean Core Classification">
      {total === 0 ? (
        <div className="text-[12px] text-text-tertiary">Nenhum objeto classificado ainda — execute o processamento por IA.</div>
      ) : (
        <div className="flex flex-wrap items-center gap-4">
          <div className="relative mx-auto h-[190px] w-[190px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="label"
                  innerRadius={56}
                  outerRadius={90}
                  paddingAngle={1}
                  stroke="none"
                  onClick={(_, index) => open(slices[index].key)}
                  className="cursor-pointer"
                >
                  {slices.map((s) => (
                    <Cell key={s.key} fill={s.hex} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => fmt(Number(value))} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <div className="text-[22px] font-semibold text-text-primary">{fmt(total)}</div>
              <div className="text-[10px] text-text-tertiary">objetos</div>
            </div>
          </div>
          <div className="min-w-[200px] flex-1 space-y-0.5">
            {slices.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => open(s.key)}
                className="flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left text-[11px] hover:bg-surface-hover"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: s.hex }} />
                  <span className="text-text-primary">{s.label}</span>
                </span>
                <span className="shrink-0 whitespace-nowrap font-mono text-text-secondary">
                  {fmt(s.value)} <span className="text-text-tertiary">({Math.round((s.value / total) * 100)}%)</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </Panel>
  )
}

export function AtcPriorityBars({ data, onOpenList }: { data: DashboardOverviewRecord; onOpenList: OpenList }) {
  const bars = ['1', '2', '3'].map((p) => ({ key: p, label: `P${p}`, value: data.atc_by_priority[p] ?? 0 }))
  return (
    <Panel title="Findings ATC por Prioridade">
      {data.atc_run_id == null ? (
        <div className="text-[12px] text-text-tertiary">Sem findings ATC importados.</div>
      ) : (
        <div className="h-[220px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bars} layout="vertical" margin={{ top: 4, right: 48, bottom: 4, left: 4 }}>
              <XAxis type="number" tick={{ fill: '#9ca3af', fontSize: 10 }} tickFormatter={(v) => fmt(Number(v))} />
              <YAxis type="category" dataKey="label" width={32} tick={{ fill: '#d1d5db', fontSize: 11 }} />
              <Tooltip formatter={(value) => fmt(Number(value))} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
              <Bar
                dataKey="value"
                name="Findings"
                radius={[0, 3, 3, 0]}
                label={{ position: 'right', fill: '#d1d5db', fontSize: 11, formatter: (v: unknown) => fmt(Number(v)) }}
                onClick={(_, index) =>
                  onOpenList({
                    type: 'list',
                    entity: 'atc_findings',
                    filter: { priority: Number(bars[index].key) },
                    title: `Findings ATC — ${PRIORITY_LABELS[bars[index].key]}`,
                  })
                }
                className="cursor-pointer"
              >
                {bars.map((b) => (
                  <Cell key={b.key} fill={PRIORITY_COLORS[b.key]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  )
}
