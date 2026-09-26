import Editor, { type OnMount } from '@monaco-editor/react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, FileCode2 } from 'lucide-react'
import { fetchObjectSource } from '@/lib/api'

interface Props {
  assessmentId: number
  objectId: number
}

/** Monaco-backed source viewer for Technical View's object detail (CAP-002, SPRINT-17) — read-only,
 * scrolls to and highlights the object's own line range within its source file. */
export function SourceViewer({ assessmentId, objectId }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['object-source', assessmentId, objectId],
    queryFn: () => fetchObjectSource(assessmentId, objectId),
  })

  const handleMount: OnMount = (editor, monaco) => {
    if (!data) return
    const endLine = data.line_end ?? data.line_start
    editor.revealLineInCenter(data.line_start)
    editor.createDecorationsCollection([
      {
        range: new monaco.Range(data.line_start, 1, endLine, 1),
        options: { isWholeLine: true, className: 'source-viewer-object-range' },
      },
    ])
  }

  if (isLoading) {
    return (
      <div className="flex h-[320px] items-center justify-center rounded border border-border-soft bg-surface-elevated text-[11px] text-text-tertiary">
        Carregando código-fonte…
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="flex h-[120px] flex-col items-center justify-center gap-2 rounded border border-border-soft bg-surface-elevated text-[11px] text-text-tertiary">
        <AlertTriangle className="h-4 w-4" strokeWidth={2} />
        Não foi possível carregar o código-fonte deste objeto.
      </div>
    )
  }

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-[11px] font-medium text-text-secondary">
        <span className="flex items-center gap-1.5">
          <FileCode2 className="h-3.5 w-3.5" strokeWidth={2} />
          {data.rel_path}
        </span>
        {data.truncated && (
          <span className="flex items-center gap-1 text-[10px] text-attention">
            <AlertTriangle className="h-3 w-3" strokeWidth={2} />
            Arquivo truncado (exibindo os primeiros 512 KB)
          </span>
        )}
      </div>
      <div className="overflow-hidden rounded border border-border-soft">
        <Editor
          height="320px"
          language={data.language}
          value={data.content}
          onMount={handleMount}
          options={{
            readOnly: true,
            domReadOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            scrollBeyondLastLine: false,
            renderLineHighlight: 'none',
          }}
        />
      </div>
    </div>
  )
}
