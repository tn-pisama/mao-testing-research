'use client'

import { Card } from '../ui/Card'

interface AgentComparisonViewProps {
  agents?: unknown[]
  selectedAgents?: string[]
  onToggleAgent?: (agentId: string) => void
}

export function AgentComparisonView({
  agents,
  selectedAgents,
  onToggleAgent,
}: AgentComparisonViewProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Comparison view coming soon</p>
      </div>
    </Card>
  )
}
