/**
 * Full-page detail dispatcher for the Dashboard drill-down (SPRINT-18 CAP-003 / ADR-019). Reuses
 * the entity detail components and adds the ATC finding detail (raw imported record, ADR-016).
 */
import { useQuery } from '@tanstack/react-query'
import { ApplicationDetail } from '@/components/architecture/ApplicationBrowser'
import { RuleDetailPage } from '@/components/functional/BusinessRuleBrowser'
import { ObjectDetail, PriorityBadge } from '@/components/parsing/ObjectBrowser'
import { ErrorState } from '@/components/shared/ErrorState'
import { fetchATCFinding } from '@/lib/api'
import type { ResultFocus } from '@/lib/resultNav'

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value == null || value === '') return null
  return (
    <div>
      <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">{label}</div>
      <div className="mt-0.5 whitespace-pre-wrap text-[12px] text-text-primary">{value}</div>
    </div>
  )
}

function ATCFindingDetail({
  assessmentId,
  findingId,
  onNavigate,
}: {
  assessmentId: number
  findingId: number
  onNavigate: (target: ResultFocus) => void
}) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['atc-finding', assessmentId, findingId],
    queryFn: () => fetchATCFinding(assessmentId, findingId),
  })
  if (isLoading) return <div className="p-6 text-[12px] text-text-tertiary">Carregando…</div>
  if (isError || !data) return <ErrorState message="Não foi possível carregar o finding ATC." onRetry={refetch} />

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-6">
      <div className="flex items-center gap-2">
        <PriorityBadge priority={data.priority} />
        <div className="text-[15px] font-medium text-text-primary">{data.check_title ?? 'Finding ATC'}</div>
      </div>
      {data.check_message && <div className="text-[13px] text-text-secondary">{data.check_message}</div>}

      <div className="rounded border border-border-soft bg-surface-elevated px-3 py-2 text-[11px]">
        <div className="text-[10px] font-medium uppercase tracking-wide text-text-tertiary">Objeto</div>
        {data.correlated_object_id != null ? (
          <button
            type="button"
            onClick={() => onNavigate({ kind: 'sap_object', id: data.correlated_object_id as number })}
            className="mt-0.5 font-mono text-[12px] text-brand hover:underline"
          >
            {data.object_name_raw ?? `Objeto #${data.correlated_object_id}`} →
          </button>
        ) : (
          <div className="mt-0.5 font-mono text-[12px] text-text-primary">
            {data.object_name_raw ?? '—'}{' '}
            <span className="font-sans text-[11px] text-text-tertiary">
              (não correlacionado a um objeto do código-fonte{data.correlation_status ? ` — ${data.correlation_status}` : ''})
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Tipo do objeto" value={data.object_type_raw} />
        <Field label="Pacote" value={data.package_name_raw} />
        <Field label="Responsável pelo objeto" value={data.object_responsible} />
        <Field label="Última alteração por" value={data.last_changed_by} />
        <Field label="Encontrado pela primeira vez em" value={data.first_found_on} />
        <Field label="Estado de isenção" value={data.exemption_state} />
        <Field label="Nota SAP" value={data.sap_note_number} />
        <Field label="Descrição da nota SAP" value={data.sap_note_short_text} />
        <Field label="Componente referenciado" value={data.referenced_application_component} />
        <Field label="Objeto referenciado" value={[data.referenced_object_type, data.referenced_object_name].filter(Boolean).join(' ')} />
        <Field label="Categoria do Simplification Item" value={data.simplification_item_category} />
        <Field label="Categoria da mudança" value={data.change_category_description ?? data.change_category} />
      </div>
      <Field label="Informações adicionais" value={data.additional_info} />
      <Field label="Observações" value={data.remarks} />
      <div className="text-[10px] text-text-tertiary">
        Importação ATC #{data.atc_run_id} · linha {data.source_row_number}
      </div>
    </div>
  )
}

export function DetailPage({
  assessmentId,
  focus,
  onNavigate,
}: {
  assessmentId: number
  focus: ResultFocus
  onNavigate: (target: ResultFocus) => void
}) {
  switch (focus.kind) {
    case 'sap_object':
      return <ObjectDetail key={focus.id} assessmentId={assessmentId} objectId={focus.id} onNavigate={onNavigate} />
    case 'application':
      return <ApplicationDetail key={focus.id} assessmentId={assessmentId} applicationId={focus.id} onNavigate={onNavigate} />
    case 'business_rule':
      return <RuleDetailPage key={focus.id} assessmentId={assessmentId} ruleId={focus.id} onNavigate={onNavigate} />
    case 'atc_finding':
      return <ATCFindingDetail key={focus.id} assessmentId={assessmentId} findingId={focus.id} onNavigate={onNavigate} />
  }
}
