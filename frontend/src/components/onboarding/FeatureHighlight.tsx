'use client'

import { useState, useEffect } from 'react'
import { X, Sparkles } from 'lucide-react'
import { clsx } from 'clsx'

interface FeatureHighlightProps {
  id: string
  title: string
  description: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  isNew?: boolean
  children: React.ReactNode
  onDismiss?: (id: string) => void
}

export function FeatureHighlight({
  id,
  title,
  description,
  position = 'top',
  isNew = true,
  children,
  onDismiss,
}: FeatureHighlightProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [isDismissed, setIsDismissed] = useState(false)

  useEffect(() => {
    const dismissed = localStorage.getItem(`feature-highlight-${id}`)
    if (!dismissed) {
      const timer = setTimeout(() => setIsVisible(true), 500)
      return () => clearTimeout(timer)
    } else {
      setIsDismissed(true)
    }
  }, [id])

  const handleDismiss = () => {
    setIsVisible(false)
    localStorage.setItem(`feature-highlight-${id}`, 'true')
    setIsDismissed(true)
    onDismiss?.(id)
  }

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  }

  const arrowClasses = {
    top: 'bottom-0 left-1/2 -translate-x-1/2 translate-y-full border-t-slate-700',
    bottom: 'top-0 left-1/2 -translate-x-1/2 -translate-y-full border-b-slate-700',
    left: 'right-0 top-1/2 -translate-y-1/2 translate-x-full border-l-slate-700',
    right: 'left-0 top-1/2 -translate-y-1/2 -translate-x-full border-r-slate-700',
  }

  return (
    <div className="relative inline-block">
      {children}
      
      {isVisible && !isDismissed && (
        <div
          className={clsx(
            'absolute z-50 w-64 p-4 rounded-xl bg-slate-800 border border-slate-700 shadow-xl',
            'animate-fade-in-up',
            positionClasses[position]
          )}
        >
          <div
            className={clsx(
              'absolute w-0 h-0 border-8 border-transparent',
              arrowClasses[position]
            )}
          />
          
          <button
            onClick={handleDismiss}
            className="absolute top-2 right-2 p-1 text-slate-400 hover:text-white transition-colors"
          >
            <X size={14} />
          </button>

          <div className="flex items-start gap-3">
            {isNew && (
              <div className="p-1.5 rounded-lg bg-purple-500/20">
                <Sparkles size={14} className="text-purple-400" />
              </div>
            )}
            <div className="flex-1">
              <h4 className="font-semibold text-white text-sm mb-1">{title}</h4>
              <p className="text-xs text-slate-400">{description}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
