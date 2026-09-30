import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { AlertTriangle, Info, Loader2, PanelRightClose, PanelRightOpen, Send, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Markdown } from '@/components/shared/Markdown'
import { SOURCE_TYPE_LABELS } from '@/components/shared/evidenceLabels'
import { askCopilot, type CopilotAskResponse, type CopilotMessageTurn, type CopilotReferenceRecord } from '@/lib/api'
import type { ResultFocus } from '@/lib/resultNav'

interface CopilotPanelProps {
  collapsed: boolean
  onToggle: () => void
  contextLabel: string
  assessmentId: number | null
  view: string
  selection: ResultFocus | null
  onNavigate: (target: ResultFocus) => void
  width: number
}

interface CopilotMessage {
  role: 'user' | 'assistant'
  content: string
  references?: CopilotReferenceRecord[]
  navigation?: ResultFocus | null
  status?: CopilotAskResponse['status']
}

const NAVIGATION_LABEL: Record<ResultFocus['kind'], string> = {
  sap_object: 'Ver objeto SAP',
  business_rule: 'Ver regra de negócio',
  application: 'Ver aplicação',
  atc_finding: 'Ver finding ATC',
}

const FAILED_MESSAGE = 'Falha ao consultar a IA — tente novamente ou reformule a pergunta.'
const INSUFFICIENT_FALLBACK = 'Não encontrei evidência suficiente no assessment para responder a isso.'

/** Models sometimes emit "•" bullets on consecutive lines; turn them into markdown list items so
 * they don't collapse into a single paragraph. */
function normalizeAnswer(text: string): string {
  return text.replace(/^[ \t]*[•·][ \t]*/gm, '- ').replace(/([^\n])\n(- )/g, '$1\n\n$2')
}

function ReferenceChips({ references }: { references: CopilotReferenceRecord[] }) {
  if (references.length === 0) return null
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {references.map((ref) => (
        <span
          key={ref.ref_id}
          title={SOURCE_TYPE_LABELS[ref.source_type] ?? ref.source_type}
          className="rounded bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary"
        >
          {ref.ref_id}
        </span>
      ))}
    </div>
  )
}

/** Permanent right-side Copilot (ADR-010) — real chat since SPRINT-16. Message state lives here,
 * not in App.tsx: this component is never unmounted while an assessment is open (it renders
 * outside Workspace's conditional), so the conversation naturally survives view/focus changes. */
