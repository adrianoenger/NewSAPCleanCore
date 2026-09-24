import { PanelRightClose, PanelRightOpen, Send, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface CopilotPanelProps {
  collapsed: boolean
  onToggle: () => void
  contextLabel: string
}

/** Permanent right-side Copilot (ADR-010). Placeholder until the chat capability lands in SPRINT-13. */
export function CopilotPanel({ collapsed, onToggle, contextLabel }: CopilotPanelProps) {
  if (collapsed) {
    return (
      <aside
        data-region="copilot"
        data-collapsed="true"
        className="flex w-12 shrink-0 flex-col items-center gap-3 border-l border-border-default bg-surface-sidebar py-3"
      >
        <Button variant="ghost" size="icon" onClick={onToggle} aria-label="Open AI Copilot">
          <PanelRightOpen className="h-4 w-4" />
        </Button>
        <Sparkles className="h-4 w-4 text-brand-text" aria-hidden />
      </aside>
    )
  }

  return (
    <aside
      data-region="copilot"
      data-collapsed="false"
      className="flex w-[30%] max-w-[560px] min-w-[340px] shrink-0 flex-col border-l border-border-default bg-surface-sidebar"
    >
      <header className="flex h-14 items-center justify-between border-b border-border-soft px-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-brand-text" aria-hidden />
          <span className="text-[14px] font-medium">AI Copilot</span>
        </div>
        <Button variant="ghost" size="icon" onClick={onToggle} aria-label="Collapse AI Copilot">
          <PanelRightClose className="h-4 w-4" />
        </Button>
      </header>

      <div className="border-b border-border-soft px-4 py-2.5">
        <div className="mb-1.5 text-[10.5px] tracking-wide text-text-tertiary uppercase">Context</div>
        <span className="inline-flex items-center rounded-chip border border-brand-border bg-brand-tint px-2 py-0.5 font-mono text-[11.5px] text-brand-text-soft">
          {contextLabel}
        </span>
      </div>

      <div className="flex flex-1 items-center justify-center px-8 text-center">
        <p className="text-[13px] leading-relaxed text-text-secondary">
          The Copilot will answer questions about the current assessment context and link every
          answer to evidence. It becomes available in a later sprint.
        </p>
      </div>

      <div className="border-t border-border-soft p-3">
        <div className="flex items-center gap-2 rounded-card border border-border-default bg-surface-card px-3 py-2">
          <input
            disabled
            placeholder="Ask about this assessment…"
            className="flex-1 bg-transparent text-[13px] text-text-primary placeholder:text-text-tertiary focus:outline-none"
          />
          <Button variant="primary" size="icon" disabled aria-label="Send">
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </aside>
  )
}
