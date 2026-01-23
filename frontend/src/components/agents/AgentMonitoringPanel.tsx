'use client'

import { Card } from '../ui/Card'
import { Monitor } from 'lucide-react'

interface AgentMonitoringPanelProps {
  agents?: unknown[]
  events?: unknown[]
  isLive?: boolean
}

export function AgentMonitoringPanel({ agents, events, isLive }: AgentMonitoringPanelProps) {
  return (
    <Card>
      <div className="text-center py-12 text-slate-400">
        <Monitor size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No monitoring data</p>
        <p className="text-xs mt-1">Real-time agent status will appear here</p>
      </div>
    </Card>
  )
}
