'use client'

import { Card } from '../ui/Card'
import { HeartPulse } from 'lucide-react'

interface AgentHealthDashboardProps {
  agents?: unknown[]
  isLive?: boolean
}

export function AgentHealthDashboard({ agents, isLive }: AgentHealthDashboardProps) {
  return (
    <Card>
      <div className="text-center py-12 text-slate-400">
        <HeartPulse size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No health data available</p>
        <p className="text-xs mt-1">Agent health metrics will appear here</p>
      </div>
    </Card>
  )
}
