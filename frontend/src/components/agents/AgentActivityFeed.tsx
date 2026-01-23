'use client'

import { Card } from '../ui/Card'
import { Activity } from 'lucide-react'

interface AgentActivityFeedProps {
  events?: unknown[]
  agents?: unknown[]
  maxHeight?: string
  isLive?: boolean
}

export function AgentActivityFeed({ events, agents, maxHeight, isLive }: AgentActivityFeedProps) {
  return (
    <Card>
      <div className="text-center py-12 text-slate-400">
        <Activity size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No activity recorded</p>
        <p className="text-xs mt-1">Agent events will stream here</p>
      </div>
    </Card>
  )
}
