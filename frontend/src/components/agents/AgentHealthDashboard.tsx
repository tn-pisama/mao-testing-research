'use client'

import { Card } from '../ui/Card'

interface AgentHealthDashboardProps {
  agents?: unknown[]
  isLive?: boolean
}

export function AgentHealthDashboard({ agents, isLive }: AgentHealthDashboardProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Health dashboard coming soon</p>
      </div>
    </Card>
  )
}
