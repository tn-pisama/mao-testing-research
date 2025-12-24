'use client'

import { clsx } from 'clsx'

interface ConfidenceBadgeProps {
  confidence: number
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        confidence >= 90 && 'bg-danger-500/20 text-danger-500',
        confidence >= 70 && confidence < 90 && 'bg-warning-500/20 text-warning-500',
        confidence < 70 && 'bg-slate-600 text-slate-300'
      )}
    >
      {confidence}%
    </span>
  )
}
