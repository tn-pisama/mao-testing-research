'use client'

import { forwardRef, ButtonHTMLAttributes, ReactNode } from 'react'
import clsx from 'clsx'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success' | 'warning'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  loading?: boolean
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading, loading, disabled, children, leftIcon, rightIcon, ...props }, ref) => {
    const showLoading = isLoading || loading
    const baseStyles = 'inline-flex items-center justify-center font-mono font-medium rounded transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-black disabled:opacity-50 disabled:cursor-not-allowed'

    const variants = {
      primary: 'bg-transparent border border-primary-500 text-primary-500 hover:bg-primary-500/10 hover:shadow-glow-cyan focus:ring-primary-500',
      secondary: 'bg-transparent border border-white/20 text-white hover:border-white/40 hover:bg-white/5 focus:ring-white/50',
      ghost: 'bg-transparent text-primary-500 hover:bg-primary-500/10 focus:ring-primary-500',
      danger: 'bg-transparent border border-danger-500 text-danger-500 hover:bg-danger-500/10 hover:shadow-glow-red focus:ring-danger-500',
      success: 'bg-transparent border border-success-500 text-success-500 hover:bg-success-500/10 hover:shadow-glow-green focus:ring-success-500',
      warning: 'bg-transparent border border-warning-500 text-warning-500 hover:bg-warning-500/10 focus:ring-warning-500',
    }

    const sizes = {
      sm: 'px-3 py-1.5 text-xs',
      md: 'px-4 py-2 text-sm',
      lg: 'px-6 py-3 text-base',
    }

    return (
      <button
        ref={ref}
        className={clsx(baseStyles, variants[variant], sizes[size], className)}
        disabled={disabled || showLoading}
        {...props}
      >
        {showLoading && (
          <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )}
        {!showLoading && leftIcon && <span className="mr-2">{leftIcon}</span>}
        {children}
        {rightIcon && <span className="ml-2">{rightIcon}</span>}
      </button>
    )
  }
)

Button.displayName = 'Button'