export function CopilotPanel({
  collapsed,
  onToggle,
  contextLabel,
  assessmentId,
  view,
  selection,
  onNavigate,
  width,
}: CopilotPanelProps) {
  const [messages, setMessages] = useState<CopilotMessage[]>([])
  const [input, setInput] = useState('')

  const mutation = useMutation({
    mutationFn: (question: string) => {
      const history: CopilotMessageTurn[] = messages
        .slice(-10)
        .map((m) => ({ role: m.role, content: m.content }))
      return askCopilot(assessmentId as number, { question, view, selection, history })
    },
    onSuccess: (resp) => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: resp.status === 'FAILED' ? FAILED_MESSAGE : resp.answer || INSUFFICIENT_FALLBACK,
          references: resp.references,
          navigation: resp.navigation,
          status: resp.status,
        },
      ])
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Erro de comunicação com o backend. Tente novamente.', status: 'FAILED' },
      ])
    },
  })

  const handleSend = () => {
    const question = input.trim()
    if (!question || assessmentId == null || mutation.isPending) return
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setInput('')
    mutation.mutate(question)
  }

  if (collapsed) {
    return (
      <aside
        data-region="copilot"
        data-collapsed="true"
        className="flex w-12 shrink-0 flex-col items-center gap-3 border-l border-border-default bg-surface-sidebar py-3"
      >
        <Button variant="ghost" size="icon" onClick={onToggle} aria-label="Abrir AIDA">
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
      style={{ width }}
      className="flex shrink-0 flex-col overflow-hidden border-l border-border-default bg-surface-sidebar"
    >
      <header className="flex h-14 items-center justify-between border-b border-border-soft px-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-brand-text" aria-hidden />
          <span className="text-[14px] font-medium">AIDA</span>
        </div>
        <Button variant="ghost" size="icon" onClick={onToggle} aria-label="Recolher AIDA">
          <PanelRightClose className="h-4 w-4" />
        </Button>
      </header>

      <div className="border-b border-border-soft px-4 py-2.5">
        <div className="mb-1.5 text-[10.5px] tracking-wide text-text-tertiary uppercase">Contexto</div>
        <span className="inline-flex items-center rounded-chip border border-brand-border bg-brand-tint px-2 py-0.5 font-mono text-[11.5px] text-brand-text-soft">
          {contextLabel}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3" data-testid="copilot-messages">
        {assessmentId == null ? (
          <div className="flex h-full items-center justify-center px-4 text-center">
            <p className="text-[13px] leading-relaxed text-text-secondary">
              O Copilot responde perguntas sobre a assessment aberta e vincula cada resposta a
              evidência. Abra uma assessment para começar.
            </p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex h-full items-center justify-center px-4 text-center">
            <p className="text-[13px] leading-relaxed text-text-secondary">
              Converse com a AIDA sobre esta assessment. Explore resultados, riscos, dependências,
              regras de negócio e recomendações de Clean Core. Para uma análise mais contextual,
              abra um item no Dashboard e faça sua pergunta.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((m, i) => (
              <div
                key={i}
                className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
              >
                <div
                  className={
                    m.role === 'user'
                      ? 'max-w-[85%] rounded-card bg-brand px-3 py-2 text-[12.5px] text-white'
                      : 'max-w-[85%] rounded-card border border-border-soft bg-surface-card px-3 py-2 text-[12.5px] text-text-primary'
                  }
                >
                  {m.status === 'FAILED' && m.role === 'assistant' && (
                    <div className="mb-1 flex items-center gap-1 text-[10px] text-risk">
                      <AlertTriangle className="h-3 w-3" strokeWidth={2} />
                      Falha ao consultar a IA
                    </div>
                  )}
                  {m.status === 'INSUFFICIENT_CONTEXT' && m.role === 'assistant' && (
                    <div className="mb-1 flex items-center gap-1 text-[10px] text-text-tertiary">
                      <Info className="h-3 w-3" strokeWidth={2} />
                      Sem evidência suficiente
                    </div>
                  )}
                  {m.role === 'assistant' ? <Markdown>{normalizeAnswer(m.content)}</Markdown> : <div>{m.content}</div>}
                  {m.references && <ReferenceChips references={m.references} />}
                  {m.navigation && (
                    <button
                      type="button"
                      onClick={() => onNavigate(m.navigation as ResultFocus)}
                      className="mt-1.5 text-[11px] font-medium text-brand-text underline-offset-2 hover:underline"
                    >
                      {NAVIGATION_LABEL[m.navigation.kind]} →
                    </button>
                  )}
                </div>
              </div>
            ))}
            {mutation.isPending && (
              <div className="flex justify-start">
                <div className="flex items-center gap-1.5 rounded-card border border-border-soft bg-surface-card px-3 py-2 text-[12px] text-text-tertiary">
                  <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
                  Pensando…
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="border-t border-border-soft p-3">
        <div className="flex items-center gap-2 rounded-card border border-border-default bg-surface-card px-3 py-2">
          <input
            disabled={assessmentId == null}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="Pergunte sobre esta assessment…"
            className="flex-1 bg-transparent text-[13px] text-text-primary placeholder:text-text-tertiary focus:outline-none disabled:cursor-not-allowed"
          />
          <Button
            variant="primary"
            size="icon"
            disabled={assessmentId == null || !input.trim() || mutation.isPending}
            onClick={handleSend}
            aria-label="Enviar"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </aside>
  )
}
