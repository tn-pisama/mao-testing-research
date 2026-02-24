'use client'

import { HTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'danger' | 'info'
  size?: 'sm' | 'md'
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', size = 'md', children, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center font-mono font-medium rounded border'

    const variants = {
      default: 'border-white/30 text-white bg-white/10',
      success: 'border-success-500 text-success-500 bg-success-500/10',
      warning: 'border-warning-500 text-warning-500 bg-warning-500/10',
      error: 'border-danger-500 text-danger-500 bg-danger-500/10',
      danger: 'border-danger-500 text-danger-500 bg-danger-500/10',
      info: 'border-primary-500 text-primary-500 bg-primary-500/10',
    }

    const sizes = {
      sm: 'px-2 py-0.5 text-xs',
      md: 'px-2.5 py-0.5 text-xs',
    }

    return (
      <span
        ref={ref}
        className={clsx(baseStyles, variants[variant], sizes[size], className)}
        {...props}
      >
        {children}
      </span>
    )
  }
)

Badge.displayName = 'Badge'


const tierConfig: Record<string, { variant: BadgeProps['variant']; label: string }> = {
  HIGH: { variant: 'success', label: 'HIGH' },
  LIKELY: { variant: 'info', label: 'LIKELY' },
  POSSIBLE: { variant: 'warning', label: 'POSSIBLE' },
  LOW: { variant: 'error', label: 'LOW' },
}

export interface ConfidenceTierBadgeProps {
  tier?: string | null
  className?: string
}

export function ConfidenceTierBadge({ tier, className }: ConfidenceTierBadgeProps) {
  if (!tier) return null
  const config = tierConfig[tier.toUpperCase()] ?? { variant: 'default' as const, label: tier }
  return (
    <Badge variant={config.variant} size="sm" className={className}>
      {config.label}
    </Badge>
  )
}
