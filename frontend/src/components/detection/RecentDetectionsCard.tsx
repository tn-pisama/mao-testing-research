'use client'

import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { AlertTriangle, ArrowRight } from 'lucide-react'
import type { Detection } from '@/lib/api'
import { clsx } from 'clsx'

interface RecentDetectionsCardProps {
  detections: Detection[]
  isLoading: boolean
}

export function RecentDetectionsCard({ detections, isLoading }: RecentDetectionsCardProps) {
  if (isLoading) {
    return (
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-700 rounded w-1/3"></div>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-slate-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Recent Detections</h3>
        <Link
          href="/detections"
          className="text-primary-400 hover:text-primary-300 text-sm flex items-center gap-1"
        >
          View all <ArrowRight size={14} />
        </Link>
      </div>
      <div className="space-y-3">
        {detections.length === 0 ? (
          <p className="text-slate-400 text-sm">No detections yet</p>
        ) : (
          detections.map((detection) => (
            <Link
              key={detection.id}
              href={`/traces/${detection.trace_id}`}
              className="flex items-start gap-3 bg-slate-700/50 rounded-lg p-3 hover:bg-slate-700 transition-colors"
            >
              <div
                className={clsx(
                  'p-1.5 rounded',
                  detection.false_positive
                    ? 'bg-slate-600 text-slate-400'
                    : 'bg-danger-500/20 text-danger-500'
                )}
              >
                <AlertTriangle size={14} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-white capitalize">
                    {detection.detection_type}
                  </span>
                  <span className="text-xs text-slate-400">
                    {formatDistanceToNow(new Date(detection.created_at), { addSuffix: true })}
                  </span>
                </div>
                <div className="text-xs text-slate-400">
                  {detection.confidence}% confidence via {detection.method}
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
