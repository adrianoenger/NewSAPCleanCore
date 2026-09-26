import { AlertTriangle, RefreshCw } from 'lucide-react'

interface Props {
  message?: string
  onRetry?: () => void
}

/** Shared error-state affordance (CAP-004, SPRINT-17) — distinguishes "request failed" from
 * "request succeeded with zero results" across list/detail queries, so a backend outage during
 * the demo never silently looks like an empty assessment. */
export function ErrorState({ message, onRetry }: Props) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 py-12 text-center">
      <AlertTriangle className="h-8 w-8 text-risk/60" strokeWidth={1.25} />
      <div className="text-[12px] text-risk">
        {message ?? 'Não foi possível carregar os dados. Verifique a conexão com o backend.'}
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="flex items-center gap-1.5 rounded-control border border-border-default px-3 py-1.5 text-[12px] text-text-secondary hover:border-brand/50 hover:text-text-primary"
        >
          <RefreshCw className="h-3.5 w-3.5" strokeWidth={2} />
          Tentar novamente
        </button>
      )}
    </div>
  )
}
