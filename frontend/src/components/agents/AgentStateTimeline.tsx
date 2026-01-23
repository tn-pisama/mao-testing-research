'use client'

import { Card } from '../ui/Card'
import { Clock } from 'lucide-react'

export function AgentStateTimeline({ agent, events }: { agent?: unknown; events?: unknown[] }) {
  return (
    <Card>
      <div className="text-center py-12 text-slate-400">
        <Clock size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No state events available</p>
        <p className="text-xs mt-1">Events will appear here during execution</p>
      </div>
    </Card>
  )
}
