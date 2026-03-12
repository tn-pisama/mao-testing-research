'use client'

import { Card } from '../ui/Card'
import { MessageSquare } from 'lucide-react'

interface AgentCommunicationLogProps {
  agent?: unknown
  agentId?: string
  messages?: unknown[]
  agents?: unknown[]
}

export function AgentCommunicationLog({ agent: _agent, agentId: _agentId, messages: _messages, agents: _agents }: AgentCommunicationLogProps) {
  return (
    <Card>
      <div className="text-center py-12 text-zinc-400">
        <MessageSquare size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No communications recorded</p>
        <p className="text-xs mt-1">Inter-agent messages will appear here</p>
      </div>
    </Card>
  )
}
