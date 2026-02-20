'use client'

import { useState } from 'react'
import { AlertTriangle, Play, X, Clock, ExternalLink, Loader2, ShieldCheck, CheckCircle2, XCircle, FlaskConical } from 'lucide-react'
import { Button } from '../ui/Button'
import { PipelineStepper } from './PipelineStepper'
import type { HealingRecord } from '@/lib/api'

interface StagedFixBannerProps {
  healings: HealingRecord[]
  onPromote: (healingId: string) => Promise<void>
  onReject: (healingId: string) => Promise<void>
  onVerify: (healingId: string, level?: number) => Promise<void>
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

export function StagedFixBanner({ healings, onPromote, onReject, onVerify }: StagedFixBannerProps) {
  const [promotingId, setPromotingId] = useState<string | null>(null)
  const [rejectingId, setRejectingId] = useState<string | null>(null)
  const [verifyingId, setVerifyingId] = useState<string | null>(null)

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

  const handleVerify = async (healingId: string, level: number = 1) => {
    setVerifyingId(healingId)
    try {
      await onVerify(healingId, level)
    } finally {
      setVerifyingId(null)
    }
  }

  const isVerified = (healing: HealingRecord) => healing.validation_status === 'passed'
  const isVerificationFailed = (healing: HealingRecord) => healing.validation_status === 'failed'
  const anyBusy = promotingId !== null || rejectingId !== null || verifyingId !== null

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
                  {isVerified(healing)
                    ? ' Verified and ready to promote.'
                    : ' Verify the fix before promoting.'}
                </p>
                <div className="flex items-center gap-4 mt-2 text-xs text-amber-400/70">
                  {healing.workflow_id && (
                    <span>Workflow: {healing.workflow_id}</span>
                  )}
                  <span className="flex items-center gap-1">
                    <Clock size={12} />
                    Staged {formatTime(healing.staged_at || healing.created_at)}
                  </span>
                  {/* Verification badge */}
                  {isVerified(healing) && (
                    <span className="flex items-center gap-1 text-green-400">
                      <CheckCircle2 size={12} />
                      Verified
                    </span>
                  )}
                  {isVerificationFailed(healing) && (
                    <span className="flex items-center gap-1 text-red-400">
                      <XCircle size={12} />
                      Verification Failed
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              {/* Verify button - always available */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleVerify(healing.id, 1)}
                isLoading={verifyingId === healing.id}
                leftIcon={verifyingId === healing.id
                  ? <Loader2 className="animate-spin" size={14} />
                  : <ShieldCheck size={14} />
                }
                disabled={anyBusy}
                className={isVerified(healing) ? 'text-green-400 border-green-500/30' : ''}
                title="Level 1: Checks fix configuration without running the workflow"
              >
                {isVerified(healing) ? 'Re-verify' : 'Verify'}
              </Button>
              {/* Level 2: Run Test - only when n8n connection exists */}
              {healing.n8n_connection_id && healing.workflow_id && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleVerify(healing.id, 2)}
                  isLoading={verifyingId === healing.id}
                  leftIcon={<FlaskConical size={14} />}
                  disabled={anyBusy}
                  className="text-blue-400"
                  title="Run the workflow and verify the fix works in practice"
                >
                  Run Test
                </Button>
              )}
              {/* Promote - enabled only after verification */}
              <Button
                variant="success"
                size="sm"
                onClick={() => handlePromote(healing.id)}
                isLoading={promotingId === healing.id}
                leftIcon={promotingId === healing.id
                  ? <Loader2 className="animate-spin" size={14} />
                  : <Play size={14} />
                }
                disabled={anyBusy || !isVerified(healing)}
                title={!isVerified(healing) ? 'Verify the fix before promoting' : undefined}
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
                disabled={anyBusy}
              >
                Reject
              </Button>
              {healing.workflow_id && (
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<ExternalLink size={14} />}
                  onClick={() => {
                    window.open(`/detections/${healing.detection_id}`, '_blank')
                  }}
                >
                  View
                </Button>
              )}
            </div>
          </div>

          {/* Pipeline Progress */}
          <div className="mt-3 pt-3 border-t border-amber-500/20">
            <PipelineStepper healing={healing} />
          </div>

          {/* Verification results summary */}
          {healing.validation_results && Object.keys(healing.validation_results).length > 0 && (
            <div className="mt-3 pt-3 border-t border-amber-500/20">
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck size={14} className={isVerified(healing) ? 'text-green-400' : 'text-red-400'} />
                <p className="text-xs font-medium text-amber-300">
                  Verification Results
                </p>
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div>
                  <p className="text-slate-500">Level</p>
                  <p className="text-white">{healing.validation_results.level || 1}</p>
                </div>
                <div>
                  <p className="text-slate-500">Confidence Before</p>
                  <p className="text-white">
                    {healing.validation_results.before_confidence != null
                      ? `${(healing.validation_results.before_confidence * 100).toFixed(0)}%`
                      : 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-slate-500">Confidence After</p>
                  <p className={`${healing.validation_results.after_confidence === 0 ? 'text-green-400' : 'text-white'}`}>
                    {healing.validation_results.after_confidence != null
                      ? `${(healing.validation_results.after_confidence * 100).toFixed(0)}%`
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

          {/* Instructions - updated for verification flow */}
          {!healing.validation_results?.config_checks && (
            <div className="mt-3 pt-3 border-t border-amber-500/20">
              <p className="text-xs text-amber-300/60">
                <strong>Step 1:</strong> Click Verify to run automated checks on the fix.
                <strong> Step 2:</strong> Once verified, click Promote to activate it in production.
              </p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
