'use client'

import { Card } from '../ui/Card'
import { Activity } from 'lucide-react'

export function AgentPerformanceChart({ agent: _agent, data: _data }: { agent?: unknown; data?: unknown }) {
  return (
    <Card>
      <div className="text-center py-12 text-zinc-400">
        <Activity size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No performance data available</p>
        <p className="text-xs mt-1">Run this agent to collect metrics</p>
      </div>
    </Card>
  )
}
