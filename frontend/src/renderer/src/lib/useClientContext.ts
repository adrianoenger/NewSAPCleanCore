/**
 * useClientContext — global selection state for Client / SAP System / Assessment.
 * Lives in App and is passed down as props; no external state library needed at PoC scale.
 */

import type { AssessmentRecord, ClientRecord, SAPSystemRecord } from '@/lib/api'

export interface ClientContext {
  client: ClientRecord | null
  system: SAPSystemRecord | null
  assessment: AssessmentRecord | null
  setClient: (client: ClientRecord | null) => void
  setSystem: (system: SAPSystemRecord | null) => void
  setAssessment: (assessment: AssessmentRecord | null) => void
}
