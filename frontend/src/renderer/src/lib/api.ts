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
// SPRINT-04: Client and Assessment types + fetchers (Assessment-centric)
// ---------------------------------------------------------------------------

export interface ClientRecord {
  id: number
  name: string
  description: string | null
  created_at: string
}

export interface AssessmentRecord {
  id: number
  client_id: number
  name: string
  sap_source_system: string | null
  description: string | null
  status: string
  created_at: string
}

export interface AssessmentListItem extends AssessmentRecord {
  client_name: string
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, init)
  if (!response.ok) throw new Error(`API ${path} → ${response.status}`)
  return response.json() as Promise<T>
}

export const fetchClients = (): Promise<ClientRecord[]> => api('/clients')

export const createClient = (name: string, description?: string): Promise<ClientRecord> =>
  api('/clients', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description: description ?? null }),
  })

export const fetchAssessments = (params?: {
  client_id?: number
  name?: string
}): Promise<AssessmentListItem[]> => {
  const qs = new URLSearchParams()
  if (params?.client_id != null) qs.set('client_id', String(params.client_id))
  if (params?.name) qs.set('name', params.name)
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return api(`/assessments${query}`)
}

export const createAssessment = (body: {
  client_id: number
  name: string
  sap_source_system?: string
  description?: string
}): Promise<AssessmentRecord> =>
  api('/assessments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

export const fetchAssessment = (id: number): Promise<AssessmentRecord> =>
  api(`/assessments/${id}`)

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
  duration_seconds: number | null
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

export interface ObjectUnderstandingEvidenceRef {
  ref_id: string
  source_type: string
  entity_id: number
}

export interface ObjectUnderstandingRecord {
  status: 'COMPLETED' | 'INSUFFICIENT_CONTEXT' | 'FAILED'
  functional_purpose: string
  technical_purpose: string
  concepts: string[]
  confidence: number | null
  rationale: string
  evidence_refs: ObjectUnderstandingEvidenceRef[]
  provider: string
  model_id: string
  prompt_capability: string
  prompt_version: string
  error: string | null
  updated_at: string
}

export interface SAPObjectDetail extends SAPObjectRecord {
  attributes: Record<string, unknown>
  understanding: ObjectUnderstandingRecord | null
}

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

// ---------------------------------------------------------------------------
// SPRINT-05: Dependencies, ATC runs/findings
// ---------------------------------------------------------------------------

export interface DependencyRecord {
  id: number
  source_object_id: number
  target_name: string
  target_type: string | null
  dep_type: string
  source_line: number | null
  confidence: string
}

export interface DependenciesResponse {
  assessment_id: number
  object_id: number
  dependencies: DependencyRecord[]
  total: number
}

export const fetchObjectDependencies = (
  assessmentId: number,
  objectId: number,
): Promise<DependenciesResponse> =>
  api(`/assessments/${assessmentId}/objects/${objectId}/dependencies`)

export const detectAllDependencies = (assessmentId: number): Promise<{ assessment_id: number; objects_processed: number; dependencies_detected: number }> =>
  api(`/assessments/${assessmentId}/detect-dependencies`, { method: 'POST' })

export interface ATCDiagnostics {
  worksheet: string
  total_rows: number
  recognized_columns: string[]
  missing_known_columns: string[]
  unknown_columns: string[]
  original_headers: string[]
  validation_status: string
  warnings: string[]
}

export interface ATCRunRecord {
  id: number
  assessment_id: number
  source_filename: string
  selected_worksheet: string | null
  original_headers: string[]
  canonical_mapping: Record<string, unknown>
  unknown_headers: string[]
  missing_known_headers: string[]
  importer_version: string
  imported_row_count: number
  warning_count: number
  validation_status: string
  warnings_summary: string[]
  imported_at: string
}

export interface ATCRunListResponse {
  assessment_id: number
  runs: ATCRunRecord[]
  total: number
}

export interface ATCFindingRecord {
  id: number
  atc_run_id: number
  assessment_id: number
  source_row_number: number
  priority: number | null
  check_title: string | null
  check_message: string | null
  object_name_raw: string | null
  object_type_raw: string | null
  exemption_state: string | null
  package_name_raw: string | null
  first_found_on: string | null
  sap_note_number: string | null
  correlation_status: string | null
  correlated_object_id: number | null
  mapping_warnings: string[]
}

export interface ATCFindingsResponse {
  assessment_id: number
  atc_run_id: number
  findings: ATCFindingRecord[]
  total: number
  correlation_summary: Record<string, number>
}

export const inspectATCFile = async (assessmentId: number, file: File): Promise<ATCDiagnostics> => {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${BACKEND_URL}/assessments/${assessmentId}/atc/inspect`, { method: 'POST', body: form })
  if (!resp.ok) throw new Error(`inspectATCFile → ${resp.status}`)
  return resp.json()
}

export const importATCFile = async (assessmentId: number, file: File): Promise<ATCRunRecord> => {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${BACKEND_URL}/assessments/${assessmentId}/atc/import`, { method: 'POST', body: form })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error(body?.detail?.message ?? `importATCFile → ${resp.status}`)
  }
  return resp.json()
}

