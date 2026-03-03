'use client'

import { useState, useEffect } from 'react'
import { X, Plus, Minus, Edit3, AlertTriangle, Loader2 } from 'lucide-react'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import type { WorkflowDiff, N8nConnection } from '@/lib/api'

interface FixPreviewModalProps {
  isOpen: boolean
  onClose: () => void
  onApply: (connectionId: string, stage: boolean) => Promise<void>
  connections: N8nConnection[]
  fix?: {
    type: string
    description: string
    confidence: string
  }
  diff?: WorkflowDiff
  isApplying?: boolean
}

export function FixPreviewModal({
  isOpen,
  onClose,
  onApply,
  connections,
  fix,
  diff,
  isApplying = false
}: FixPreviewModalProps) {
  const [selectedConnection, setSelectedConnection] = useState<string>('')
  const [stageForTesting, setStageForTesting] = useState(true)

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleApply = async () => {
    if (!selectedConnection) return
    await onApply(selectedConnection, stageForTesting)
  }

  const confidenceColor = fix?.confidence === 'high' ? 'success' :
                          fix?.confidence === 'medium' ? 'warning' : 'default'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="fix-preview-modal-title">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-700">
          <div>
            <h2 id="fix-preview-modal-title" className="text-lg font-semibold text-white">Preview Fix</h2>
            <p className="text-sm text-zinc-400">Review changes before applying to n8n</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
            aria-label="Close dialog"
          >
            <X size={20} className="text-zinc-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4 max-h-[60vh] overflow-y-auto">
          {/* Fix Details */}
          {fix && (
            <div className="bg-zinc-800/50 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-white">Fix Details</h3>
                <Badge variant={confidenceColor} size="sm">
                  {fix.confidence} confidence
                </Badge>
              </div>
              <p className="text-sm text-zinc-300 mb-2">
                <span className="text-zinc-500">Type:</span> {fix.type.replace(/_/g, ' ')}
              </p>
              <p className="text-sm text-zinc-300">{fix.description}</p>
            </div>
          )}

          {/* Diff Preview */}
          {diff && (
            <div className="bg-zinc-800/50 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Workflow Changes</h3>

              {/* Summary */}
              <p className="text-sm text-zinc-400 mb-4">{diff.summary}</p>

              {/* Added Nodes */}
              {diff.added_nodes.length > 0 && (
                <div className="mb-3">
                  <div className="flex items-center gap-2 text-green-400 text-xs mb-2">
                    <Plus size={14} />
                    <span>Added Nodes ({diff.added_nodes.length})</span>
                  </div>
                  <div className="space-y-1">
                    {diff.added_nodes.map((node, idx) => (
                      <div
                        key={idx}
                        className="text-sm text-green-300 bg-green-500/10 px-3 py-1.5 rounded font-mono"
                      >
                        + {node}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Removed Nodes */}
              {diff.removed_nodes.length > 0 && (
                <div className="mb-3">
                  <div className="flex items-center gap-2 text-red-400 text-xs mb-2">
                    <Minus size={14} />
                    <span>Removed Nodes ({diff.removed_nodes.length})</span>
                  </div>
                  <div className="space-y-1">
                    {diff.removed_nodes.map((node, idx) => (
                      <div
                        key={idx}
                        className="text-sm text-red-300 bg-red-500/10 px-3 py-1.5 rounded font-mono"
                      >
                        - {node}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Modified Nodes */}
              {diff.modified_nodes.length > 0 && (
                <div className="mb-3">
                  <div className="flex items-center gap-2 text-amber-400 text-xs mb-2">
                    <Edit3 size={14} />
                    <span>Modified Nodes ({diff.modified_nodes.length})</span>
                  </div>
                  <div className="space-y-1">
                    {diff.modified_nodes.map((node, idx) => (
                      <div
                        key={idx}
                        className="text-sm text-amber-300 bg-amber-500/10 px-3 py-1.5 rounded font-mono"
                      >
                        ~ {node}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Settings Changes */}
              {Object.keys(diff.settings_changes || {}).length > 0 && (
                <div>
                  <div className="flex items-center gap-2 text-blue-400 text-xs mb-2">
                    <Edit3 size={14} />
                    <span>Settings Changes</span>
                  </div>
                  <pre className="text-xs text-blue-300 bg-blue-500/10 p-3 rounded overflow-x-auto">
                    {JSON.stringify(diff.settings_changes, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Connection Selection */}
          <div className="bg-zinc-800/50 rounded-lg p-4">
            <h3 className="text-sm font-medium text-white mb-3">Target n8n Instance</h3>
            {connections.length === 0 ? (
              <div className="text-center py-4 text-zinc-400">
                <AlertTriangle size={24} className="mx-auto mb-2 opacity-50" />
                <p className="text-sm">No n8n connections configured</p>
                <p className="text-xs">Add a connection in Settings first</p>
              </div>
            ) : (
              <select
                value={selectedConnection}
                onChange={(e) => setSelectedConnection(e.target.value)}
                className="w-full bg-zinc-700 border border-zinc-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select a connection...</option>
                {connections.map((conn) => (
                  <option key={conn.id} value={conn.id}>
                    {conn.name} ({conn.instance_url})
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Stage Option */}
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={stageForTesting}
                onChange={(e) => setStageForTesting(e.target.checked)}
                className="mt-1 w-4 h-4 rounded border-zinc-600 bg-zinc-700 text-amber-500 focus:ring-amber-500"
              />
              <div>
                <p className="text-sm font-medium text-amber-400">Stage for Testing</p>
                <p className="text-xs text-amber-300/70 mt-1">
                  Apply the fix but deactivate the workflow. You can test manually,
                  then promote to production or reject to rollback.
                </p>
              </div>
            </label>
          </div>

          {/* Warning */}
          <div className="flex items-start gap-3 text-zinc-400 text-xs">
            <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
            <p>
              {stageForTesting
                ? 'The workflow will be updated but deactivated. Test it manually in n8n before promoting to production.'
                : 'The fix will be applied directly to the active workflow. Use staging for safer deployments.'}
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-zinc-700 bg-zinc-800/50">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant={stageForTesting ? 'warning' : 'primary'}
            onClick={handleApply}
            isLoading={isApplying}
            leftIcon={isApplying ? <Loader2 className="animate-spin" size={16} /> : undefined}
            disabled={!selectedConnection || connections.length === 0}
          >
            {stageForTesting ? 'Apply & Stage' : 'Apply Fix'}
          </Button>
        </div>
      </div>
    </div>
  )
}
