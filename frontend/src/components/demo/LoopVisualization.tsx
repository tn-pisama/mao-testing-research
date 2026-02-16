'use client'

import { Card } from '../ui/Card'
import { RefreshCw } from 'lucide-react'

interface LoopVisualizationProps {
  data?: unknown
  agents?: unknown[]
}

export function LoopVisualization({ data, agents }: LoopVisualizationProps) {
  return (
    <Card>
      <div className="text-center py-12 text-white/60 font-mono">
        <RefreshCw size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No loops detected</p>
        <p className="text-xs mt-1 text-white/40">Loop patterns will be visualized here</p>
      </div>
    </Card>
  )
}
