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

// ---------------------------------------------------------------------------
// SPRINT-02: Source Ingestion types + fetchers
// ---------------------------------------------------------------------------

export interface CategoryCount {
  category: string
  count: number
}

export interface ScanRecord {
  id: number
  assessment_id: number
  source_path: string
  status: 'pending' | 'scanning' | 'completed' | 'failed'
  total_files: number
  scanned_files: number
  error: string | null
  started_at: string
  completed_at: string | null
}

export interface ScanDetail extends ScanRecord {
  category_counts: CategoryCount[]
}

export interface SourceFileRecord {
  id: number
  scan_id: number
  assessment_id: number
  rel_path: string
  size_bytes: number
  mtime: number
  sha256: string
  category: string
}

export interface ScanConfig {
  scan_root: string
  demo_path: string
}

export const fetchScanConfig = (): Promise<ScanConfig> => api('/ingestion/config')

export const fetchScans = (assessmentId: number): Promise<ScanRecord[]> =>
  api(`/assessments/${assessmentId}/scans`)

export const fetchScan = (assessmentId: number, scanId: number): Promise<ScanDetail> =>
  api(`/assessments/${assessmentId}/scans/${scanId}`)

export const startScan = (assessmentId: number, sourcePath: string): Promise<ScanRecord> =>
  api(`/assessments/${assessmentId}/scans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_path: sourcePath }),
  })

export const fetchSourceFiles = (
  assessmentId: number,
  scanId?: number,
): Promise<SourceFileRecord[]> => {
  const qs = scanId != null ? `?scan_id=${scanId}` : ''
  return api(`/assessments/${assessmentId}/source-files${qs}`)
}

// ---------------------------------------------------------------------------
// SPRINT-03: SAP Object Parsing types + fetchers
// ---------------------------------------------------------------------------

export interface SAPObjectRecord {
  id: number
  assessment_id: number
  source_file_id: number
  object_type: string
  object_name: string
  description: string
  line_start: number
  line_end: number | null
  parsed_at: string
}

export interface SAPObjectDetail extends SAPObjectRecord {
  attributes: Record<string, unknown>
}

export interface ParseJobResult {
  scan_id: number
  status: string
}

export const triggerParse = (assessmentId: number, scanId: number): Promise<ParseJobResult> =>
  api(`/assessments/${assessmentId}/scans/${scanId}/parse`, { method: 'POST' })

export const fetchSAPObjects = (
  assessmentId: number,
  objectType?: string,
): Promise<SAPObjectRecord[]> => {
  const qs = objectType ? `?object_type=${encodeURIComponent(objectType)}` : ''
  return api(`/assessments/${assessmentId}/objects${qs}`)
}

export const fetchSAPObject = (
  assessmentId: number,
  objectId: number,
): Promise<SAPObjectDetail> => api(`/assessments/${assessmentId}/objects/${objectId}`)
