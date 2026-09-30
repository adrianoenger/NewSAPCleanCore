/**
 * Dashboard drill-down navigation (SPRINT-18 / ADR-019, supersedes the SPRINT-15 cross-view
 * focus). Dashboard Geral is the single results screen: KPIs/panels open a full-page `list`, a
 * list row opens a full-page `detail`, and details link to each other. The drill-down is a stack
 * (`DrillPage[]`) rendered with a breadcrumb; an empty stack is the dashboard root.
 */
import type { ATCFindingListFilter, ObjectListFilter } from '@/lib/api'

export type ResultFocus =
  | { kind: 'sap_object'; id: number }
  | { kind: 'business_rule'; id: number }
  | { kind: 'application'; id: number }
  | { kind: 'atc_finding'; id: number }

export type ListEntity = 'objects' | 'applications' | 'business_rules' | 'atc_findings'

export interface ApplicationListFilter {
  recommendation?: string
}

export type ListFilter = ObjectListFilter & ATCFindingListFilter & ApplicationListFilter

export type DrillPage =
  | { type: 'list'; entity: ListEntity; filter: ListFilter; title: string }
  | { type: 'detail'; focus: ResultFocus; label?: string }

/** Selection kinds the Copilot context builder understands (ai/copilot/context.py). */
export const COPILOT_SELECTION_KINDS: ReadonlySet<ResultFocus['kind']> = new Set([
  'sap_object',
  'business_rule',
  'application',
])
