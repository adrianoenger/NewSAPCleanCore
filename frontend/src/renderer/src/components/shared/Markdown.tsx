/**
 * Shared markdown renderer (SPRINT-18) for AI-generated text — Copilot answers and the Executive
 * Summary. Styled through a component map (no @tailwindcss/typography dependency). Raw HTML in
 * the markdown is never rendered (react-markdown's default), so model output cannot inject markup.
 */
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'

const COMPONENTS: Components = {
  h1: ({ children }) => <h1 className="mb-3 mt-5 text-[18px] font-semibold text-text-primary first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 mt-5 text-[15px] font-semibold text-text-primary first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1.5 mt-4 text-[13.5px] font-semibold text-text-primary first:mt-0">{children}</h3>,
  p: ({ children }) => <p className="mb-2 leading-relaxed last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-0.5 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-0.5 pl-5 last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-text-primary">{children}</strong>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-brand-text underline underline-offset-2">
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-surface-elevated px-1 py-0.5 font-mono text-[0.92em] text-text-primary">{children}</code>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-l-2 border-border-default pl-3 text-text-secondary">{children}</blockquote>
  ),
  table: ({ children }) => (
    <div className="mb-3 overflow-x-auto">
      <table className="w-full border-collapse text-left">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-border-default px-2 py-1 font-medium text-text-primary">{children}</th>,
  td: ({ children }) => <td className="border-b border-border-soft px-2 py-1 align-top">{children}</td>,
  hr: () => <hr className="my-4 border-border-soft" />,
}

export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn('break-words', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
