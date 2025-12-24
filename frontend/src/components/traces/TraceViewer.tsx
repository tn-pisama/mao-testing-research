'use client'

import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { State } from '@/lib/api'

interface TraceViewerProps {
  states: State[]
}

export function TraceViewer({ states }: TraceViewerProps) {
  const { nodes, edges } = useMemo(() => {
    const nodeMap = new Map<string, number>()
    const resultNodes: Node[] = []
    const resultEdges: Edge[] = []

    states.forEach((state, index) => {
      const agentKey = state.agent_id
      const yOffset = nodeMap.get(agentKey) || 0
      nodeMap.set(agentKey, yOffset + 1)

      resultNodes.push({
        id: state.id,
        position: { x: index * 200, y: yOffset * 100 },
        data: {
          label: (
            <div className="text-xs">
              <div className="font-semibold">{state.agent_id}</div>
              <div className="text-slate-400">#{state.sequence_num}</div>
            </div>
          ),
        },
        style: {
          background: '#1e293b',
          color: 'white',
          border: '1px solid #475569',
          borderRadius: '8px',
          padding: '8px',
        },
      })

      if (index > 0) {
        resultEdges.push({
          id: `${states[index - 1].id}-${state.id}`,
          source: states[index - 1].id,
          target: state.id,
          animated: true,
          style: { stroke: '#0ea5e9' },
        })
      }
    })

    return { nodes: resultNodes, edges: resultEdges }
  }, [states])

  const [flowNodes, setNodes, onNodesChange] = useNodesState(nodes)
  const [flowEdges, setEdges, onEdgesChange] = useEdgesState(edges)

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 h-96">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        className="bg-slate-900"
      >
        <Background color="#475569" gap={16} />
        <Controls className="bg-slate-700 border-slate-600" />
        <MiniMap
          nodeColor="#0ea5e9"
          maskColor="rgba(0, 0, 0, 0.8)"
          className="bg-slate-800 border-slate-700"
        />
      </ReactFlow>
    </div>
  )
}
