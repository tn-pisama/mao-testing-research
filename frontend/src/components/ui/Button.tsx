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
    const baseStyles = 'inline-flex items-center justify-center font-medium rounded-2xl transition-all duration-300 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed glass'

    const variants = {
      primary: 'hover:bg-white/20 hover:shadow-[0_8px_32px_rgba(102,126,234,0.3)] text-white',
      secondary: 'bg-white/5 hover:bg-white/10 text-white/80 hover:text-white',
      ghost: 'bg-transparent hover:bg-white/10 text-white border-0',
      danger: 'hover:bg-danger-500/20 hover:shadow-[0_8px_32px_rgba(239,68,68,0.3)] text-white',
      success: 'hover:bg-success-500/20 hover:shadow-[0_8px_32px_rgba(16,185,129,0.3)] text-white',
      warning: 'hover:bg-warning-500/20 hover:shadow-[0_8px_32px_rgba(245,158,11,0.3)] text-white',
    }

    const sizes = {
      sm: 'px-4 py-2 text-sm',
      md: 'px-6 py-3 text-base',
      lg: 'px-8 py-4 text-lg',
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
