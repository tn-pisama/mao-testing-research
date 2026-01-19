'use client'

import { Card } from '../ui/Card'

interface TraceViewerProps {
  trace?: unknown
  states?: unknown[]
}

export function TraceViewer({ trace, states }: TraceViewerProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Trace viewer coming soon</p>
        {states && states.length > 0 && (
          <p className="text-xs mt-2">{states.length} states to visualize</p>
        )}
      </div>
    </Card>
  )
}
