'use client'

import { Card } from '../ui/Card'

interface TraceSearchProps {
  onSearch?: (query: string) => void
  statusFilter?: string
  onStatusChange?: (status: string | undefined) => void
}

export function TraceSearch({ onSearch, statusFilter, onStatusChange }: TraceSearchProps) {
  return (
    <Card padding="compact">
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search traces..."
          aria-label="Search traces"
          onChange={(e) => onSearch?.(e.target.value)}
          className="flex-1 px-4 py-2 bg-black border border-primary-500/30 rounded-lg text-white placeholder-white/40 font-mono focus:outline-none focus:ring-2 focus:ring-primary-500 focus:shadow-glow-cyan"
        />
        {onStatusChange && (
          <select
            value={statusFilter || ''}
            aria-label="Filter by status"
            onChange={(e) => onStatusChange(e.target.value || undefined)}
            className="px-4 py-2 bg-black border border-primary-500/30 rounded-lg text-white font-mono focus:outline-none focus:ring-2 focus:ring-primary-500 focus:shadow-glow-cyan"
          >
            <option value="">All Statuses</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        )}
      </div>
    </Card>
  )
}
