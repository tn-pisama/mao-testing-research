'use client'

import { useState } from 'react'
import { AlertTriangle, Play, X, Clock, ExternalLink, Loader2 } from 'lucide-react'
import { Button } from '../ui/Button'
import type { HealingRecord } from '@/lib/api'

interface StagedFixBannerProps {
  healings: HealingRecord[]
  onPromote: (healingId: string) => Promise<void>
  onReject: (healingId: string) => Promise<void>
}

function formatTime(isoString: string | null): string {
  if (!isoString) return 'N/A'
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins} minutes ago`
  if (diffHours < 24) return `${diffHours} hours ago`
  return date.toLocaleDateString()
}

export function StagedFixBanner({ healings, onPromote, onReject }: StagedFixBannerProps) {
  const [promotingId, setPromotingId] = useState<string | null>(null)
  const [rejectingId, setRejectingId] = useState<string | null>(null)

  const stagedHealings = healings.filter(
    h => h.deployment_stage === 'staged' || h.status === 'staged'
  )

  if (stagedHealings.length === 0) return null

  const handlePromote = async (healingId: string) => {
    setPromotingId(healingId)
    try {
      await onPromote(healingId)
    } finally {
      setPromotingId(null)
    }
  }

  const handleReject = async (healingId: string) => {
    setRejectingId(healingId)
    try {
      await onReject(healingId)
    } finally {
      setRejectingId(null)
    }
  }

  return (
    <div className="space-y-3">
      {stagedHealings.map((healing) => (
        <div
          key={healing.id}
          className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-amber-500/20 rounded-lg mt-0.5">
                <AlertTriangle size={20} className="text-amber-400" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-amber-300">
                  Staged Fix Awaiting Review
                </h3>
                <p className="text-xs text-amber-300/70 mt-1">
                  {healing.fix_type.replace(/_/g, ' ')} fix is staged and deactivated.
                  Test in n8n, then promote or reject.
                </p>
                <div className="flex items-center gap-4 mt-2 text-xs text-amber-400/70">
                  {healing.workflow_id && (
                    <span>Workflow: {healing.workflow_id}</span>
                  )}
                  <span className="flex items-center gap-1">
                    <Clock size={12} />
                    Staged {formatTime(healing.staged_at || healing.created_at)}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              <Button
                variant="success"
                size="sm"
                onClick={() => handlePromote(healing.id)}
                isLoading={promotingId === healing.id}
                leftIcon={promotingId === healing.id
                  ? <Loader2 className="animate-spin" size={14} />
                  : <Play size={14} />
                }
                disabled={promotingId !== null || rejectingId !== null}
              >
                Promote
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => handleReject(healing.id)}
                isLoading={rejectingId === healing.id}
                leftIcon={rejectingId === healing.id
                  ? <Loader2 className="animate-spin" size={14} />
                  : <X size={14} />
                }
                disabled={promotingId !== null || rejectingId !== null}
              >
                Reject
              </Button>
              {healing.workflow_id && (
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<ExternalLink size={14} />}
                  onClick={() => {
                    // This would ideally link to the n8n workflow
                    // For now, open detection
                    window.open(`/detections/${healing.detection_id}`, '_blank')
                  }}
                >
                  View
                </Button>
              )}
            </div>
          </div>

          {/* Instructions */}
          <div className="mt-3 pt-3 border-t border-amber-500/20">
            <p className="text-xs text-amber-300/60">
              <strong>To test:</strong> Open your n8n instance and manually run the workflow.
              The workflow is currently deactivated. If it works correctly, click Promote
              to activate it in production. If there are issues, click Reject to rollback.
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}
