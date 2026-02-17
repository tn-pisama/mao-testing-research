'use client'

import { useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  NodeTypes,
  BackgroundVariant,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { applyDagreLayout } from '@/lib/workflow-layout'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import type { State } from '@/lib/api'

const AGENT_COLORS = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e',
  '#06b6d4', '#f97316', '#6366f1',
]

interface AgentStats {
  agentId: string
  totalTokens: number
  totalLatency: number
  stateCount: number
  color: string
}

function TraceAgentNode({ data }: { data: AgentStats }) {
  return (
    <div
      className="px-4 py-3 rounded-lg border-2 bg-slate-900 min-w-[160px]"
      style={{ borderColor: data.color }}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-500" />
      <div className="text-sm font-medium font-mono text-white truncate" title={data.agentId}>
        {data.agentId}
      </div>
      <div className="flex items-center gap-3 mt-1 text-[11px] font-mono text-slate-400">
        <span>{data.stateCount} steps</span>
        <span>{data.totalTokens.toLocaleString()} tok</span>
      </div>
      <div className="text-[11px] font-mono text-slate-500 mt-0.5">
        {data.totalLatency < 1000 ? `${data.totalLatency}ms` : `${(data.totalLatency / 1000).toFixed(1)}s`}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-slate-500" />
    </div>
  )
}

const nodeTypes: NodeTypes = {
  traceAgent: TraceAgentNode,
}

interface TraceFlowGraphProps {
  states: State[]
  height?: number
}

export function TraceFlowGraph({ states, height = 500 }: TraceFlowGraphProps) {
  const { initialNodes, initialEdges } = useMemo(() => {
    if (!states || states.length === 0) {
      return { initialNodes: [], initialEdges: [] }
    }

    const sorted = [...states].sort((a, b) => a.sequence_num - b.sequence_num)

    // Collect per-agent stats
    const uniqueAgents: string[] = []
    const agentStats = new Map<string, AgentStats>()

    sorted.forEach(state => {
      if (!agentStats.has(state.agent_id)) {
        const colorIdx = uniqueAgents.length
        uniqueAgents.push(state.agent_id)
        agentStats.set(state.agent_id, {
          agentId: state.agent_id,
          totalTokens: 0,
          totalLatency: 0,
          stateCount: 0,
          color: AGENT_COLORS[colorIdx % AGENT_COLORS.length],
        })
      }
      const stats = agentStats.get(state.agent_id)!
      stats.totalTokens += state.token_count
      stats.totalLatency += state.latency_ms
      stats.stateCount += 1
    })

    // Collect transitions
    const transitions = new Map<string, number>()
    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i - 1].agent_id !== sorted[i].agent_id) {
        const key = `${sorted[i - 1].agent_id}->${sorted[i].agent_id}`
        transitions.set(key, (transitions.get(key) || 0) + 1)
      }
    }

    // Build nodes
    const nodes: Node[] = [
      {
        id: '__start',
        type: 'input',
        data: { label: 'START' },
        position: { x: 0, y: 0 },
        style: {
          background: '#1e293b',
          border: '1px solid #475569',
          borderRadius: '50%',
          width: 60,
          height: 60,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#94a3b8',
          fontSize: '10px',
          fontFamily: 'monospace',
        },
      },
    ]

    uniqueAgents.forEach(agentId => {
      nodes.push({
        id: agentId,
        type: 'traceAgent',
        data: agentStats.get(agentId)!,
        position: { x: 0, y: 0 },
      })
    })

    nodes.push({
      id: '__end',
      type: 'output',
      data: { label: 'END' },
      position: { x: 0, y: 0 },
      style: {
        background: '#1e293b',
        border: '1px solid #475569',
        borderRadius: '50%',
        width: 60,
        height: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#94a3b8',
        fontSize: '10px',
        fontFamily: 'monospace',
      },
    })

    // Build edges
    const edges: Edge[] = []

    // Start -> first agent
    if (sorted.length > 0) {
      edges.push({
        id: `__start-${sorted[0].agent_id}`,
        source: '__start',
        target: sorted[0].agent_id,
        type: 'smoothstep',
        style: { stroke: '#475569', strokeWidth: 1.5 },
      })
    }

    // Agent-to-agent transitions
    transitions.forEach((count, key) => {
      const [from, to] = key.split('->')
      const fromColor = agentStats.get(from)?.color || '#64748b'
      edges.push({
        id: key,
        source: from,
        target: to,
        type: 'smoothstep',
        animated: count >= 3,
        style: { stroke: fromColor, strokeWidth: Math.min(1.5 + count * 0.5, 4) },
        label: count > 1 ? `${count}x` : undefined,
        labelStyle: { fill: '#94a3b8', fontSize: 11, fontFamily: 'monospace' },
        labelBgStyle: { fill: '#0f172a', fillOpacity: 0.8 },
      })
    })

    // Last agent -> end
    if (sorted.length > 0) {
      const lastAgent = sorted[sorted.length - 1].agent_id
      edges.push({
        id: `${lastAgent}-__end`,
        source: lastAgent,
        target: '__end',
        type: 'smoothstep',
        style: { stroke: '#475569', strokeWidth: 1.5 },
      })
    }

    // Apply dagre layout
    const layouted = applyDagreLayout(nodes, edges, {
      direction: 'TB',
      nodeWidth: 180,
      nodeHeight: 80,
      rankSeparation: 80,
      nodeSeparation: 60,
    })

    return { initialNodes: layouted.nodes, initialEdges: layouted.edges }
  }, [states])

  const [nodes, , onNodesChange] = useNodesState(initialNodes)
  const [edges, , onEdgesChange] = useEdgesState(initialEdges)

  if (!states || states.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-white/60 font-mono">
          <p className="text-sm">No state data for flow graph</p>
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent Flow Graph</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div
          className="bg-slate-900 rounded-b-lg overflow-hidden"
          style={{ height }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            minZoom={0.3}
            maxZoom={2}
            defaultEdgeOptions={{
              type: 'smoothstep',
              style: { stroke: '#64748b', strokeWidth: 1.5 },
            }}
            proOptions={{ hideAttribution: true }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="#334155"
            />
            <Controls className="bg-slate-800 border border-slate-700 rounded-lg" />
            <MiniMap
              className="bg-slate-800 border border-slate-700 rounded"
              nodeColor={(node) => {
                if (node.type === 'input' || node.type === 'output') return '#475569'
                return (node.data as AgentStats)?.color || '#64748b'
              }}
              maskColor="rgba(15, 23, 42, 0.8)"
            />
          </ReactFlow>
        </div>
      </CardContent>
    </Card>
  )
}
