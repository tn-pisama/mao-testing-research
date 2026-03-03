'use client'

import { HTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

export interface QualityHealingStatusBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  status: string
  size?: 'sm' | 'md'
}

function statusConfig(status: string): { label: string; className: string } {
  switch (status) {
    case 'pending':
      return { label: 'Pending', className: 'bg-amber-500/20 text-amber-400 border-amber-500/50' }
    case 'analyzing':
      return { label: 'Analyzing', className: 'bg-blue-500/20 text-blue-400 border-blue-500/50' }
    case 'applying':
      return { label: 'Applying', className: 'bg-blue-500/20 text-blue-400 border-blue-500/50' }
    case 'validating':
      return { label: 'Validating', className: 'bg-blue-500/20 text-blue-400 border-blue-500/50' }
    case 'in_progress':
      return { label: 'In Progress', className: 'bg-blue-500/20 text-blue-400 border-blue-500/50' }
    case 'success':
    case 'applied':
      return { label: status === 'applied' ? 'Applied' : 'Success', className: 'bg-green-500/20 text-green-400 border-green-500/50' }
    case 'partial_success':
      return { label: 'Partial', className: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50' }
    case 'failed':
      return { label: 'Failed', className: 'bg-red-500/20 text-red-400 border-red-500/50' }
    case 'rolled_back':
      return { label: 'Rolled Back', className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/50' }
    case 'rejected':
      return { label: 'Rejected', className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/50' }
    case 'staged':
      return { label: 'Staged', className: 'bg-purple-500/20 text-purple-400 border-purple-500/50' }
    default:
      return { label: status, className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/50' }
  }
}

export const QualityHealingStatusBadge = forwardRef<HTMLSpanElement, QualityHealingStatusBadgeProps>(
  ({ className, status, size = 'md', ...props }, ref) => {
    const baseStyles = 'inline-flex items-center font-semibold rounded-md border font-mono'

    const sizes = {
      sm: 'px-1.5 py-0.5 text-xs',
      md: 'px-2 py-1 text-sm',
    }

    const { label, className: colorClass } = statusConfig(status)

    return (
      <span
        ref={ref}
        className={cn(baseStyles, colorClass, sizes[size], className)}
        title={label}
        {...props}
      >
        {label}
      </span>
    )
  }
)

QualityHealingStatusBadge.displayName = 'QualityHealingStatusBadge'
