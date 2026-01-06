'use client'

import { useState } from 'react'
import { AlertTriangle, RefreshCcw, CheckCircle, XCircle, Wrench, Loader2, ChevronDown, ChevronUp, Lightbulb, TrendingDown } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import type { Detection, FixSuggestion } from '@/lib/api'
import { clsx } from 'clsx'
import { FixPreviewModal } from './FixPreviewModal'

interface FailureCardProps {
  detection: Detection
  onValidate?: (id: string, falsePositive: boolean) => void
  onGetFixes?: (detectionId: string) => Promise<FixSuggestion[]>
  onApplyFix?: (detectionId: string, fixId: string) => Promise<void>
}

export function FailureCard({ detection, onValidate, onGetFixes, onApplyFix }: FailureCardProps) {
  const [fixes, setFixes] = useState<FixSuggestion[]>([])
  const [loadingFixes, setLoadingFixes] = useState(false)
  const [selectedFix, setSelectedFix] = useState<FixSuggestion | null>(null)
  const [applyingFix, setApplyingFix] = useState(false)
  const [fixApplied, setFixApplied] = useState(false)
  const [showDetails, setShowDetails] = useState(false)

  const icons = {
    loop: RefreshCcw,
    corruption: AlertTriangle,
    persona: AlertTriangle,
    coordination: AlertTriangle,
  }
  const Icon = icons[detection.detection_type as keyof typeof icons] || AlertTriangle

  const handleGetFixes = async () => {
    if (!onGetFixes) return
    setLoadingFixes(true)
    try {
      const suggestions = await onGetFixes(detection.id)
      setFixes(suggestions)
      if (suggestions.length > 0) {
        setSelectedFix(suggestions[0])
      }
    } catch (error) {
      console.error('Failed to get fixes:', error)
    } finally {
      setLoadingFixes(false)
    }
  }

  const handleApplyFix = async () => {
    if (!onApplyFix || !selectedFix) return
    setApplyingFix(true)
    try {
      await onApplyFix(detection.id, selectedFix.id)
      setFixApplied(true)
      setSelectedFix(null)
    } catch (error) {
      console.error('Failed to apply fix:', error)
    } finally {
      setApplyingFix(false)
    }
  }

  return (
    <div
      className={clsx(
        'bg-slate-800 rounded-lg border p-4',
        detection.false_positive === true
          ? 'border-slate-600'
          : detection.validated
          ? 'border-success-500/50'
          : 'border-danger-500/50'
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={clsx(
            'p-2 rounded-lg',
            detection.false_positive === true
              ? 'bg-slate-700 text-slate-400'
              : 'bg-danger-500/20 text-danger-500'
          )}
        >
          <Icon size={20} />
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <h4 className="font-medium text-white capitalize">
              {detection.detection_type} Detected
            </h4>
            <span className="text-xs text-slate-400">
              {formatDistanceToNow(new Date(detection.created_at), { addSuffix: true })}
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm text-slate-400 mb-3">
            <span>Confidence: {detection.confidence}%</span>
            <span>Method: {detection.method}</span>
          </div>

          {/* Plain-English Explanation */}
          {detection.explanation && (
            <div className="mb-3 space-y-2">
              <p className="text-sm text-slate-200">{detection.explanation}</p>

              {detection.business_impact && (
                <div className="flex items-start gap-2 text-sm">
                  <TrendingDown size={14} className="text-warning-500 mt-0.5 flex-shrink-0" />
                  <span className="text-slate-400">
                    <span className="text-warning-500 font-medium">Impact:</span> {detection.business_impact}
                  </span>
                </div>
              )}

              {detection.suggested_action && (
                <div className="flex items-start gap-2 text-sm">
                  <Lightbulb size={14} className="text-primary-500 mt-0.5 flex-shrink-0" />
                  <span className="text-slate-400">
                    <span className="text-primary-500 font-medium">Suggestion:</span> {detection.suggested_action}
                  </span>
                </div>
              )}
            </div>
          )}

          {/* Collapsible raw details */}
          {detection.details && Object.keys(detection.details).length > 0 && (
            <div className="mb-2">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showDetails ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {showDetails ? 'Hide details' : 'Show technical details'}
              </button>
              {showDetails && (
                <pre className="mt-2 bg-slate-900 rounded p-2 text-xs text-slate-300 overflow-x-auto">
                  {JSON.stringify(detection.details, null, 2)}
                </pre>
              )}
            </div>
          )}
          <div className="flex gap-2 mt-3 flex-wrap">
            {/* Apply Fix button - always show when fixes are available */}
            {onGetFixes && !fixApplied && (
              <button
                onClick={handleGetFixes}
                disabled={loadingFixes}
                className="flex items-center gap-1 px-3 py-1.5 bg-primary-500/20 text-primary-500 rounded-lg text-sm hover:bg-primary-500/30 transition-colors disabled:opacity-50"
              >
                {loadingFixes ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Wrench size={14} />
                )}
                {loadingFixes ? 'Getting Fixes...' : 'Apply Fix'}
              </button>
            )}

            {/* Fix applied indicator */}
            {fixApplied && (
              <span className="flex items-center gap-1 px-3 py-1.5 bg-success-500/20 text-success-500 rounded-lg text-sm">
                <CheckCircle size={14} />
                Fix Applied
              </span>
            )}

            {/* Validation buttons */}
            {!detection.validated && onValidate && (
              <>
                <button
                  onClick={() => onValidate(detection.id, false)}
                  className="flex items-center gap-1 px-3 py-1.5 bg-success-500/20 text-success-500 rounded-lg text-sm hover:bg-success-500/30 transition-colors"
                >
                  <CheckCircle size={14} />
                  Confirm
                </button>
                <button
                  onClick={() => onValidate(detection.id, true)}
                  className="flex items-center gap-1 px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600 transition-colors"
                >
                  <XCircle size={14} />
                  False Positive
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Fix Preview Modal */}
      {selectedFix && (
        <FixPreviewModal
          fix={selectedFix}
          allFixes={fixes}
          onSelectFix={setSelectedFix}
          onApply={handleApplyFix}
          onClose={() => setSelectedFix(null)}
          applying={applyingFix}
        />
      )}
    </div>
  )
}
