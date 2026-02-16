'use client'

import { HTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

export interface QualityGradeBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  grade: string
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

const gradeColors: Record<string, string> = {
  'A': 'bg-success-500/20 text-success-500 border-success-500/50',
  'B+': 'bg-primary-500/20 text-primary-500 border-primary-500/50 shadow-glow-cyan',
  'B': 'bg-primary-500/20 text-primary-500 border-primary-500/50 shadow-glow-cyan',
  'C+': 'bg-accent-500/20 text-accent-500 border-accent-500/50',
  'C': 'bg-accent-500/20 text-accent-500 border-accent-500/50',
  'D': 'bg-danger-500/20 text-danger-500 border-danger-500/50',
  'F': 'bg-danger-500/20 text-danger-500 border-danger-500/50',
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
    const baseStyles = 'inline-flex items-center font-semibold rounded-md border font-mono'

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
    'A': 'text-success-500',
    'B+': 'text-primary-500',
    'B': 'text-primary-500',
    'C+': 'text-accent-500',
    'C': 'text-accent-500',
    'D': 'text-danger-500',
    'F': 'text-danger-500',
  }
  return colors[grade] || 'text-white/60'
}

export function getScoreColor(score: number): string {
  if (score >= 0.9) return 'text-success-500'
  if (score >= 0.8) return 'text-primary-500'
  if (score >= 0.6) return 'text-accent-500'
  return 'text-danger-500'
}
