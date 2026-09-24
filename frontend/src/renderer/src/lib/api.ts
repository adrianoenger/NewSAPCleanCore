export const BACKEND_URL: string = import.meta.env.VITE_CCA_BACKEND_URL ?? 'http://localhost:8000'

/** Mirrors `HealthResponse` in backend/src/api/routes/health.py. */
export interface HealthResponse {
  status: 'ok' | 'degraded'
  service: string
  version: string
  environment: string
  database: {
    status: 'ok' | 'unavailable'
    pgvector: boolean
    migration_revision: string | null
    error: string | null
  }
}

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${BACKEND_URL}/health`, { signal })
  if (!response.ok) throw new Error(`Backend responded ${response.status}`)
  return (await response.json()) as HealthResponse
}

// ---------------------------------------------------------------------------
// SPRINT-01: Client / SAP System / Assessment types + fetchers
// ---------------------------------------------------------------------------

export interface ClientRecord {
  id: number
  name: string
  description: string | null
  created_at: string
}

export interface SAPSystemRecord {
  id: number
  client_id: number
  name: string
  sid: string | null
  description: string | null
  created_at: string
}

export interface AssessmentRecord {
  id: number
  sap_system_id: number
  name: string
  description: string | null
  status: string
  created_at: string
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, init)
  if (!response.ok) throw new Error(`API ${path} → ${response.status}`)
  return response.json() as Promise<T>
}

export const fetchClients = (): Promise<ClientRecord[]> => api('/clients')

export const fetchSystems = (clientId: number): Promise<SAPSystemRecord[]> =>
  api(`/clients/${clientId}/systems`)

export const fetchAssessments = (clientId: number, systemId: number): Promise<AssessmentRecord[]> =>
  api(`/clients/${clientId}/systems/${systemId}/assessments`)
