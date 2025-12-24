'use client'

import { useMemo } from 'react'
import dynamic from 'next/dynamic'
import { Node, Edge, MarkerType } from 'reactflow'
import { AgentInfo } from './AgentCard'

const ReactFlowWrapper = dynamic(
  () => import('./ReactFlowWrapper'),
  { 
    ssr: false,
    loading: () => (
      <div className="h-[600px] bg-slate-900 rounded-xl border border-slate-700 flex items-center justify-center">
        <div className="text-slate-400">Loading orchestration view...</div>
      </div>
    )
  }
)

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

export function AgentOrchestrationView({
  agents,
  messages,
  activeAgentId,
  onAgentClick,
}: AgentOrchestrationViewProps) {
  const { nodes, edges } = useMemo(() => {
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

  return <ReactFlowWrapper initialNodes={nodes} initialEdges={edges} />
}
