'use client'

import { Card } from '../ui/Card'
import { Radio } from 'lucide-react'

interface LiveDetectionFeedProps {
  detections?: unknown[]
  scenario?: string
  isActive?: boolean
}

export function LiveDetectionFeed({ detections, scenario, isActive }: LiveDetectionFeedProps) {
  return (
    <Card>
      <div className="text-center py-12 text-slate-400">
        <Radio size={32} className="mx-auto mb-3 opacity-50" />
        <p className="text-sm">No live detections</p>
        <p className="text-xs mt-1">Detections will stream here in real-time</p>
      </div>
    </Card>
  )
}
