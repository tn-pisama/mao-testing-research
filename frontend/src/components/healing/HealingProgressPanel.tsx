'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Skeleton } from '@/components/ui/Skeleton'
import type { HealingProgressResponse, DetectorProgressItem } from '@/lib/api/healing'

const statusColors: Record<string, { bar: string; label: string }> = {
  fixed: { bar: 'bg-green-500', label: 'text-green-400' },
  fixing: { bar: 'bg-blue-500', label: 'text-blue-400' },
  pending: { bar: 'bg-zinc-600', label: 'text-zinc-400' },
  failed: { bar: 'bg-red-500', label: 'text-red-400' },
  rolled_back: { bar: 'bg-amber-500', label: 'text-amber-400' },
}

function ConfidenceBar({ before, after, status }: DetectorProgressItem) {
  const colors = statusColors[status] || statusColors.pending
  const beforePct = before != null ? Math.round(before * 100) : 0
  const afterPct = after != null ? Math.round(after * 100) : beforePct

  return (
    <div className="flex items-center gap-2 h-4">
      {/* Before bar (faded) */}
      <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden relative">
        {before != null && (
          <div className="absolute inset-y-0 left-0 bg-zinc-600 rounded-full opacity-40"
               style={{ width: `${beforePct}%` }} />
        )}
        {after != null && (
          <div className={`absolute inset-y-0 left-0 rounded-full ${colors.bar}`}
               style={{ width: `${afterPct}%` }} />
        )}
      </div>
      {/* Values */}
      <div className="flex items-center gap-1 w-28 text-xs font-mono justify-end">
        {before != null && <span className="text-zinc-500">{beforePct}%</span>}
        {before != null && after != null && <span className="text-zinc-600">&rarr;</span>}
        {after != null ? (
          <span className={colors.label}>{afterPct}%</span>
        ) : (
          <span className="text-zinc-600">-</span>
        )}
      </div>
    </div>
  )
}

export function HealingProgressPanel({ healingId }: { healingId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['healing', healingId, 'progress'],
    queryFn: () => api.getHealingProgress(healingId),
    enabled: !!healingId,
    retry: false,
    refetchInterval: 5000, // Poll every 5s while healing is active
  })

  if (isLoading) return <Skeleton className="h-32 rounded-xl" />
  if (error || !data) return null

  const p = data as HealingProgressResponse
  const detectors = Object.entries(p.detector_progress)

  if (detectors.length === 0) return null

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-sm font-semibold text-zinc-300">Per-Detector Progress</h4>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-green-400">{p.fixed_count} fixed</span>
          {p.failed_count > 0 && <span className="text-red-400">{p.failed_count} failed</span>}
          {p.pending_count > 0 && <span className="text-zinc-400">{p.pending_count} pending</span>}
        </div>
      </div>

      <div className="space-y-3">
        {detectors.map(([detType, progress]) => {
          const colors = statusColors[progress.status] || statusColors.pending
          return (
            <div key={detType}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm text-zinc-300">{detType.replace(/_/g, ' ')}</span>
                <span className={`text-xs font-medium ${colors.label}`}>
                  {progress.status}
                </span>
              </div>
              <ConfidenceBar {...progress} />
            </div>
          )
        })}
      </div>
    </div>
  )
}
