'use client'

import { X, Loader2, AlertTriangle, CheckCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import type { FixSuggestion } from '@/lib/api'
import { clsx } from 'clsx'

interface FixPreviewModalProps {
  fix: FixSuggestion
  allFixes: FixSuggestion[]
  onSelectFix: (fix: FixSuggestion) => void
  onApply: () => void
  onClose: () => void
  applying: boolean
}

export function FixPreviewModal({
  fix,
  allFixes,
  onSelectFix,
  onApply,
  onClose,
  applying,
}: FixPreviewModalProps) {
  const currentIndex = allFixes.findIndex((f) => f.id === fix.id)
  const hasPrev = currentIndex > 0
  const hasNext = currentIndex < allFixes.length - 1

  const handlePrev = () => {
    if (hasPrev) {
      onSelectFix(allFixes[currentIndex - 1])
    }
  }

  const handleNext = () => {
    if (hasNext) {
      onSelectFix(allFixes[currentIndex + 1])
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-lg border border-slate-700 max-w-3xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold text-white">{fix.title}</h3>
            <span
              className={clsx(
                'px-2 py-0.5 rounded text-xs font-medium',
                fix.confidence === 'high'
                  ? 'bg-success-500/20 text-success-500'
                  : fix.confidence === 'medium'
                  ? 'bg-warning-500/20 text-warning-500'
                  : 'bg-slate-700 text-slate-300'
              )}
            >
              {fix.confidence} confidence
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Description and Rationale */}
          <div className="space-y-3">
            <p className="text-slate-300">{fix.description}</p>
            <div className="bg-slate-900 rounded p-3">
              <h4 className="text-sm font-medium text-slate-400 mb-1">Rationale</h4>
              <p className="text-sm text-slate-300">{fix.rationale}</p>
            </div>
          </div>

          {/* Warnings */}
          {fix.breaking_changes && (
            <div className="flex items-start gap-2 p-3 bg-danger-500/10 border border-danger-500/30 rounded-lg">
              <AlertTriangle size={16} className="text-danger-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-danger-500">Breaking Changes</p>
                <p className="text-xs text-danger-400">
                  This fix may introduce breaking changes. Review carefully before applying.
                </p>
              </div>
            </div>
          )}

          {fix.requires_testing && (
            <div className="flex items-start gap-2 p-3 bg-warning-500/10 border border-warning-500/30 rounded-lg">
              <AlertTriangle size={16} className="text-warning-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-warning-500">Testing Required</p>
                <p className="text-xs text-warning-400">
                  This fix requires testing after application. Run your test suite to verify.
                </p>
              </div>
            </div>
          )}

          {/* Code Changes */}
          {fix.code_changes && fix.code_changes.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-white">Code Changes</h4>
              {fix.code_changes.map((change, idx) => (
                <div key={idx} className="bg-slate-900 rounded-lg overflow-hidden">
                  <div className="px-3 py-2 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between">
                    <span className="text-sm text-slate-300 font-mono">{change.file_path}</span>
                    <span className="text-xs text-slate-500">{change.language}</span>
                  </div>
                  <div className="p-3">
                    {change.description && (
                      <p className="text-xs text-slate-400 mb-2">{change.description}</p>
                    )}
                    <pre className="text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap font-mono">
                      {change.diff || change.suggested_code}
                    </pre>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Impact and Tags */}
          <div className="flex flex-wrap gap-2">
            {fix.estimated_impact && (
              <span className="px-2 py-1 bg-slate-700 rounded text-xs text-slate-300">
                Impact: {fix.estimated_impact}
              </span>
            )}
            {fix.tags?.map((tag) => (
              <span key={tag} className="px-2 py-1 bg-slate-700 rounded text-xs text-slate-400">
                {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-slate-700">
          {/* Navigation */}
          <div className="flex items-center gap-2">
            {allFixes.length > 1 && (
              <>
                <button
                  onClick={handlePrev}
                  disabled={!hasPrev}
                  className="p-1.5 rounded bg-slate-700 text-slate-300 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft size={16} />
                </button>
                <span className="text-sm text-slate-400">
                  Fix {currentIndex + 1} of {allFixes.length}
                </span>
                <button
                  onClick={handleNext}
                  disabled={!hasNext}
                  className="p-1.5 rounded bg-slate-700 text-slate-300 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight size={16} />
                </button>
              </>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              disabled={applying}
              className="px-4 py-2 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600 transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={onApply}
              disabled={applying}
              className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg text-sm hover:bg-primary-600 transition-colors disabled:opacity-50"
            >
              {applying ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Applying...
                </>
              ) : (
                <>
                  <CheckCircle size={14} />
                  Apply Fix
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
