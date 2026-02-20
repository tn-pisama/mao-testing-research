'use client'

import { useEffect } from 'react'
import { X, AlertTriangle, RotateCcw, Loader2 } from 'lucide-react'
import { Button } from '../ui/Button'

interface RollbackConfirmModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => Promise<void>
  healingId: string
  workflowId?: string
  fixType?: string
  isRollingBack?: boolean
}

export function RollbackConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  healingId,
  workflowId,
  fixType,
  isRollingBack = false
}: RollbackConfirmModalProps) {
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="rollback-modal-title">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-slate-900 border border-slate-700 rounded-xl shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 rounded-lg">
              <RotateCcw size={20} className="text-amber-400" />
            </div>
            <h2 id="rollback-modal-title" className="text-lg font-semibold text-white">Confirm Rollback</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-800 rounded-lg transition-colors"
            aria-label="Close dialog"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          <div className="flex items-start gap-3 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
            <AlertTriangle size={20} className="text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-amber-300 font-medium">
                This action will restore the previous workflow version
              </p>
              <p className="text-xs text-amber-300/70 mt-1">
                The fix will be undone and the workflow will return to its state
                before the fix was applied.
              </p>
            </div>
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Healing ID</span>
              <span className="text-white font-mono text-xs">{healingId.slice(0, 12)}...</span>
            </div>
            {workflowId && (
              <div className="flex justify-between">
                <span className="text-slate-400">Workflow ID</span>
                <span className="text-white">{workflowId}</span>
              </div>
            )}
            {fixType && (
              <div className="flex justify-between">
                <span className="text-slate-400">Fix Type</span>
                <span className="text-white">{fixType.replace(/_/g, ' ')}</span>
              </div>
            )}
          </div>

          <p className="text-xs text-slate-500">
            This action will push the original workflow back to your n8n instance.
            The workflow will be reactivated with its previous configuration.
          </p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-slate-700 bg-slate-800/50">
          <Button variant="ghost" onClick={onClose} disabled={isRollingBack}>
            Cancel
          </Button>
          <Button
            variant="warning"
            onClick={onConfirm}
            isLoading={isRollingBack}
            leftIcon={isRollingBack ? <Loader2 className="animate-spin" size={16} /> : <RotateCcw size={16} />}
          >
            Confirm Rollback
          </Button>
        </div>
      </div>
    </div>
  )
}
