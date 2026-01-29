'use client'

import { HTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
  size?: 'sm' | 'md'
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', size = 'md', children, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center font-medium rounded-full border'

    const variants = {
      default: 'bg-neutral-100 text-neutral-600 border-neutral-200',
      success: 'bg-success-500/10 text-success-600 border-success-500/20',
      warning: 'bg-warning-500/10 text-warning-600 border-warning-500/20',
      error: 'bg-danger-500/10 text-danger-600 border-danger-500/20',
      info: 'bg-primary-500/10 text-primary-600 border-primary-500/20',
    }

    const sizes = {
      sm: 'px-2 py-0.5 text-xs',
      md: 'px-3 py-1 text-sm',
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
