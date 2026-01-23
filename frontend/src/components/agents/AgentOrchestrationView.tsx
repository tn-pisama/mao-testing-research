'use client'

import { Card } from '../ui/Card'
import { Network } from 'lucide-react'

interface AgentOrchestrationViewProps {
  agents?: unknown[]
  messages?: unknown[]
  activeAgentId?: string
  onAgentClick?: (agentId: string) => void
}

export function AgentOrchestrationView({
  agents,
  messages,
  activeAgentId,
  onAgentClick,
}: AgentOrchestrationViewProps) {
  return (
    <Card>
      <div className="text-center py-12 text-slate-400">
        <Network size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No orchestration data</p>
        <p className="text-xs mt-1">Agent workflow visualization will appear here</p>
      </div>
    </Card>
  )
}
