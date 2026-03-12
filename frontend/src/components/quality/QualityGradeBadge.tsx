'use client'

import { HTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'

export interface QualityGradeBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  grade: string
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

function gradeToTier(grade: string): { label: string; className: string } {
  // Tier names (current backend format)
  if (grade === 'Healthy') return { label: 'Healthy', className: 'bg-green-500/20 text-green-500 border-green-500/50' }
  if (grade === 'Good') return { label: 'Good', className: 'bg-blue-500/20 text-blue-500 border-blue-500/50' }
  if (grade === 'Needs Attention') return { label: 'Needs Attention', className: 'bg-violet-500/20 text-violet-500 border-violet-500/50' }
  if (grade === 'Needs Data') return { label: 'Needs Data', className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/50' }
  if (grade === 'At Risk') return { label: 'At Risk', className: 'bg-orange-500/20 text-orange-400 border-orange-500/50' }
  if (grade === 'Critical') return { label: 'Critical', className: 'bg-red-500/20 text-red-500 border-red-500/50' }
  // Legacy "Degraded" from old DB rows
  if (grade === 'Degraded') return { label: 'Needs Attention', className: 'bg-violet-500/20 text-violet-500 border-violet-500/50' }
  // Legacy letter grades (backward compat for old DB data)
  if (['A+', 'A', 'A-'].includes(grade)) return { label: 'Healthy', className: 'bg-green-500/20 text-green-500 border-green-500/50' }
  if (['B+', 'B'].includes(grade)) return { label: 'Good', className: 'bg-blue-500/20 text-blue-500 border-blue-500/50' }
  if (['B-'].includes(grade)) return { label: 'Needs Attention', className: 'bg-violet-500/20 text-violet-500 border-violet-500/50' }
  if (['C+', 'C', 'C-', 'D'].includes(grade)) return { label: 'At Risk', className: 'bg-orange-500/20 text-orange-400 border-orange-500/50' }
  return { label: 'Critical', className: 'bg-red-500/20 text-red-500 border-red-500/50' }
}

export const QualityGradeBadge = forwardRef<HTMLSpanElement, QualityGradeBadgeProps>(
  ({ className, grade, size = 'md', showLabel: _showLabel = false, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center font-semibold rounded-md border'

    const sizes = {
      sm: 'px-1.5 py-0.5 text-xs',
      md: 'px-2 py-1 text-sm',
      lg: 'px-3 py-1.5 text-base',
    }

    const { label, className: colorClass } = gradeToTier(grade)

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

QualityGradeBadge.displayName = 'QualityGradeBadge'

export function getGradeColor(grade: string): string {
  if (grade === 'Healthy' || ['A+', 'A', 'A-'].includes(grade)) return 'text-green-500'
  if (grade === 'Good' || ['B+', 'B'].includes(grade)) return 'text-blue-500'
  if (grade === 'Needs Attention' || grade === 'Degraded' || ['B-'].includes(grade)) return 'text-violet-500'
  if (grade === 'Needs Data') return 'text-zinc-400'
  if (grade === 'At Risk' || ['C+', 'C', 'C-', 'D'].includes(grade)) return 'text-orange-400'
  return 'text-red-500'
}

export function getScoreColor(score: number): string {
  if (score >= 0.9) return 'text-green-500'
  if (score >= 0.8) return 'text-blue-500'
  if (score >= 0.6) return 'text-violet-500'
  return 'text-red-500'
}
