'use client'

import { Card } from '../ui/Card'

interface TraceTimelineProps {
  trace?: unknown
  states?: unknown[]
  isLoading?: boolean
}

export function TraceTimeline({ trace, states, isLoading }: TraceTimelineProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="text-center py-8 text-slate-400">
          <p className="text-sm">Loading timeline...</p>
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Trace timeline coming soon</p>
        {states && states.length > 0 && (
          <p className="text-xs mt-2">{states.length} states</p>
        )}
      </div>
    </Card>
  )
}
