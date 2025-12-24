'use client'

import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Position,
  MarkerType,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { AgentInfo } from './AgentCard'
import { AgentNode } from './AgentNode'
import { MessageNode } from './MessageNode'

interface OrchestrationMessage {
  id: string
  from: string
  to: string
  type: 'task' | 'result' | 'error' | 'delegation'
  content: string
  timestamp: string
}

interface AgentOrchestrationViewProps {
  agents: AgentInfo[]
  messages: OrchestrationMessage[]
  activeAgentId?: string
  onAgentClick?: (agentId: string) => void
}

const nodeTypes = {
  agent: AgentNode,
  message: MessageNode,
}

export function AgentOrchestrationView({
  agents,
  messages,
  activeAgentId,
  onAgentClick,
}: AgentOrchestrationViewProps) {
  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const angleStep = (2 * Math.PI) / agents.length
    const radius = 250
    const centerX = 400
    const centerY = 300

    const agentNodes: Node[] = agents.map((agent, index) => {
      const angle = angleStep * index - Math.PI / 2
      const x = centerX + radius * Math.cos(angle)
      const y = centerY + radius * Math.sin(angle)

      return {
        id: agent.id,
        type: 'agent',
        position: { x, y },
        data: {
          agent,
          isActive: agent.id === activeAgentId,
          onClick: () => onAgentClick?.(agent.id),
        },
      }
    })

    const messageEdges: Edge[] = messages.map((msg) => ({
      id: msg.id,
      source: msg.from,
      target: msg.to,
      type: 'smoothstep',
      animated: msg.type === 'task',
      style: {
        stroke:
          msg.type === 'error'
            ? '#ef4444'
            : msg.type === 'result'
            ? '#22c55e'
            : msg.type === 'delegation'
            ? '#a855f7'
            : '#3b82f6',
        strokeWidth: 2,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color:
          msg.type === 'error'
            ? '#ef4444'
            : msg.type === 'result'
            ? '#22c55e'
            : msg.type === 'delegation'
            ? '#a855f7'
            : '#3b82f6',
      },
      label: msg.content.slice(0, 20) + (msg.content.length > 20 ? '...' : ''),
      labelStyle: { fill: '#94a3b8', fontSize: 10 },
      labelBgStyle: { fill: '#1e293b', fillOpacity: 0.8 },
    }))

    return { nodes: agentNodes, edges: messageEdges }
  }, [agents, messages, activeAgentId, onAgentClick])

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  return (
    <div className="h-[600px] bg-slate-900 rounded-xl border border-slate-700 overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.5}
        maxZoom={1.5}
        defaultViewport={{ x: 0, y: 0, zoom: 0.8 }}
      >
        <Background color="#334155" gap={20} size={1} />
        <Controls className="bg-slate-800 border-slate-700 text-white" />
        <MiniMap
          nodeColor={(node) => {
            if (node.data?.agent?.status === 'running') return '#22c55e'
            if (node.data?.agent?.status === 'failed') return '#ef4444'
            return '#64748b'
          }}
          maskColor="rgba(15, 23, 42, 0.8)"
          className="bg-slate-800 border-slate-700"
        />
      </ReactFlow>
    </div>
  )
}
