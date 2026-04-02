'use client'

import { cn } from '@/lib/utils'

interface UsageBarProps {
  label: string
  used: number
  limit: number
}

export function UsageBar({ label, used, limit }: UsageBarProps) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0
  const isHigh = pct >= 80

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-sm text-zinc-400">{label}</span>
        <span className={cn('text-sm font-medium', isHigh ? 'text-amber-400' : 'text-zinc-100')}>
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
      </div>
      <div className="h-2 rounded-full bg-zinc-800/80 overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            isHigh
              ? 'bg-gradient-to-r from-amber-500 to-red-500'
              : 'bg-gradient-to-r from-blue-500 to-blue-400'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
