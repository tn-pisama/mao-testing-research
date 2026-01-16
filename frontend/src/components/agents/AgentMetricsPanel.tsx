'use client'

import { Card } from '../ui/Card'

interface AgentMetricsPanelProps {
  metrics?: unknown
  agents?: unknown[]
}

export function AgentMetricsPanel({ metrics, agents }: AgentMetricsPanelProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Metrics panel coming soon</p>
      </div>
    </Card>
  )
}
