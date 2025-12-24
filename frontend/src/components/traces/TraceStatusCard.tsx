'use client'

import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { ArrowRight } from 'lucide-react'
import type { Trace } from '@/lib/api'

interface TraceStatusCardProps {
  traces: Trace[]
  isLoading: boolean
}

export function TraceStatusCard({ traces, isLoading }: TraceStatusCardProps) {
  if (isLoading) {
    return (
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-700 rounded w-1/3"></div>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-slate-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Recent Traces</h3>
        <Link href="/traces" className="text-primary-400 hover:text-primary-300 text-sm flex items-center gap-1">
          View all <ArrowRight size={14} />
        </Link>
      </div>
      <div className="space-y-3">
        {traces.map((trace) => (
          <Link
            key={trace.id}
            href={`/traces/${trace.id}`}
            className="block bg-slate-700/50 rounded-lg p-3 hover:bg-slate-700 transition-colors"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-mono text-sm text-white">
                {trace.session_id.slice(0, 12)}...
              </span>
              <span className="text-xs text-slate-400">
                {formatDistanceToNow(new Date(trace.created_at), { addSuffix: true })}
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-400">
              <span>{trace.framework}</span>
              <span>{trace.state_count} states</span>
              <span>{trace.total_tokens.toLocaleString()} tokens</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
