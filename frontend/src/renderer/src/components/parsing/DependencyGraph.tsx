import { useMemo } from 'react'
import { Background, Controls, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useQuery } from '@tanstack/react-query'
import { fetchObjectDependencies, type SAPObjectRecord } from '@/lib/api'

interface Props {
  assessmentId: number
  object: SAPObjectRecord
}

const DEP_TYPE_LABEL: Record<string, string> = {
  CALL_FUNCTION: 'CALL FUNCTION',
  INCLUDE: 'INCLUDE',
  INHERITS_FROM: 'INHERITS FROM',
  USES_TABLE: 'USES TABLE',
}

const DEP_TYPE_COLOR: Record<string, string> = {
  CALL_FUNCTION: '#c084fc',
  INCLUDE: '#67e8f9',
  INHERITS_FROM: '#fbbf24',
  USES_TABLE: '#6ee7b7',
}

const ROOT_ID = 'root'
const NODE_STYLE_BASE = {
  borderRadius: 6,
  fontSize: 11,
  fontFamily: 'var(--font-mono)',
  padding: 8,
}

/** Object-level dependency graph for Technical View (CAP-003, SPRINT-17) — replaces the flat
 * dependency list with a React Flow diagram centered on the selected object. Target nodes are
 * plain labels (never a navigable SAPObject) since `SAPObjectDependency.target_name` is free
 * text with no resolved target id (pre-existing gap, see BACKLOG BL-022/BL-016) — this graph
 * does not attempt cross-application coupling resolution, only visualizes what is already known. */
export function DependencyGraph({ assessmentId, object }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['dependencies', assessmentId, object.id],
    queryFn: () => fetchObjectDependencies(assessmentId, object.id),
  })

  const { nodes, edges } = useMemo<{ nodes: Node[]; edges: Edge[] }>(() => {
    const deps = data?.dependencies ?? []
    const rootNode: Node = {
      id: ROOT_ID,
      position: { x: 0, y: Math.max(deps.length - 1, 0) * 30 },
      data: { label: object.object_name },
      style: { ...NODE_STYLE_BASE, background: '#e30074', color: '#fff', border: '1px solid #e30074' },
    }
    const targetNodes: Node[] = deps.map((dep, i) => ({
      id: `dep-${dep.id}`,
      position: { x: 320, y: i * 64 },
      data: { label: dep.target_name },
      style: { ...NODE_STYLE_BASE, background: '#1d2128', color: '#e6e6e6', border: '1px solid #33373f' },
    }))
    const depEdges: Edge[] = deps.map((dep) => ({
      id: `edge-${dep.id}`,
      source: ROOT_ID,
      target: `dep-${dep.id}`,
      label: DEP_TYPE_LABEL[dep.dep_type] ?? dep.dep_type,
      labelStyle: { fill: DEP_TYPE_COLOR[dep.dep_type] ?? '#9ca3af', fontSize: 10 },
      style: { stroke: DEP_TYPE_COLOR[dep.dep_type] ?? '#4b5563' },
    }))
    return { nodes: [rootNode, ...targetNodes], edges: depEdges }
  }, [data, object])

  if (isLoading) return <div className="text-[11px] text-text-tertiary">Loading dependencies…</div>
  if (!data || data.total === 0) return null

  return (
    <div>
      <div className="mb-1.5 text-[11px] font-medium text-text-secondary">Dependencies ({data.total})</div>
      <div className="h-[240px] overflow-hidden rounded border border-border-soft bg-surface-elevated">
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  )
}
