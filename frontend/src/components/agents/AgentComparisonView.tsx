'use client'

import { Card } from '../ui/Card'
import { GitCompare } from 'lucide-react'

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
      <div className="text-center py-12 text-slate-400">
        <GitCompare size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">Select agents to compare</p>
        <p className="text-xs mt-1">Side-by-side agent metrics comparison</p>
      </div>
    </Card>
  )
}
