/**
 * useAssessmentContext — global selection state for Client / Assessment.
 * Lives in App and is passed down as props.
 */

import type { AssessmentListItem, ClientRecord } from '@/lib/api'

export interface AssessmentContext {
  client: ClientRecord | null
  assessment: AssessmentListItem | null
  setClient: (client: ClientRecord | null) => void
  setAssessment: (assessment: AssessmentListItem | null) => void
}

/** @deprecated use AssessmentContext */
export type ClientContext = AssessmentContext
