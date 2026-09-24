import type { Connectivity } from '@/lib/useHealth'
import { cn } from '@/lib/utils'

const LABELS: Record<Connectivity, string> = {
  checking: 'Checking backend…',
  online: 'Backend online',
  degraded: 'Database unavailable',
  offline: 'Backend offline'
}

const DOT: Record<Connectivity, string> = {
  checking: 'bg-text-tertiary',
  online: 'bg-success',
  degraded: 'bg-attention',
  offline: 'bg-risk'
}

export function ConnectionIndicator({ connectivity }: { connectivity: Connectivity }) {
  return (
    <div
      className="flex items-center gap-2 text-[12px] text-text-secondary"
      data-testid="connection-indicator"
      data-connectivity={connectivity}
    >
      <span className={cn('h-2 w-2 rounded-full', DOT[connectivity])} aria-hidden />
      <span>{LABELS[connectivity]}</span>
    </div>
  )
}
