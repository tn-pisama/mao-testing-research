'use client'

import { Card } from '../ui/Card'
import { BarChart3 } from 'lucide-react'

interface AgentMetricsPanelProps {
  metrics?: unknown
  agents?: unknown[]
}

export function AgentMetricsPanel({ metrics, agents }: AgentMetricsPanelProps) {
  return (
    <Card>
      <div className="text-center py-12 text-slate-400">
        <BarChart3 size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No metrics available</p>
        <p className="text-xs mt-1">Performance metrics will be displayed here</p>
      </div>
    </Card>
  )
}
