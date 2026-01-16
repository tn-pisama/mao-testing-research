'use client'

import { Card } from '../ui/Card'

interface AgentActivityFeedProps {
  events?: unknown[]
  agents?: unknown[]
  maxHeight?: string
  isLive?: boolean
}

export function AgentActivityFeed({ events, agents, maxHeight, isLive }: AgentActivityFeedProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Activity feed coming soon</p>
      </div>
    </Card>
  )
}
