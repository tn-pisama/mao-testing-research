'use client'

import { Card } from '../ui/Card'

interface TraceListProps {
  traces?: unknown[]
  onSelect?: (id: string) => void
  isLoading?: boolean
  total?: number
  page?: number
  perPage?: number
  onPageChange?: (page: number) => void
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
        <div className="text-center py-8 text-slate-400">
          <p className="text-sm">Loading traces...</p>
        </div>
      </Card>
    )
  }

  const totalPages = total ? Math.ceil(total / perPage) : 1

  return (
    <Card>
      <div className="space-y-4">
        {(!traces || traces.length === 0) ? (
          <div className="text-center py-8 text-slate-400">
            <p className="text-sm">No traces found</p>
          </div>
        ) : (
          <div className="text-center py-8 text-slate-400">
            <p className="text-sm">Trace list coming soon</p>
            <p className="text-xs mt-2">{traces.length} traces on this page</p>
          </div>
        )}

        {onPageChange && totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-700 pt-4">
            <span className="text-sm text-slate-400">
              Page {page} of {totalPages} ({total} total)
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => onPageChange(page - 1)}
                disabled={page <= 1}
                className="px-3 py-1 text-sm bg-slate-700 rounded disabled:opacity-50"
              >
                Previous
              </button>
              <button
                onClick={() => onPageChange(page + 1)}
                disabled={page >= totalPages}
                className="px-3 py-1 text-sm bg-slate-700 rounded disabled:opacity-50"
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
