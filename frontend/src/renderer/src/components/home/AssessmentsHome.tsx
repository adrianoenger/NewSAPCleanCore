/**
 * AssessmentsHome — first application screen.
 * Grid/list of all assessments, filters, Novo Assessment / Novo Cliente actions.
 * No left sidebar on this screen.
 */

import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, FileSearch, Plus, RefreshCw, X } from 'lucide-react'
import {
  createAssessment,
  createClient,
  fetchAssessments,
  fetchClients,
  type AssessmentListItem,
  type ClientRecord,
} from '@/lib/api'
import type { AssessmentContext } from '@/lib/useClientContext'
import { cn } from '@/lib/utils'

interface AssessmentsHomeProps {
  ctx: AssessmentContext
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    created: 'bg-surface-elevated text-text-secondary',
    in_progress: 'bg-brand/10 text-brand-text',
    completed: 'bg-success/10 text-success',
    failed: 'bg-risk/10 text-risk',
  }
  return (
    <span
      className={cn(
        'rounded px-1.5 py-0.5 text-[11px] font-medium',
        colors[status] ?? colors.created,
      )}
    >
      {status.replace('_', ' ')}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Novo Cliente modal
// ---------------------------------------------------------------------------

interface NovoClienteModalProps {
  onClose: () => void
  onCreated: (client: ClientRecord) => void
}

function NovoClienteModal({ onClose, onCreated }: NovoClienteModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setSaving(true)
    setError(null)
    try {
      const client = await createClient(name.trim(), description.trim() || undefined)
      onCreated(client)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-[420px] rounded-card border border-border-default bg-surface-card p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[16px] font-medium">Novo Cliente</h2>
          <button type="button" onClick={onClose} className="text-text-tertiary hover:text-text-primary">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-[12px] text-text-secondary">Nome *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full rounded-md border border-border-default bg-surface-background px-3 py-2 text-[13px] focus:border-brand focus:outline-none"
              placeholder="Nome do cliente"
            />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-text-secondary">Descrição</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-md border border-border-default bg-surface-background px-3 py-2 text-[13px] focus:border-brand focus:outline-none"
              placeholder="Opcional"
            />
          </div>
          {error && <p className="text-[12px] text-risk">{error}</p>}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border-default px-4 py-2 text-[13px] text-text-secondary hover:bg-surface-elevated"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving || !name.trim()}
              className="rounded-md bg-brand px-4 py-2 text-[13px] font-medium text-white hover:bg-brand/90 disabled:opacity-50"
            >
              {saving ? 'Salvando…' : 'Criar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Novo Assessment modal
// ---------------------------------------------------------------------------

interface NovoAssessmentModalProps {
  clients: ClientRecord[]
  onClose: () => void
  onCreated: (assessment: AssessmentListItem) => void
}

function NovoAssessmentModal({ clients, onClose, onCreated }: NovoAssessmentModalProps) {
  const [clientId, setClientId] = useState<string>(clients[0]?.id?.toString() ?? '')
  const [name, setName] = useState('')
  const [sapSourceSystem, setSapSourceSystem] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim() || !clientId) return
    setSaving(true)
    setError(null)
    try {
      const assessment = await createAssessment({
        client_id: Number(clientId),
        name: name.trim(),
        sap_source_system: sapSourceSystem.trim() || undefined,
        description: description.trim() || undefined,
      })
      const client = clients.find((c) => c.id === assessment.client_id)
      onCreated({ ...assessment, client_name: client?.name ?? '' })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-[460px] rounded-card border border-border-default bg-surface-card p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[16px] font-medium">Novo Assessment</h2>
          <button type="button" onClick={onClose} className="text-text-tertiary hover:text-text-primary">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-[12px] text-text-secondary">Cliente *</label>
            <select
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              required
              className="w-full rounded-md border border-border-default bg-surface-background px-3 py-2 text-[13px] focus:border-brand focus:outline-none"
            >
              {clients.length === 0 && <option value="">Nenhum cliente cadastrado</option>}
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-text-secondary">Nome *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full rounded-md border border-border-default bg-surface-background px-3 py-2 text-[13px] focus:border-brand focus:outline-none"
              placeholder="Nome do assessment"
            />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-text-secondary">Sistema SAP de origem</label>
            <input
              type="text"
              value={sapSourceSystem}
              onChange={(e) => setSapSourceSystem(e.target.value)}
              className="w-full rounded-md border border-border-default bg-surface-background px-3 py-2 text-[13px] focus:border-brand focus:outline-none"
              placeholder="ex: S/4HANA 2023 (PRD)"
            />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-text-secondary">Descrição</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-md border border-border-default bg-surface-background px-3 py-2 text-[13px] focus:border-brand focus:outline-none"
              placeholder="Opcional"
            />
          </div>
          {error && <p className="text-[12px] text-risk">{error}</p>}
          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border-default px-4 py-2 text-[13px] text-text-secondary hover:bg-surface-elevated"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving || !name.trim() || !clientId}
              className="rounded-md bg-brand px-4 py-2 text-[13px] font-medium text-white hover:bg-brand/90 disabled:opacity-50"
            >
              {saving ? 'Criando…' : 'Criar Assessment'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function AssessmentsHome({ ctx }: AssessmentsHomeProps) {
  const queryClient = useQueryClient()
  const [filterClient, setFilterClient] = useState<string>('')
  const [filterName, setFilterName] = useState<string>('')
  const [showNovoCliente, setShowNovoCliente] = useState(false)
  const [showNovoAssessment, setShowNovoAssessment] = useState(false)

  const clientsQuery = useQuery({ queryKey: ['clients'], queryFn: fetchClients })

  const assessmentsQuery = useQuery({
    queryKey: ['assessments', filterClient, filterName],
    queryFn: () =>
      fetchAssessments({
        client_id: filterClient ? Number(filterClient) : undefined,
        name: filterName || undefined,
      }),
  })

  function handleOpen(assessment: AssessmentListItem) {
    const client = clientsQuery.data?.find((c) => c.id === assessment.client_id) ?? null
    ctx.setClient(client)
    ctx.setAssessment(assessment)
  }

  function handleClientCreated(client: ClientRecord) {
    setShowNovoCliente(false)
    void queryClient.invalidateQueries({ queryKey: ['clients'] })
    setFilterClient(String(client.id))
  }

  function handleAssessmentCreated(assessment: AssessmentListItem) {
    setShowNovoAssessment(false)
    void queryClient.invalidateQueries({ queryKey: ['assessments'] })
    handleOpen(assessment)
  }

  const assessments = assessmentsQuery.data ?? []

  return (
    <div className="flex h-full flex-col">
      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-border-soft px-6 py-4">
        <div>
          <h1 className="text-[20px] font-semibold">Assessments</h1>
          <p className="mt-0.5 text-[12px] text-text-tertiary">
            Selecione um assessment existente ou crie um novo.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowNovoCliente(true)}
            className="flex items-center gap-1.5 rounded-md border border-border-default px-3 py-2 text-[13px] text-text-secondary hover:bg-surface-elevated hover:text-text-primary"
          >
            <Building2 className="h-3.5 w-3.5" />
            Novo Cliente
          </button>
          <button
            type="button"
            onClick={() => setShowNovoAssessment(true)}
            disabled={!clientsQuery.data || clientsQuery.data.length === 0}
            className="flex items-center gap-1.5 rounded-md bg-brand px-3 py-2 text-[13px] font-medium text-white hover:bg-brand/90 disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" />
            Novo Assessment
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3 border-b border-border-soft px-6 py-3">
        <select
          value={filterClient}
          onChange={(e) => setFilterClient(e.target.value)}
          className="rounded-md border border-border-default bg-surface-background px-3 py-1.5 text-[13px] text-text-secondary focus:border-brand focus:outline-none"
        >
          <option value="">Todos os clientes</option>
          {clientsQuery.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={filterName}
          onChange={(e) => setFilterName(e.target.value)}
          placeholder="Buscar por nome…"
          className="w-60 rounded-md border border-border-default bg-surface-background px-3 py-1.5 text-[13px] focus:border-brand focus:outline-none"
        />
        <button
          type="button"
          onClick={() => void queryClient.invalidateQueries({ queryKey: ['assessments'] })}
          className="ml-auto text-text-tertiary hover:text-text-secondary"
          title="Atualizar"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Assessment grid */}
      <div className="flex-1 overflow-auto p-6">
        {assessmentsQuery.isLoading && (
          <p className="text-[13px] text-text-tertiary">Carregando…</p>
        )}
        {assessmentsQuery.isError && (
          <p className="text-[13px] text-risk">Erro ao carregar assessments</p>
        )}
        {!assessmentsQuery.isLoading && assessments.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <FileSearch className="h-10 w-10 text-text-tertiary" strokeWidth={1.5} />
            <p className="text-[14px] text-text-secondary">Nenhum assessment encontrado.</p>
            <p className="text-[12px] text-text-tertiary">
              Crie um novo assessment para começar a análise.
            </p>
          </div>
        )}
        {assessments.length > 0 && (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
            {assessments.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => handleOpen(a)}
                className="rounded-card border border-border-default bg-surface-card p-4 text-left transition-colors hover:border-brand/50 hover:bg-surface-elevated"
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <span className="text-[14px] font-medium text-text-primary leading-snug">
                    {a.name}
                  </span>
                  <StatusBadge status={a.status} />
                </div>
                <div className="flex items-center gap-1.5 text-[12px] text-text-tertiary">
                  <Building2 className="h-3 w-3 shrink-0" strokeWidth={1.75} />
                  <span className="truncate">{a.client_name}</span>
                </div>
                {a.sap_source_system && (
                  <div className="mt-1 text-[11px] font-mono text-text-tertiary truncate">
                    {a.sap_source_system}
                  </div>
                )}
                {a.description && (
                  <p className="mt-2 line-clamp-2 text-[12px] text-text-secondary">
                    {a.description}
                  </p>
                )}
                <p className="mt-2 text-[11px] text-text-tertiary">
                  {new Date(a.created_at).toLocaleDateString('pt-BR')}
                </p>
              </button>
            ))}
          </div>
        )}
      </div>

      {showNovoCliente && (
        <NovoClienteModal
          onClose={() => setShowNovoCliente(false)}
          onCreated={handleClientCreated}
        />
      )}
      {showNovoAssessment && clientsQuery.data && (
        <NovoAssessmentModal
          clients={clientsQuery.data}
          onClose={() => setShowNovoAssessment(false)}
          onCreated={handleAssessmentCreated}
        />
      )}
    </div>
  )
}
