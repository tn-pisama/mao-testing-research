'use client'

import { Lightbulb, Copy, Check, ExternalLink } from 'lucide-react'
import { clsx } from 'clsx'
import { useState } from 'react'

interface SuggestedFix {
  title: string
  description: string
  code?: string
  docLink?: string
  priority?: 'high' | 'medium' | 'low'
}

interface SuggestedFixPanelProps {
  fixes: SuggestedFix[]
  className?: string
}

export function SuggestedFixPanel({ fixes, className }: SuggestedFixPanelProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null)

  const handleCopy = async (code: string, index: number) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopiedIndex(index)
      setTimeout(() => setCopiedIndex(null), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  if (fixes.length === 0) {
    return null
  }

  const priorityStyles = {
    high: 'border-red-500/30 bg-red-500/5',
    medium: 'border-yellow-500/30 bg-yellow-500/5',
    low: 'border-blue-500/30 bg-blue-500/5',
  }

  const priorityBadgeStyles = {
    high: 'bg-red-500/20 text-red-400',
    medium: 'bg-yellow-500/20 text-yellow-400',
    low: 'bg-blue-500/20 text-blue-400',
  }

  return (
    <div className={clsx('space-y-3', className)}>
      <div className="flex items-center gap-2">
        <Lightbulb className="w-5 h-5 text-emerald-400" />
        <h3 className="font-semibold text-white">Suggested Fixes</h3>
        <span className="px-2 py-0.5 text-xs bg-emerald-500/20 text-emerald-400 rounded-full">
          {fixes.length} fix{fixes.length !== 1 ? 'es' : ''}
        </span>
      </div>

      <div className="space-y-3">
        {fixes.map((fix, index) => (
          <div
            key={index}
            className={clsx(
              'p-4 rounded-lg border',
              fix.priority ? priorityStyles[fix.priority] : 'border-slate-700 bg-slate-800/50'
            )}
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <span className="font-medium text-white text-sm">{fix.title}</span>
                {fix.priority && (
                  <span
                    className={clsx(
                      'px-1.5 py-0.5 text-[10px] font-medium rounded-full uppercase',
                      priorityBadgeStyles[fix.priority]
                    )}
                  >
                    {fix.priority}
                  </span>
                )}
              </div>
              {fix.docLink && (
                <a
                  href={fix.docLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary-400 hover:text-primary-300 transition-colors"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              )}
            </div>

            <p className="text-sm text-slate-300 mb-3">{fix.description}</p>

            {fix.code && (
              <div className="relative">
                <pre className="text-xs text-slate-400 bg-slate-900 p-3 rounded-lg overflow-x-auto">
                  {fix.code}
                </pre>
                <button
                  onClick={() => handleCopy(fix.code!, index)}
                  className="absolute top-2 right-2 p-1.5 bg-slate-800 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors"
                >
                  {copiedIndex === index ? (
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// Helper to convert detection suggested_fix to SuggestedFix array
export function detectionToFixes(
  suggestedFix: string | undefined,
  category: string,
  severity: string
): SuggestedFix[] {
  if (!suggestedFix) return []

  return [
    {
      title: `Fix for ${category}`,
      description: suggestedFix,
      priority: severity === 'critical' || severity === 'high' ? 'high' :
                severity === 'medium' ? 'medium' : 'low',
    },
  ]
}
