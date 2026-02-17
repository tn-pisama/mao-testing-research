'use client'

import { Card } from '../ui/Card'
import type { AgentInfo } from './index'

interface AgentMetricsPanelProps {
  metrics?: unknown
  agents?: AgentInfo[]
}

export function AgentMetricsPanel({ agents = [] }: AgentMetricsPanelProps) {
  const totalAgents = agents.length
  const activeAgents = agents.filter(a => a.status === 'running').length
  const totalTokens = agents.reduce((sum, a) => sum + (a.tokensUsed ?? 0), 0)
  const avgLatency = agents.length
    ? Math.round(agents.reduce((sum, a) => sum + (a.latencyMs ?? 0), 0) / agents.length)
    : 0

  const stats = [
    { label: 'Total Agents', value: totalAgents },
    { label: 'Active Now', value: activeAgents },
    { label: 'Tokens Used', value: totalTokens >= 1000 ? `${(totalTokens / 1000).toFixed(1)}k` : totalTokens },
    { label: 'Avg Latency', value: `${avgLatency}ms` },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {stats.map(({ label, value }) => (
        <Card key={label}>
          <div className="p-4 text-center">
            <div className="text-2xl font-bold text-white">{value}</div>
            <div className="text-xs text-slate-400 mt-1">{label}</div>
          </div>
        </Card>
      ))}
    </div>
  )
}
