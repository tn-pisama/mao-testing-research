'use client'

import { Card } from '../ui/Card'

interface AgentMonitoringPanelProps {
  agents?: unknown[]
  events?: unknown[]
  isLive?: boolean
}

export function AgentMonitoringPanel({ agents, events, isLive }: AgentMonitoringPanelProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Monitoring panel coming soon</p>
      </div>
    </Card>
  )
}
