'use client'

import { Card } from '../ui/Card'

interface TraceSearchProps {
  onSearch?: (query: string) => void
  statusFilter?: string
  onStatusChange?: (status: string | undefined) => void
  frameworkFilter?: string
  onFrameworkChange?: (framework: string | undefined) => void
}

export function TraceSearch({
  onSearch,
  statusFilter,
  onStatusChange,
  frameworkFilter,
  onFrameworkChange,
}: TraceSearchProps) {
  return (
    <Card padding="xs">
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search runs..."
          aria-label="Search runs"
          onChange={(e) => onSearch?.(e.target.value)}
          className="flex-1 px-4 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-white placeholder-white/40 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {onFrameworkChange && (
          <select
            value={frameworkFilter || ''}
            aria-label="Filter by framework"
            onChange={(e) => onFrameworkChange(e.target.value || undefined)}
            className="px-4 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-white font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Providers</option>
            <option value="n8n">n8n</option>
            <option value="openclaw">OpenClaw</option>
            <option value="dify">Dify</option>
          </select>
        )}
        {onStatusChange && (
          <select
            value={statusFilter || ''}
            aria-label="Filter by status"
            onChange={(e) => onStatusChange(e.target.value || undefined)}
            className="px-4 py-2 bg-zinc-950 border border-zinc-800 rounded-lg text-white font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
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
