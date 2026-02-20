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
  ExternalLink,
  ShieldCheck,
  FlaskConical
} from 'lucide-react'
import { Card, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { TermTooltip, getPlainEnglishStatus } from '../ui/Tooltip'
import { PipelineStepper } from './PipelineStepper'
import type { HealingRecord } from '@/lib/api'

interface HealingCardProps {
  healing: HealingRecord
  onPromote?: (healingId: string) => Promise<void>
  onReject?: (healingId: string) => Promise<void>
  onRollback?: (healingId: string) => Promise<void>
  onVerify?: (healingId: string, level?: number) => Promise<void>
  isExpanded?: boolean
}

const statusConfig = {
  pending: { label: 'Waiting', description: 'Fix is being prepared', variant: 'warning' as const, icon: Clock },
  in_progress: { label: 'Working on it', description: 'Fix is being applied', variant: 'info' as const, icon: Loader2 },
  staged: { label: 'Ready to test', description: 'Test it before going live', variant: 'warning' as const, icon: AlertTriangle },
  applied: { label: 'Fixed!', description: 'The fix is active', variant: 'success' as const, icon: CheckCircle2 },
  failed: { label: 'Couldn\'t fix', description: 'Something went wrong', variant: 'error' as const, icon: XCircle },
  rolled_back: { label: 'Undone', description: 'Fix was removed', variant: 'default' as const, icon: RotateCcw },
  rejected: { label: 'Not applied', description: 'Fix was declined', variant: 'error' as const, icon: X },
}

const deploymentStageConfig = {
  staged: { label: 'Ready to test', description: 'Fix is prepared but not live yet', color: 'text-amber-400 bg-amber-500/20' },
  promoted: { label: 'Live', description: 'Fix is active in your workflow', color: 'text-green-400 bg-green-500/20' },
  rejected: { label: 'Not applied', description: 'Fix was declined after review', color: 'text-red-400 bg-red-500/20' },
  rolled_back: { label: 'Undone', description: 'Fix was removed and workflow restored', color: 'text-slate-400 bg-slate-500/20' },
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
  onVerify,
  isExpanded: initialExpanded = false
}: HealingCardProps) {
  const [isExpanded, setIsExpanded] = useState(initialExpanded)
  const [isPromoting, setIsPromoting] = useState(false)
  const [isRejecting, setIsRejecting] = useState(false)
  const [isRollingBack, setIsRollingBack] = useState(false)
  const [isVerifying, setIsVerifying] = useState(false)

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

  const handleVerify = async (level: number = 1) => {
    if (!onVerify) return
    setIsVerifying(true)
    try {
      await onVerify(healing.id, level)
    } finally {
      setIsVerifying(false)
    }
  }

  const isVerified = healing.validation_status === 'passed'
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
              {healing.approval_required && healing.status === 'pending' && (
                <Badge variant="info" size="sm">
                  Awaiting Approval
                </Badge>
              )}
              {deploymentStage && (
                <span className={`text-xs px-2 py-1 rounded ${deploymentStage.color}`}>
                  {deploymentStage.label}
                </span>
              )}
              {healing.validation_status === 'passed' && (
                <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 flex items-center gap-1">
                  <ShieldCheck size={12} />
                  Verified
                </span>
              )}
              {healing.validation_status === 'failed' && (
                <span className="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 flex items-center gap-1">
                  <XCircle size={12} />
                  Unverified
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
            {/* Status explanation for non-technical users */}
            <div className="bg-slate-800/50 rounded-lg p-3 mb-4">
              <div className="flex items-center gap-2 mb-1">
                <StatusIcon size={16} className={
                  healing.status === 'applied' ? 'text-green-400' :
                  healing.status === 'staged' ? 'text-amber-400' :
                  healing.status === 'failed' || healing.status === 'rejected' ? 'text-red-400' :
                  'text-slate-400'
                } />
                <p className="text-sm font-medium text-white">{status.label}</p>
              </div>
              <p className="text-xs text-slate-400">{status.description}</p>
            </div>

            {/* Pipeline Progress */}
            <PipelineStepper healing={healing} />

            {/* Timeline - simple view of what happened */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-slate-500 text-xs mb-1">Started</p>
                <p className="text-white">{formatTime(healing.started_at)}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs mb-1">Completed</p>
                <p className="text-white">{formatTime(healing.completed_at)}</p>
              </div>
            </div>

            {/* Approval Audit Trail */}
            {healing.approval_required && (
              <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-3">
                <p className="text-xs text-purple-400 mb-2 font-medium">Approval Info</p>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="text-slate-500 text-xs">Approved by</p>
                    <p className="text-white">{healing.approved_by || 'Pending'}</p>
                  </div>
                  <div>
                    <p className="text-slate-500 text-xs">Approved at</p>
                    <p className="text-white">{healing.approved_at ? formatTime(healing.approved_at) : 'Pending'}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Testing Status - for staged deployments */}
            {healing.deployment_stage && (
              <div className={`rounded-lg p-3 ${deploymentStage?.color || 'bg-slate-500/20'}`}>
                <p className="text-xs mb-1">Current Status</p>
                <p className="text-sm font-medium">{deploymentStage?.label}</p>
                <p className="text-xs opacity-80 mt-1">{deploymentStage?.description}</p>
                <div className="grid grid-cols-2 gap-4 text-xs mt-2 opacity-70">
                  {healing.staged_at && (
                    <div>Ready to test: {formatTime(healing.staged_at)}</div>
                  )}
                  {healing.promoted_at && (
                    <div>Went live: {formatTime(healing.promoted_at)}</div>
                  )}
                </div>
              </div>
            )}

            {/* Verification Results */}
            {healing.validation_results && Object.keys(healing.validation_results).length > 0 && (
              <div className={`rounded-lg p-3 border ${
                isVerified ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  <ShieldCheck size={16} className={isVerified ? 'text-green-400' : 'text-red-400'} />
                  <p className="text-xs font-medium text-white">
                    Verification {isVerified ? 'Passed' : 'Failed'}
                  </p>
                  <Badge variant={isVerified ? 'success' : 'error'} size="sm">
                    Level {healing.validation_results.level || 1}
                  </Badge>
                </div>
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <p className="text-slate-500">Before</p>
                    <p className="text-white">
                      {healing.validation_results.before_confidence != null
                        ? `${(healing.validation_results.before_confidence * 100).toFixed(0)}% confidence`
                        : 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500">After</p>
                    <p className={healing.validation_results.after_confidence === 0 ? 'text-green-400' : 'text-white'}>
                      {healing.validation_results.after_confidence != null
                        ? `${(healing.validation_results.after_confidence * 100).toFixed(0)}% confidence`
                        : 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500">Reduction</p>
                    <p className="text-green-400">
                      {healing.validation_results.confidence_reduction != null
                        ? `${(healing.validation_results.confidence_reduction * 100).toFixed(0)}%`
                        : 'N/A'}
                    </p>
                  </div>
                </div>
                {healing.validation_results.config_checks && (
                  <div className="mt-2 flex items-center gap-2 flex-wrap">
                    {healing.validation_results.config_checks.map((check: any, i: number) => (
                      <span
                        key={i}
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${
                          check.success
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-red-500/20 text-red-400'
                        }`}
                      >
                        {check.success ? <CheckCircle2 size={10} /> : <XCircle size={10} />}
                        {check.validation_type.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Error Message - explain what went wrong */}
            {healing.error_message && (
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                <p className="text-xs text-red-400 mb-1">What Went Wrong</p>
                <p className="text-sm text-red-300">{healing.error_message}</p>
              </div>
            )}

            {/* Fix Suggestions - what we can do */}
            {healing.fix_suggestions && healing.fix_suggestions.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-slate-500">Available Fixes</p>
                {healing.fix_suggestions.map((suggestion, idx) => (
                  <div
                    key={suggestion.id || idx}
                    className="bg-slate-800/50 rounded-lg p-3"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium text-white">{suggestion.title}</p>
                      <TermTooltip term="confidence">
                        <Badge variant="info" size="sm">
                          {suggestion.confidence}
                        </Badge>
                      </TermTooltip>
                    </div>
                    <p className="text-xs text-slate-400">{suggestion.description}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Technical details - collapsed by default */}
            <details className="group">
              <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400">
                Technical Details (click to expand)
              </summary>
              <div className="mt-2 grid grid-cols-2 gap-4 text-xs">
                <div>
                  <p className="text-slate-500">Fix ID</p>
                  <p className="text-white font-mono">{healing.fix_id || 'N/A'}</p>
                </div>
                <div>
                  <p className="text-slate-500">Workflow ID</p>
                  <p className="text-white font-mono">{healing.workflow_id || 'N/A'}</p>
                </div>
              </div>
            </details>

            {/* Actions */}
            <div className="flex items-center gap-2 pt-2 border-t border-slate-700">
              {showPromoteReject && (
                <>
                  {onVerify && (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleVerify(1)}
                        isLoading={isVerifying}
                        leftIcon={<ShieldCheck size={14} />}
                        className={isVerified ? 'text-green-400' : ''}
                      >
                        {isVerified ? 'Re-verify' : 'Verify Fix'}
                      </Button>
                      {healing.n8n_connection_id && healing.workflow_id && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleVerify(2)}
                          isLoading={isVerifying}
                          leftIcon={<FlaskConical size={14} />}
                          className="text-blue-400"
                          title="Run the workflow and verify the fix works in practice"
                        >
                          Run Test
                        </Button>
                      )}
                    </>
                  )}
                  <Button
                    variant="success"
                    size="sm"
                    onClick={handlePromote}
                    isLoading={isPromoting}
                    leftIcon={<Play size={14} />}
                    disabled={!isVerified}
                    title={!isVerified ? 'Verify the fix first' : undefined}
                  >
                    Make it Live
                  </Button>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={handleReject}
                    isLoading={isRejecting}
                    leftIcon={<X size={14} />}
                  >
                    Don't Apply
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
                  Undo This Fix
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<ExternalLink size={14} />}
                onClick={() => window.open(`/detections/${healing.detection_id}`, '_blank')}
              >
                View Problem
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
