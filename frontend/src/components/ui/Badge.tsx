'use client'

import { HTMLAttributes, forwardRef } from 'react'
import clsx from 'clsx'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
  size?: 'sm' | 'md'
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', size = 'md', children, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center font-semibold rounded-full'

    const variants = {
      default: 'bg-gradient-primary text-white',
      success: 'bg-success-500/20 text-success-400 border border-success-500/50',
      warning: 'bg-warning-500/20 text-warning-400 border border-warning-500/50',
      error: 'bg-danger-500/20 text-danger-400 border border-danger-500/50',
      info: 'bg-gradient-accent text-white',
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
