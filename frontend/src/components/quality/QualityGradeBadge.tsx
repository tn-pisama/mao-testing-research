'use client'

import { HTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

export interface QualityGradeBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  grade: string
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

const gradeColors: Record<string, string> = {
  'A': 'bg-green-500/20 text-green-400 border-green-500/50',
  'B+': 'bg-blue-500/20 text-blue-400 border-blue-500/50',
  'B': 'bg-blue-500/20 text-blue-400 border-blue-500/50',
  'C+': 'bg-amber-500/20 text-amber-400 border-amber-500/50',
  'C': 'bg-amber-500/20 text-amber-400 border-amber-500/50',
  'D': 'bg-red-500/20 text-red-400 border-red-500/50',
  'F': 'bg-red-500/20 text-red-400 border-red-500/50',
}

const gradeLabels: Record<string, string> = {
  'A': 'Excellent',
  'B+': 'Very Good',
  'B': 'Good',
  'C+': 'Above Average',
  'C': 'Average',
  'D': 'Below Average',
  'F': 'Poor',
}

export const QualityGradeBadge = forwardRef<HTMLSpanElement, QualityGradeBadgeProps>(
  ({ className, grade, size = 'md', showLabel = false, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center font-semibold rounded-md border'

    const sizes = {
      sm: 'px-1.5 py-0.5 text-xs',
      md: 'px-2 py-1 text-sm',
      lg: 'px-3 py-1.5 text-base',
    }

    const colorClass = gradeColors[grade] || gradeColors['F']
    const label = gradeLabels[grade] || 'Unknown'

    return (
      <span
        ref={ref}
        className={clsx(baseStyles, colorClass, sizes[size], className)}
        title={label}
        {...props}
      >
        {grade}
        {showLabel && <span className="ml-1.5 font-normal opacity-80">{label}</span>}
      </span>
    )
  }
)

QualityGradeBadge.displayName = 'QualityGradeBadge'

export function getGradeColor(grade: string): string {
  const colors: Record<string, string> = {
    'A': 'text-green-400',
    'B+': 'text-blue-400',
    'B': 'text-blue-400',
    'C+': 'text-amber-400',
    'C': 'text-amber-400',
    'D': 'text-red-400',
    'F': 'text-red-400',
  }
  return colors[grade] || 'text-slate-400'
}

export function getScoreColor(score: number): string {
  if (score >= 0.9) return 'text-green-400'
  if (score >= 0.8) return 'text-blue-400'
  if (score >= 0.6) return 'text-amber-400'
  return 'text-red-400'
}
