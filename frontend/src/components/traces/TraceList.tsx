'use client'

import { Clock, AlertTriangle, CheckCircle, Loader2, ChevronRight } from 'lucide-react'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import type { Trace } from '@/lib/api'

interface TraceListProps {
  traces?: Trace[]
  onSelect?: (id: string) => void
  isLoading?: boolean
  total?: number
  page?: number
  perPage?: number
  onPageChange?: (page: number) => void
}

const frameworkStyles: Record<string, string> = {
  n8n: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
  openclaw: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
  dify: 'text-violet-400 bg-violet-500/10 border-violet-500/30',
}

function getFrameworkBadge(framework: string) {
  const style = frameworkStyles[framework] || 'text-zinc-400 bg-zinc-500/10 border-zinc-500/30'
  const label = framework === 'openclaw' ? 'OpenClaw' : framework === 'dify' ? 'Dify' : framework
  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${style}`}>
      {label}
    </span>
  )
}

function getStatusBadge(status: string) {
  switch (status.toLowerCase()) {
    case 'completed':
      return <Badge variant="success"><CheckCircle size={12} className="mr-1" />Completed</Badge>
    case 'running':
    case 'in_progress':
      return <Badge variant="default"><Loader2 size={12} className="mr-1 animate-spin" />Running</Badge>
    case 'failed':
    case 'error':
      return <Badge variant="error"><AlertTriangle size={12} className="mr-1" />Failed</Badge>
    default:
      return <Badge variant="default">{status}</Badge>
  }
}

function formatDuration(startDate: string, endDate?: string) {
  const start = new Date(startDate).getTime()
  const end = endDate ? new Date(endDate).getTime() : Date.now()
  const durationMs = end - start

  if (durationMs < 1000) return `${durationMs}ms`
  if (durationMs < 60000) return `${(durationMs / 1000).toFixed(1)}s`
  return `${(durationMs / 60000).toFixed(1)}m`
}

function formatCost(cents: number) {
  if (cents < 1) return '<$0.01'
  return `$${(cents / 100).toFixed(2)}`
}

export function TraceList({
  traces,
  onSelect,
  isLoading,
  total,
  page = 1,
  perPage = 20,
  onPageChange
}: TraceListProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="text-center py-8 text-zinc-400">
          <Loader2 size={24} className="mx-auto mb-2 animate-spin" />
          <p className="text-sm">Loading traces...</p>
        </div>
      </Card>
    )
  }

  const totalPages = total ? Math.ceil(total / perPage) : 1

  return (
    <Card>
      <div className="space-y-0">
        {(!traces || traces.length === 0) ? (
          <div className="text-center py-8 text-zinc-400">
            <Clock size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">No traces found</p>
            <p className="text-xs mt-1 text-zinc-500">Traces will appear here once your agents start running</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-700">
            {traces.map((trace) => (
              <div
                key={trace.id}
                onClick={() => onSelect?.(trace.id)}
                className={`p-4 ${onSelect ? 'cursor-pointer hover:bg-zinc-700/50' : ''} transition-colors`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-white font-medium truncate">
                        {trace.session_id}
                      </span>
                      {getStatusBadge(trace.status)}
                      {getFrameworkBadge(trace.framework)}
                    </div>
                    <div className="flex items-center gap-4 text-sm text-zinc-400">
                      <span className="flex items-center gap-1">
                        <Clock size={14} />
                        {formatDuration(trace.created_at, trace.completed_at)}
                      </span>
                      <span>{trace.total_tokens.toLocaleString()} tokens</span>
                      <span>{formatCost(trace.total_cost_cents)}</span>
                      <span>{trace.state_count} states</span>
                      {trace.detection_count > 0 && (
                        <span className="text-amber-400">
                          <AlertTriangle size={14} className="inline mr-1" />
                          {trace.detection_count} issues
                        </span>
                      )}
                    </div>
                  </div>
                  {onSelect && (
                    <ChevronRight size={20} className="text-zinc-500 flex-shrink-0" />
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {onPageChange && totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-zinc-700 p-4">
            <span className="text-sm text-zinc-400">
              Page {page} of {totalPages} ({total} total)
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => onPageChange(page - 1)}
                disabled={page <= 1}
                className="px-3 py-1 text-sm bg-zinc-700 hover:bg-zinc-600 rounded disabled:opacity-50 disabled:hover:bg-zinc-700 transition-colors"
              >
                Previous
              </button>
              <button
                onClick={() => onPageChange(page + 1)}
                disabled={page >= totalPages}
                className="px-3 py-1 text-sm bg-zinc-700 hover:bg-zinc-600 rounded disabled:opacity-50 disabled:hover:bg-zinc-700 transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
