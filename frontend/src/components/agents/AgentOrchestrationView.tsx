'use client'

import { Card } from '../ui/Card'

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
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Orchestration view coming soon</p>
      </div>
    </Card>
  )
}
