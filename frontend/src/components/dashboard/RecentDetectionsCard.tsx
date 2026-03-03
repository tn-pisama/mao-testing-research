'use client'

import { AlertTriangle, Clock, ChevronRight } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import Link from 'next/link'
import type { Detection } from '@/lib/api'

interface RecentDetectionsCardProps {
  detections: Detection[]
  isLoading?: boolean
}

const severityStyles = {
  critical: 'error',
  high: 'warning',
  medium: 'info',
  low: 'default',
} as const

function getSeverity(details?: { severity?: string }): 'critical' | 'high' | 'medium' | 'low' {
  const severity = details?.severity
  if (severity === 'critical' || severity === 'high' || severity === 'medium' || severity === 'low') {
    return severity
  }
  return 'medium'
}

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

export function RecentDetectionsCard({ detections, isLoading }: RecentDetectionsCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-64 animate-pulse bg-zinc-800 rounded-lg" />
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Recent Detections</CardTitle>
          <Link
            href="/detections"
            className="flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
          >
            View all
            <ChevronRight size={16} />
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {detections.length === 0 ? (
            <div className="text-center py-8 text-white/60">
              <AlertTriangle size={24} className="mx-auto mb-2 opacity-50" />
              <p className="text-sm">No recent detections</p>
            </div>
          ) : (
            detections.slice(0, 5).map((detection) => {
              const severity = getSeverity(detection.details as { severity?: string })
              return (
                <Link
                  key={detection.id}
                  href={`/detections/${detection.id}`}
                  className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-lg border border-zinc-800 hover:bg-zinc-800 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <AlertTriangle
                      size={16}
                      className={
                        severity === 'critical' ? 'text-danger-500' :
                        severity === 'high' ? 'text-accent-500' :
                        severity === 'medium' ? 'text-blue-400' :
                        'text-white/60'
                      }
                    />
                    <div>
                      <p className="text-sm font-medium text-white">
                        {detection.detection_type.replace(/_/g, ' ')}
                      </p>
                      <p className="text-xs text-white/40">
                        Trace: {detection.trace_id.slice(0, 8)}...
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant={severityStyles[severity]} size="sm">
                      {severity}
                    </Badge>
                    <div className="flex items-center gap-1 text-xs text-white/40">
                      <Clock size={12} />
                      {formatTime(detection.created_at)}
                    </div>
                  </div>
                </Link>
              )
            })
          )}
        </div>
      </CardContent>
    </Card>
  )
}
