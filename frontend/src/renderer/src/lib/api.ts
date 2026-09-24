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
