'use client'

import { Wrench, Sparkles, Play, AlertCircle, CheckCircle2 } from 'lucide-react'
import { clsx } from 'clsx'
import { useState } from 'react'

interface AutoFixPreview {
  description: string
  confidence: number
  action: string
  estimatedImpact?: string
  requirements?: string[]
}

interface SelfHealingPreviewProps {
  available: boolean
  preview?: AutoFixPreview
  onApplyFix?: () => Promise<void>
  className?: string
}

export function SelfHealingPreview({
  available,
  preview,
  onApplyFix,
  className,
}: SelfHealingPreviewProps) {
  const [isApplying, setIsApplying] = useState(false)
  const [applyStatus, setApplyStatus] = useState<'idle' | 'success' | 'error'>('idle')

  const handleApply = async () => {
    if (!onApplyFix) return

    setIsApplying(true)
    setApplyStatus('idle')

    try {
      await onApplyFix()
      setApplyStatus('success')
    } catch (err) {
      setApplyStatus('error')
    } finally {
      setIsApplying(false)
    }
  }

  if (!available || !preview) {
    return null
  }

  const confidenceColor =
    preview.confidence >= 0.8 ? 'text-emerald-400' :
    preview.confidence >= 0.6 ? 'text-yellow-400' :
    'text-red-400'

  return (
    <div
      className={clsx(
        'p-4 bg-gradient-to-br from-purple-500/10 to-primary-500/10',
        'border border-purple-500/30 rounded-xl',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-purple-500/20 rounded-lg">
            <Sparkles className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <h3 className="font-semibold text-purple-300">Self-Healing Available</h3>
            <p className="text-xs text-slate-400">AI-powered automatic fix</p>
          </div>
        </div>
        <span
          className={clsx(
            'px-2 py-1 text-sm font-medium rounded-full',
            'bg-slate-800/50',
            confidenceColor
          )}
        >
          {Math.round(preview.confidence * 100)}% confidence
        </span>
      </div>

      {/* Description */}
      <div className="mb-4">
        <p className="text-sm text-slate-300 mb-2">{preview.description}</p>
        <div className="p-3 bg-slate-900/50 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            <Wrench className="w-4 h-4 text-slate-400" />
            <span className="text-xs font-medium text-slate-400">Proposed Action</span>
          </div>
          <p className="text-sm text-white">{preview.action}</p>
        </div>
      </div>

      {/* Requirements */}
      {preview.requirements && preview.requirements.length > 0 && (
        <div className="mb-4">
          <p className="text-xs font-medium text-slate-400 mb-2">Requirements</p>
          <ul className="space-y-1">
            {preview.requirements.map((req, i) => (
              <li key={i} className="flex items-center gap-2 text-xs text-slate-300">
                <CheckCircle2 className="w-3 h-3 text-slate-500" />
                {req}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Estimated Impact */}
      {preview.estimatedImpact && (
        <div className="mb-4 p-2 bg-slate-800/50 rounded-lg">
          <p className="text-xs text-slate-400">
            <span className="font-medium">Estimated Impact:</span> {preview.estimatedImpact}
          </p>
        </div>
      )}

      {/* Apply Button */}
      {onApplyFix && (
        <div className="flex items-center gap-3">
          <button
            onClick={handleApply}
            disabled={isApplying}
            className={clsx(
              'flex-1 py-2.5 px-4 rounded-lg font-medium transition-all',
              'flex items-center justify-center gap-2',
              isApplying
                ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                : 'bg-purple-600 hover:bg-purple-500 text-white'
            )}
          >
            {isApplying ? (
              <>
                <div className="w-4 h-4 border-2 border-slate-500 border-t-transparent rounded-full animate-spin" />
                Applying...
              </>
            ) : applyStatus === 'success' ? (
              <>
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Applied Successfully
              </>
            ) : applyStatus === 'error' ? (
              <>
                <AlertCircle className="w-4 h-4 text-red-400" />
                Failed - Retry
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Apply Fix
              </>
            )}
          </button>
        </div>
      )}

      {/* Disclaimer */}
      <p className="mt-3 text-[10px] text-slate-500 text-center">
        Preview only. Full self-healing requires connected agent runtime.
      </p>
    </div>
  )
}
