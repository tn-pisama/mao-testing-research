'use client'

import { useState } from 'react'
import { ChevronDown, Lightbulb } from 'lucide-react'
import { getScoreColor } from '@/components/quality/QualityGradeBadge'
import type { QualityDimensionScore } from '@/lib/api'

export function DimensionBar({ dimension }: { dimension: QualityDimensionScore }) {
  const [expanded, setExpanded] = useState(false)
  const scorePercent = Math.round(dimension.score * 100)
  const barColor = scorePercent >= 80 ? 'bg-green-500' : scorePercent >= 60 ? 'bg-amber-500' : 'bg-red-500'
  const hasDetails = dimension.suggestions.length > 0 ||
                     Object.keys(dimension.evidence || {}).length > 0

  return (
    <div className="mb-3">
      <div
        className={`flex items-center justify-between mb-1 ${hasDetails ? 'cursor-pointer' : ''}`}
        onClick={() => hasDetails && setExpanded(!expanded)}
      >
        <span className="text-sm text-zinc-300 capitalize flex items-center gap-1">
          {dimension.dimension.replace(/_/g, ' ')}
          {hasDetails && (
            <ChevronDown size={12} className={`text-zinc-500 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          )}
        </span>
        <span className={`text-sm font-medium ${getScoreColor(dimension.score)}`}>
          {scorePercent}%
        </span>
      </div>
      <div className="h-2 bg-zinc-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} transition-all duration-500`}
          style={{ width: `${scorePercent}%` }}
        />
      </div>
      {dimension.issues.length > 0 && (
        <div className="mt-1">
          {dimension.issues.slice(0, 2).map((issue, i) => (
            <p key={i} className="text-xs text-zinc-500 truncate">{issue}</p>
          ))}
        </div>
      )}

      {expanded && (
        <div className="mt-2 ml-2 pl-3 border-l-2 border-zinc-700 space-y-2">
          {dimension.suggestions.length > 0 && (
            <div>
              <span className="text-xs text-zinc-500 uppercase">Suggestions</span>
              <ul className="text-xs text-zinc-400 space-y-1 mt-1">
                {dimension.suggestions.map((s, i) => (
                  <li key={i} className="flex items-start gap-1">
                    <Lightbulb size={10} className="text-amber-400 mt-0.5 flex-shrink-0" />
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {Object.keys(dimension.evidence || {}).length > 0 && (
            <div>
              <span className="text-xs text-zinc-500 uppercase">Evidence</span>
              <div className="text-xs text-zinc-400 mt-1 space-y-1">
                {Object.entries(dimension.evidence).map(([key, val]) => (
                  <div key={key}>
                    <span className="text-zinc-500">{key.replace(/_/g, ' ')}:</span>{' '}
                    {String(val)}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
