'use client'

import { Activity, CheckCircle, Clock, AlertCircle, ChevronRight } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import Link from 'next/link'
import type { Trace } from '@/lib/api'

interface TraceStatusCardProps {
  traces: Trace[]
  isLoading?: boolean
}

const statusStyles = {
  completed: 'success',
  running: 'info',
  failed: 'error',
} as const

const statusIcons = {
  completed: CheckCircle,
  running: Clock,
  failed: AlertCircle,
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

export function TraceStatusCard({ traces, isLoading }: TraceStatusCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-64 animate-pulse bg-zinc-800 rounded-lg" />
      </Card>
    )
  }

  const statusCounts = traces.reduce(
    (acc, trace) => {
      const status = trace.status as 'completed' | 'running' | 'failed'
      acc[status] = (acc[status] || 0) + 1
      return acc
    },
    { completed: 0, running: 0, failed: 0 } as Record<string, number>
  )

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Trace Status</CardTitle>
          <Link
            href="/traces"
            className="flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300 font-mono"
          >
            View all
            <ChevronRight size={16} />
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {/* Status summary */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="text-center p-3 bg-green-500/20 rounded-lg border border-green-500/30">
            <CheckCircle size={20} className="mx-auto text-green-500 mb-1" />
            <div className="text-xl font-bold text-green-500 font-mono">{statusCounts.completed}</div>
            <div className="text-xs text-white/60">Completed</div>
          </div>
          <div className="text-center p-3 bg-blue-500/10 rounded-lg border border-zinc-700">
            <Clock size={20} className="mx-auto text-blue-400 mb-1" />
            <div className="text-xl font-bold text-blue-400 font-mono">{statusCounts.running}</div>
            <div className="text-xs text-white/60">Running</div>
          </div>
          <div className="text-center p-3 bg-red-500/20 rounded-lg border border-red-500/30">
            <AlertCircle size={20} className="mx-auto text-red-500 mb-1" />
            <div className="text-xl font-bold text-red-500 font-mono">{statusCounts.failed}</div>
            <div className="text-xs text-white/60">Failed</div>
          </div>
        </div>

        {/* Recent traces */}
        <div className="space-y-2">
          {traces.length === 0 ? (
            <div className="text-center py-8 text-zinc-400">
              <Activity size={24} className="mx-auto mb-2 opacity-50" />
              <p className="text-sm font-mono">No recent traces</p>
            </div>
          ) : (
            traces.slice(0, 4).map((trace) => {
              const status = trace.status as 'completed' | 'running' | 'failed'
              const StatusIcon = statusIcons[status] || Clock
              return (
                <Link
                  key={trace.id}
                  href={`/traces/${trace.id}`}
                  className="flex items-center justify-between p-2 bg-zinc-800/50 border border-zinc-800 rounded-lg hover:bg-zinc-800 transition-all"
                >
                  <div className="flex items-center gap-2">
                    <StatusIcon size={14} className={
                      status === 'completed' ? 'text-green-500' :
                      status === 'running' ? 'text-blue-400' :
                      'text-red-500'
                    } />
                    <span className="text-sm text-white font-mono">{trace.id.slice(0, 8)}...</span>
                    <Badge variant="default" size="sm">{trace.framework}</Badge>
                  </div>
                  <span className="text-xs text-white/60 font-mono">{formatTime(trace.created_at)}</span>
                </Link>
              )
            })
          )}
        </div>
      </CardContent>
    </Card>
  )
}