export const fetchATCRuns = (assessmentId: number): Promise<ATCRunListResponse> =>
  api(`/assessments/${assessmentId}/atc/runs`)

export const fetchATCFindings = (
  assessmentId: number,
  runId: number,
  limit = 200,
  offset = 0,
): Promise<ATCFindingsResponse> =>
  api(`/assessments/${assessmentId}/atc/runs/${runId}/findings?limit=${limit}&offset=${offset}`)

// ---------------------------------------------------------------------------
// SPRINT-06: Durable Pipeline Execution (ADR-005)
// ---------------------------------------------------------------------------

export interface StageRunRecord {
  id: number
  stage_key: 'scan' | 'parse' | 'detect_dependencies' | 'object_understanding'
  sequence: number
  depends_on: string[]
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'skipped'
  total_items: number
  completed_items: number
  failed_items: number
  started_at: string | null
  completed_at: string | null
  error: string | null
}

export interface PipelineRunRecord {
  id: number
  assessment_id: number
  source_path: string
  source_scan_id: number | null
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed'
  pause_requested: boolean
  error: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  stages: StageRunRecord[]
}

export interface PipelineRunListResponse {
  assessment_id: number
  runs: PipelineRunRecord[]
  total: number
}

export interface WorkItemRecord {
  id: number
  stage_run_id: number
  item_key: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  attempts: number
  max_attempts: number
  last_error: string | null
  started_at: string | null
  completed_at: string | null
}

export interface WorkItemsResponse {
  items: WorkItemRecord[]
  total: number
}

export interface ProcessingStatusRecord {
  current_scan_id: number | null
  current_scan_source_path: string | null
  current_scan_completed_at: string | null
  is_processed: boolean
  is_stale: boolean
  latest_run_id: number | null
  latest_run_status: string | null
}

async function apiOrDetail<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body?.detail === 'string' ? body.detail : `API ${path} → ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const startPipelineRun = (
  assessmentId: number,
  sourcePath: string,
): Promise<PipelineRunRecord> =>
  apiOrDetail(`/assessments/${assessmentId}/pipeline-runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_path: sourcePath }),
  })

export const fetchPipelineRuns = (assessmentId: number): Promise<PipelineRunListResponse> =>
  api(`/assessments/${assessmentId}/pipeline-runs`)

export const fetchProcessingStatus = (assessmentId: number): Promise<ProcessingStatusRecord> =>
  api(`/assessments/${assessmentId}/pipeline-runs/processing-status`)

export const fetchPipelineRun = (
  assessmentId: number,
  runId: number,
): Promise<PipelineRunRecord> => api(`/assessments/${assessmentId}/pipeline-runs/${runId}`)

export const fetchPipelineWorkItems = (
  assessmentId: number,
  runId: number,
  params?: { stage_key?: string; status?: string },
): Promise<WorkItemsResponse> => {
  const qs = new URLSearchParams()
  if (params?.stage_key) qs.set('stage_key', params.stage_key)
  if (params?.status) qs.set('status', params.status)
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return api(`/assessments/${assessmentId}/pipeline-runs/${runId}/work-items${query}`)
}

export const pausePipelineRun = (
  assessmentId: number,
  runId: number,
): Promise<PipelineRunRecord> =>
  apiOrDetail(`/assessments/${assessmentId}/pipeline-runs/${runId}/pause`, { method: 'POST' })

export const resumePipelineRun = (
  assessmentId: number,
  runId: number,
): Promise<PipelineRunRecord> =>
  apiOrDetail(`/assessments/${assessmentId}/pipeline-runs/${runId}/resume`, { method: 'POST' })

export const retryWorkItem = (
  assessmentId: number,
  runId: number,
  itemId: number,
): Promise<WorkItemRecord> =>
  apiOrDetail(`/assessments/${assessmentId}/pipeline-runs/${runId}/work-items/${itemId}/retry`, {
    method: 'POST',
  })

// ---------------------------------------------------------------------------
// SPRINT-08: Supplemental Evidence Datasets (ADR-017)
// ---------------------------------------------------------------------------

export type EvidenceDatasetStatus =
  | 'INSPECTED'
  | 'IMPORTING'
  | 'IMPORTED_FULL'
  | 'IMPORTED_PARTIAL'
  | 'FAILED'

