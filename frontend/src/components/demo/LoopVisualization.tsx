'use client'

import { Card } from '../ui/Card'

interface LoopVisualizationProps {
  data?: unknown
  agents?: unknown[]
}

export function LoopVisualization({ data, agents }: LoopVisualizationProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Loop visualization coming soon</p>
      </div>
    </Card>
  )
}
