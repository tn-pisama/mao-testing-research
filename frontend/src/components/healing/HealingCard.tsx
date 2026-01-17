'use client'

import { useState } from 'react'
import {
  Clock,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  RotateCcw,
  Play,
  X,
  ExternalLink
} from 'lucide-react'
import { Card, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import type { HealingRecord } from '@/lib/api'

interface HealingCardProps {
  healing: HealingRecord
  onPromote?: (healingId: string) => Promise<void>
  onReject?: (healingId: string) => Promise<void>
  onRollback?: (healingId: string) => Promise<void>
  isExpanded?: boolean
}

const statusConfig = {
  pending: { label: 'Pending', variant: 'warning' as const, icon: Clock },
  in_progress: { label: 'In Progress', variant: 'info' as const, icon: Loader2 },
  staged: { label: 'Staged', variant: 'warning' as const, icon: AlertTriangle },
  applied: { label: 'Applied', variant: 'success' as const, icon: CheckCircle2 },
  failed: { label: 'Failed', variant: 'error' as const, icon: XCircle },
  rolled_back: { label: 'Rolled Back', variant: 'default' as const, icon: RotateCcw },
  rejected: { label: 'Rejected', variant: 'error' as const, icon: X },
}

const deploymentStageConfig = {
  staged: { label: 'Staged for Testing', color: 'text-amber-400 bg-amber-500/20' },
  promoted: { label: 'Promoted to Production', color: 'text-green-400 bg-green-500/20' },
  rejected: { label: 'Rejected', color: 'text-red-400 bg-red-500/20' },
  rolled_back: { label: 'Rolled Back', color: 'text-slate-400 bg-slate-500/20' },
}

function formatTime(isoString: string | null): string {
  if (!isoString) return 'N/A'
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

export function HealingCard({
  healing,
  onPromote,
  onReject,
  onRollback,
  isExpanded: initialExpanded = false
}: HealingCardProps) {
  const [isExpanded, setIsExpanded] = useState(initialExpanded)
  const [isPromoting, setIsPromoting] = useState(false)
  const [isRejecting, setIsRejecting] = useState(false)
  const [isRollingBack, setIsRollingBack] = useState(false)

  const status = statusConfig[healing.status] || statusConfig.pending
  const StatusIcon = status.icon
  const deploymentStage = healing.deployment_stage
    ? deploymentStageConfig[healing.deployment_stage]
    : null

  const handlePromote = async () => {
    if (!onPromote) return
    setIsPromoting(true)
    try {
      await onPromote(healing.id)
    } finally {
      setIsPromoting(false)
    }
  }

  const handleReject = async () => {
    if (!onReject) return
    setIsRejecting(true)
    try {
      await onReject(healing.id)
    } finally {
      setIsRejecting(false)
    }
  }

  const handleRollback = async () => {
    if (!onRollback) return
    setIsRollingBack(true)
    try {
      await onRollback(healing.id)
    } finally {
      setIsRollingBack(false)
    }
  }

  const showPromoteReject = healing.status === 'staged' || healing.deployment_stage === 'staged'
  const showRollback = healing.rollback_available &&
    (healing.status === 'applied' || healing.deployment_stage === 'promoted')

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-0">
        {/* Header */}
        <div
          className="p-4 cursor-pointer hover:bg-slate-800/50 transition-colors"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <StatusIcon
                size={20}
                className={
                  healing.status === 'in_progress' ? 'animate-spin text-blue-400' :
                  healing.status === 'applied' ? 'text-green-400' :
                  healing.status === 'failed' || healing.status === 'rejected' ? 'text-red-400' :
                  healing.status === 'staged' ? 'text-amber-400' :
                  'text-slate-400'
                }
              />
              <div>
                <p className="text-sm font-medium text-white">
                  {healing.fix_type.replace(/_/g, ' ')}
                </p>
                <p className="text-xs text-slate-500">
                  Detection: {healing.detection_id.slice(0, 8)}...
                  {healing.workflow_id && ` | Workflow: ${healing.workflow_id}`}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant={status.variant} size="sm">
                {status.label}
              </Badge>
              {deploymentStage && (
                <span className={`text-xs px-2 py-1 rounded ${deploymentStage.color}`}>
                  {deploymentStage.label}
                </span>
              )}
              <div className="flex items-center gap-1 text-xs text-slate-500">
                <Clock size={12} />
                {formatTime(healing.created_at)}
              </div>
              {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </div>
          </div>
        </div>

        {/* Expanded Content */}
        {isExpanded && (
          <div className="border-t border-slate-700 p-4 space-y-4">
            {/* Details Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-slate-500 text-xs mb-1">Status</p>
                <p className="text-white">{status.label}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs mb-1">Fix ID</p>
                <p className="text-white font-mono text-xs">{healing.fix_id || 'N/A'}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs mb-1">Started</p>
                <p className="text-white">{formatTime(healing.started_at)}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs mb-1">Completed</p>
                <p className="text-white">{formatTime(healing.completed_at)}</p>
              </div>
            </div>

            {/* Staged Deployment Info */}
            {healing.deployment_stage && (
              <div className="bg-slate-800/50 rounded-lg p-3">
                <p className="text-xs text-slate-500 mb-2">Staged Deployment</p>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-slate-400">Stage</p>
                    <p className="text-white">{healing.deployment_stage}</p>
                  </div>
                  {healing.staged_at && (
                    <div>
                      <p className="text-slate-400">Staged At</p>
                      <p className="text-white">{formatTime(healing.staged_at)}</p>
                    </div>
                  )}
                  {healing.promoted_at && (
                    <div>
                      <p className="text-slate-400">Promoted At</p>
                      <p className="text-white">{formatTime(healing.promoted_at)}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Error Message */}
            {healing.error_message && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                <p className="text-xs text-red-400 mb-1">Error</p>
                <p className="text-sm text-red-300">{healing.error_message}</p>
              </div>
            )}

            {/* Fix Suggestions */}
            {healing.fix_suggestions && healing.fix_suggestions.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-slate-500">Fix Suggestions</p>
                {healing.fix_suggestions.map((suggestion, idx) => (
                  <div
                    key={suggestion.id || idx}
                    className="bg-slate-800/50 rounded-lg p-3"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium text-white">{suggestion.title}</p>
                      <Badge variant="info" size="sm">
                        {suggestion.confidence}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-400">{suggestion.description}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2 pt-2 border-t border-slate-700">
              {showPromoteReject && (
                <>
                  <Button
                    variant="success"
                    size="sm"
                    onClick={handlePromote}
                    isLoading={isPromoting}
                    leftIcon={<Play size={14} />}
                  >
                    Promote
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleReject}
                    isLoading={isRejecting}
                    leftIcon={<X size={14} />}
                  >
                    Reject
                  </Button>
                </>
              )}
              {showRollback && (
                <Button
                  variant="warning"
                  size="sm"
                  onClick={handleRollback}
                  isLoading={isRollingBack}
                  leftIcon={<RotateCcw size={14} />}
                >
                  Rollback
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<ExternalLink size={14} />}
                onClick={() => window.open(`/detections/${healing.detection_id}`, '_blank')}
              >
                View Detection
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
