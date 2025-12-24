'use client'

import { clsx } from 'clsx'

interface SkeletonProps {
  className?: string
  style?: React.CSSProperties
}

export function Skeleton({ className, style }: SkeletonProps) {
  return (
    <div
      className={clsx(
        'animate-pulse rounded-md bg-slate-700/50',
        className
      )}
      style={style}
    />
  )
}

export function CardSkeleton({ className }: SkeletonProps) {
  return (
    <div className={clsx('p-4 rounded-xl border border-slate-700 bg-slate-800/50', className)}>
      <div className="flex items-center gap-3 mb-4">
        <Skeleton className="h-10 w-10 rounded-lg" />
        <div className="flex-1">
          <Skeleton className="h-4 w-24 mb-2" />
          <Skeleton className="h-3 w-16" />
        </div>
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      <Skeleton className="h-12 w-full rounded-lg mb-3" />
      <div className="grid grid-cols-3 gap-2">
        <Skeleton className="h-14 rounded-lg" />
        <Skeleton className="h-14 rounded-lg" />
        <Skeleton className="h-14 rounded-lg" />
      </div>
    </div>
  )
}

export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
  return (
    <tr className="border-b border-slate-700/50">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="p-4">
          <Skeleton className="h-4 w-full" />
        </td>
      ))}
    </tr>
  )
}

export function ChartSkeleton({ className }: SkeletonProps) {
  return (
    <div className={clsx('p-4 rounded-xl border border-slate-700 bg-slate-800/50', className)}>
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-8 w-24 rounded-md" />
      </div>
      <div className="flex items-end justify-between gap-2 h-48">
        {Array.from({ length: 12 }).map((_, i) => (
          <Skeleton
            key={i}
            className="flex-1 rounded-t"
            style={{ height: `${Math.random() * 80 + 20}%` }}
          />
        ))}
      </div>
      <div className="flex justify-between mt-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-8" />
        ))}
      </div>
    </div>
  )
}

export function AgentCardSkeleton() {
  return (
    <div className="p-4 rounded-xl border border-slate-700 bg-slate-800/50 animate-pulse">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-lg" />
          <div>
            <Skeleton className="h-4 w-20 mb-1.5" />
            <Skeleton className="h-3 w-14" />
          </div>
        </div>
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      <Skeleton className="h-10 w-full rounded-lg mb-3" />
      <div className="grid grid-cols-3 gap-2">
        <div className="p-2 rounded-lg bg-slate-900/50">
          <Skeleton className="h-3 w-10 mx-auto mb-1" />
          <Skeleton className="h-4 w-12 mx-auto" />
        </div>
        <div className="p-2 rounded-lg bg-slate-900/50">
          <Skeleton className="h-3 w-10 mx-auto mb-1" />
          <Skeleton className="h-4 w-12 mx-auto" />
        </div>
        <div className="p-2 rounded-lg bg-slate-900/50">
          <Skeleton className="h-3 w-10 mx-auto mb-1" />
          <Skeleton className="h-4 w-12 mx-auto" />
        </div>
      </div>
    </div>
  )
}

export function MetricsGridSkeleton() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="p-4 rounded-xl border border-slate-700 bg-slate-800/50">
          <div className="flex items-start justify-between mb-3">
            <Skeleton className="h-9 w-9 rounded-lg" />
            <Skeleton className="h-4 w-10" />
          </div>
          <Skeleton className="h-8 w-20 mb-1" />
          <Skeleton className="h-4 w-24" />
        </div>
      ))}
    </div>
  )
}

export function ActivityFeedSkeleton({ items = 5 }: { items?: number }) {
  return (
    <div className="divide-y divide-slate-700/50">
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="px-4 py-3">
          <div className="flex items-start gap-3">
            <Skeleton className="h-8 w-8 rounded-lg" />
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-3 w-12" />
              </div>
              <Skeleton className="h-4 w-full" />
            </div>
            <Skeleton className="h-3 w-16" />
          </div>
        </div>
      ))}
    </div>
  )
}
