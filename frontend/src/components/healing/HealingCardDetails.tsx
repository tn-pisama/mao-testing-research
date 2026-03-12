'use client'

import { CheckCircle2, XCircle, ShieldCheck } from 'lucide-react'
import { Badge } from '../ui/Badge'
import { TermTooltip } from '../ui/Tooltip'
import { PipelineStepper } from './PipelineStepper'
import { formatTime, getStatusConfig, getDeploymentStageConfig } from './HealingCardHeader'
import type { HealingRecord } from '@/lib/api'

interface HealingCardDetailsProps {
  healing: HealingRecord
}

export function HealingCardDetails({ healing }: HealingCardDetailsProps) {
  const status = getStatusConfig(healing.status)
  const StatusIcon = status.icon
  const deploymentStage = getDeploymentStageConfig(healing.deployment_stage)
  const isVerified = healing.validation_status === 'passed'

  return (
    <div className="border-t border-zinc-700 p-4 space-y-4">
      {/* Status explanation */}
      <div className="bg-zinc-800/50 rounded-lg p-3 mb-4">
        <div className="flex items-center gap-2 mb-1">
          <StatusIcon size={16} className={
            healing.status === 'applied' ? 'text-green-400' :
            healing.status === 'staged' ? 'text-amber-400' :
            healing.status === 'failed' || healing.status === 'rejected' ? 'text-red-400' :
            'text-zinc-400'
          } />
          <p className="text-sm font-medium text-white">{status.label}</p>
        </div>
        <p className="text-xs text-zinc-400">{status.description}</p>
      </div>

      <PipelineStepper healing={healing} />

      {/* Timeline */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-zinc-500 text-xs mb-1">Started</p>
          <p className="text-white">{formatTime(healing.started_at)}</p>
        </div>
        <div>
          <p className="text-zinc-500 text-xs mb-1">Completed</p>
          <p className="text-white">{formatTime(healing.completed_at)}</p>
        </div>
      </div>

      {/* Approval Audit Trail */}
      {healing.approval_required && (
        <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-3">
          <p className="text-xs text-purple-400 mb-2 font-medium">Approval Info</p>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-zinc-500 text-xs">Approved by</p>
              <p className="text-white">{healing.approved_by || 'Pending'}</p>
            </div>
            <div>
              <p className="text-zinc-500 text-xs">Approved at</p>
              <p className="text-white">{healing.approved_at ? formatTime(healing.approved_at) : 'Pending'}</p>
            </div>
          </div>
        </div>
      )}

      {/* Deployment Stage */}
      {healing.deployment_stage && deploymentStage && (
        <div className={`rounded-lg p-3 ${deploymentStage.color}`}>
          <p className="text-xs mb-1">Current Status</p>
          <p className="text-sm font-medium">{deploymentStage.label}</p>
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
        <VerificationResults healing={healing} isVerified={isVerified} />
      )}

      {/* Error Message */}
      {healing.error_message && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
          <p className="text-xs text-red-400 mb-1">What Went Wrong</p>
          <p className="text-sm text-red-300">{healing.error_message}</p>
        </div>
      )}

      {/* Fix Suggestions */}
      {healing.fix_suggestions && healing.fix_suggestions.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-zinc-500">Available Fixes</p>
          {healing.fix_suggestions.map((suggestion, idx) => (
            <div key={suggestion.id || idx} className="bg-zinc-800/50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-white">{suggestion.title}</p>
                <TermTooltip term="confidence">
                  <Badge variant="info" size="sm">
                    {suggestion.confidence}
                  </Badge>
                </TermTooltip>
              </div>
              <p className="text-xs text-zinc-400">{suggestion.description}</p>
            </div>
          ))}
        </div>
      )}

      {/* Technical details */}
      <details className="group">
        <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-400">
          Technical Details (click to expand)
        </summary>
        <div className="mt-2 grid grid-cols-2 gap-4 text-xs">
          <div>
            <p className="text-zinc-500">Fix ID</p>
            <p className="text-white">{healing.fix_id || 'N/A'}</p>
          </div>
          <div>
            <p className="text-zinc-500">Workflow ID</p>
            <p className="text-white">{healing.workflow_id || 'N/A'}</p>
          </div>
        </div>
      </details>
    </div>
  )
}

function VerificationResults({ healing, isVerified }: { healing: HealingRecord; isVerified: boolean }) {
  return (
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
          <p className="text-zinc-500">Before</p>
          <p className="text-white">
            {healing.validation_results.before_confidence != null
              ? `${(healing.validation_results.before_confidence * 100).toFixed(0)}% confidence`
              : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-zinc-500">After</p>
          <p className={healing.validation_results.after_confidence === 0 ? 'text-green-400' : 'text-white'}>
            {healing.validation_results.after_confidence != null
              ? `${(healing.validation_results.after_confidence * 100).toFixed(0)}% confidence`
              : 'N/A'}
          </p>
        </div>
        <div>
          <p className="text-zinc-500">Reduction</p>
          <p className="text-green-400">
            {healing.validation_results.confidence_reduction != null
              ? `${(healing.validation_results.confidence_reduction * 100).toFixed(0)}%`
              : 'N/A'}
          </p>
        </div>
      </div>
      {healing.validation_results.config_checks && (
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          {healing.validation_results.config_checks.map((check: { success: boolean; validation_type: string }, i: number) => (
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
  )
}
