'use client'

import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { AlertTriangle, CheckCircle, Clock, ChevronLeft, ChevronRight } from 'lucide-react'
import type { Trace } from '@/lib/api'
import { clsx } from 'clsx'

interface TraceListProps {
  traces: Trace[]
  isLoading: boolean
  total: number
  page: number
  perPage: number
  onPageChange: (page: number) => void
}

export function TraceList({ traces, isLoading, total, page, perPage, onPageChange }: TraceListProps) {
  const totalPages = Math.ceil(total / perPage)

  if (isLoading) {
    return (
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-8 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-700 text-left">
              <th className="px-4 py-3 text-sm font-medium text-slate-400">Session</th>
              <th className="px-4 py-3 text-sm font-medium text-slate-400">Framework</th>
              <th className="px-4 py-3 text-sm font-medium text-slate-400">Status</th>
              <th className="px-4 py-3 text-sm font-medium text-slate-400">States</th>
              <th className="px-4 py-3 text-sm font-medium text-slate-400">Detections</th>
              <th className="px-4 py-3 text-sm font-medium text-slate-400">Tokens</th>
              <th className="px-4 py-3 text-sm font-medium text-slate-400">Created</th>
            </tr>
          </thead>
          <tbody>
            {traces.map((trace) => (
              <tr key={trace.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                <td className="px-4 py-3">
                  <Link href={`/traces/${trace.id}`} className="text-primary-400 hover:text-primary-300 font-mono text-sm">
                    {trace.session_id.slice(0, 12)}...
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span className="text-sm text-slate-300">{trace.framework}</span>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={trace.status} />
                </td>
                <td className="px-4 py-3 text-sm text-slate-300">
                  {trace.state_count}
                </td>
                <td className="px-4 py-3">
                  {trace.detection_count > 0 ? (
                    <span className="inline-flex items-center gap-1 text-danger-500 text-sm">
                      <AlertTriangle size={14} />
                      {trace.detection_count}
                    </span>
                  ) : (
                    <span className="text-slate-500 text-sm">0</span>
                  )}
                </td>
                <td className="px-4 py-3 text-sm text-slate-300">
                  {trace.total_tokens.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-slate-400">
                  {formatDistanceToNow(new Date(trace.created_at), { addSuffix: true })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="px-4 py-3 border-t border-slate-700 flex items-center justify-between">
          <span className="text-sm text-slate-400">
            Showing {(page - 1) * perPage + 1} to {Math.min(page * perPage, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page === 1}
              className="p-2 text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={20} />
            </button>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page === totalPages}
              className="p-2 text-slate-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight size={20} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
        status === 'completed' && 'bg-success-500/20 text-success-500',
        status === 'running' && 'bg-primary-500/20 text-primary-400',
        status === 'failed' && 'bg-danger-500/20 text-danger-500'
      )}
    >
      {status === 'completed' && <CheckCircle size={12} />}
      {status === 'running' && <Clock size={12} />}
      {status === 'failed' && <AlertTriangle size={12} />}
      {status}
    </span>
  )
}
