'use client'

import { Target, ChevronDown, ChevronUp } from 'lucide-react'
import { clsx } from 'clsx'
import { useState } from 'react'

interface RootCauseCardProps {
  explanation: string
  confidence?: number
  category?: string
  className?: string
}

export function RootCauseCard({
  explanation,
  confidence,
  category,
  className,
}: RootCauseCardProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const truncateLength = 300

  const shouldTruncate = explanation.length > truncateLength
  const displayText = isExpanded ? explanation : explanation.slice(0, truncateLength) + '...'

  return (
    <div className={clsx('bg-slate-800/50 rounded-xl border border-slate-700', className)}>
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-primary-400" />
            <h3 className="font-semibold text-white">Root Cause Analysis</h3>
          </div>
          <div className="flex items-center gap-2">
            {category && (
              <span className="px-2 py-0.5 text-xs bg-slate-700 text-slate-300 rounded-full">
                {category}
              </span>
            )}
            {confidence !== undefined && (
              <span className="px-2 py-0.5 text-xs bg-primary-500/20 text-primary-400 rounded-full">
                {Math.round(confidence * 100)}% confidence
              </span>
            )}
          </div>
        </div>

        <div className="text-slate-300 text-sm whitespace-pre-line">
          {displayText}
        </div>

        {shouldTruncate && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="mt-2 flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300 transition-colors"
          >
            {isExpanded ? (
              <>
                <ChevronUp className="w-3 h-3" />
                Show less
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3" />
                Show more
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}
