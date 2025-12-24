'use client'

interface TraceSearchProps {
  statusFilter?: string
  onStatusChange: (status: string | undefined) => void
}

export function TraceSearch({ statusFilter, onStatusChange }: TraceSearchProps) {
  return (
    <div className="flex gap-4">
      <select
        value={statusFilter || ''}
        onChange={(e) => onStatusChange(e.target.value || undefined)}
        className="bg-slate-700 border border-slate-600 text-white text-sm rounded-lg px-3 py-2 focus:ring-primary-500 focus:border-primary-500"
      >
        <option value="">All Statuses</option>
        <option value="running">Running</option>
        <option value="completed">Completed</option>
        <option value="failed">Failed</option>
      </select>
    </div>
  )
}
