'use client'

import { Card } from '../ui/Card'

interface LiveDetectionFeedProps {
  detections?: unknown[]
  scenario?: string
  isActive?: boolean
}

export function LiveDetectionFeed({ detections, scenario, isActive }: LiveDetectionFeedProps) {
  return (
    <Card>
      <div className="text-center py-8 text-slate-400">
        <p className="text-sm">Live detection feed coming soon</p>
      </div>
    </Card>
  )
}