export interface EvidenceDatasetRecord {
  id: number
  assessment_id: number
  dataset_type: string
  display_name: string
  source_filename: string
  source_sha256: string
  source_size_bytes: number
  importer_name: string
  importer_version: string
  status: EvidenceDatasetStatus
  source_system_hint: string | null
  source_client_hint: string | null
  extracted_at: string | null
  capabilities: string[]
  manifest: Record<string, unknown>
  warning_summary: string[]
  error: string | null
  created_at: string
  updated_at: string
  records_count: number
  correlation_summary: Record<string, number>
  pipeline_run_id: number | null
  pipeline_run_status: string | null
}

export interface EvidenceDatasetListResponse {
  assessment_id: number
  datasets: EvidenceDatasetRecord[]
  total: number
}

export interface EvidenceRecordSummary {
  id: number
  dataset_id: number
  record_type: string
  capability: string
  object_name: string | null
  object_type: string | null
  package_name: string | null
  normalized_payload: Record<string, unknown>
  source_locator: Record<string, unknown>
}

export interface EvidenceCorrelationRecord {
  id: number
  target_type: string
  target_id: number | null
  status: string
  method: string
  score: number | null
  rationale: Record<string, unknown> | null
  created_at: string
  evidence_record: EvidenceRecordSummary
  dataset_display_name: string
  dataset_type: string
}

export interface ObjectEvidenceCorrelationsResponse {
  assessment_id: number
  object_id: number
  correlations: EvidenceCorrelationRecord[]
  total: number
}

export const fetchEvidenceDatasets = (assessmentId: number): Promise<EvidenceDatasetListResponse> =>
  api(`/assessments/${assessmentId}/evidence-datasets`)

export const fetchEvidenceDataset = (
  assessmentId: number,
  datasetId: number,
): Promise<EvidenceDatasetRecord> => api(`/assessments/${assessmentId}/evidence-datasets/${datasetId}`)

export const createEvidenceDataset = async (
  assessmentId: number,
  file: File,
): Promise<EvidenceDatasetRecord> => {
  const form = new FormData()
  form.append('file', file)
  const resp = await fetch(`${BACKEND_URL}/assessments/${assessmentId}/evidence-datasets`, {
    method: 'POST',
    body: form,
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error(typeof body?.detail === 'string' ? body.detail : `createEvidenceDataset → ${resp.status}`)
  }
  return resp.json()
}

export const deleteEvidenceDataset = async (assessmentId: number, datasetId: number): Promise<void> => {
  const resp = await fetch(`${BACKEND_URL}/assessments/${assessmentId}/evidence-datasets/${datasetId}`, {
    method: 'DELETE',
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error(typeof body?.detail === 'string' ? body.detail : `deleteEvidenceDataset → ${resp.status}`)
  }
}

export const fetchObjectEvidenceCorrelations = (
  assessmentId: number,
  objectId: number,
): Promise<ObjectEvidenceCorrelationsResponse> =>
  api(`/assessments/${assessmentId}/objects/${objectId}/evidence-correlations`)

// ---------------------------------------------------------------------------
// SPRINT-10: Business Rule Discovery (ADR-008/ADR-012)
// ---------------------------------------------------------------------------

export interface BusinessRuleEvidenceRef {
  ref_id: string
  source_type: string
  entity_id: number
}

export interface BusinessRuleRecord {
  id: number
  assessment_id: number
  sap_object_id: number
  rule_type: 'VALIDATION' | 'CALCULATION' | 'AUTHORIZATION' | 'WORKFLOW' | 'DATA_INTEGRITY' | 'OTHER'
  condition: string
  action: string
  confidence: number
  rationale: string
  evidence_refs: BusinessRuleEvidenceRef[]
  status: 'CANDIDATE' | 'MERGED'
  consolidated_into_id: number | null
  user_validated: boolean
  user_validated_at: string | null
  user_notes: string | null
  provider: string
  model_id: string
  prompt_capability: string
  prompt_version: string
  created_at: string
  updated_at: string
}

export interface BusinessRuleListResponse {
  assessment_id: number
  rules: BusinessRuleRecord[]
  total: number
}

export const fetchBusinessRules = (
  assessmentId: number,
  objectId?: number,
): Promise<BusinessRuleListResponse> => {
  const qs = objectId != null ? `?object_id=${objectId}` : ''
  return api(`/assessments/${assessmentId}/business-rules${qs}`)
}

export const validateBusinessRule = (
  assessmentId: number,
  ruleId: number,
  userValidated: boolean,
  userNotes?: string | null,
): Promise<BusinessRuleRecord> =>
  apiOrDetail(`/assessments/${assessmentId}/business-rules/${ruleId}/validate`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_validated: userValidated, user_notes: userNotes ?? null }),
  })
