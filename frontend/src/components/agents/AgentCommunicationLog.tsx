'use client'

import { Card } from '../ui/Card'

interface AgentCommunicationLogProps {
  agent?: unknown
  agentId?: string
  messages?: unknown[]
  agents?: unknown[]
}

export function AgentCommunicationLog({ agent, agentId, messages, agents }: AgentCommunicationLogProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Communication log coming soon</p>
      </div>
    </Card>
  )
}
