/**
 * Cross-view drill-down focus (SPRINT-15 / ADR-009). A `ResultFocus` names one entity a result
 * view should pre-select when navigated to — e.g. a business rule's source object opening in
 * Technical View. `FOCUS_VIEW` maps each focus kind to the nav item that renders it, so callers
 * only need to know the entity, not the view id.
 */
export type ResultFocus =
  | { kind: 'sap_object'; id: number }
  | { kind: 'business_rule'; id: number }
  | { kind: 'application'; id: number }

export const FOCUS_VIEW: Record<ResultFocus['kind'], string> = {
  sap_object: 'technical',
  business_rule: 'functional',
  application: 'architecture',
}
