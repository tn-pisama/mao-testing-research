'use client'

import { useState } from 'react'
import { RotateCcw, Play, X, ExternalLink, ShieldCheck, FlaskConical } from 'lucide-react'
import { Button } from '../ui/Button'
import type { HealingRecord } from '@/lib/api'

interface HealingCardActionsProps {
  healing: HealingRecord
  onPromote?: (healingId: string) => Promise<void>
  onReject?: (healingId: string) => Promise<void>
  onRollback?: (healingId: string) => Promise<void>
  onVerify?: (healingId: string, level?: number) => Promise<void>
}

export function HealingCardActions({
  healing,
  onPromote,
  onReject,
  onRollback,
  onVerify,
}: HealingCardActionsProps) {
  const [isPromoting, setIsPromoting] = useState(false)
  const [isRejecting, setIsRejecting] = useState(false)
  const [isRollingBack, setIsRollingBack] = useState(false)
  const [isVerifying, setIsVerifying] = useState(false)

  const isVerified = healing.validation_status === 'passed'
  const showPromoteReject = healing.status === 'staged' || healing.deployment_stage === 'staged'
  const showRollback = healing.rollback_available &&
    (healing.status === 'applied' || healing.deployment_stage === 'promoted')

  const handleAction = async (
    action: ((id: string, level?: number) => Promise<void>) | undefined,
    setLoading: (v: boolean) => void,
    level?: number,
  ) => {
    if (!action) return
    setLoading(true)
    try {
      await action(healing.id, level)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center gap-2 pt-2 border-t border-zinc-700">
      {showPromoteReject && (
        <>
          {onVerify && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleAction(onVerify, setIsVerifying, 1)}
                isLoading={isVerifying}
                leftIcon={<ShieldCheck size={14} />}
                className={isVerified ? 'text-green-400' : ''}
                title="Level 1: Checks fix configuration without running the workflow"
              >
                {isVerified ? 'Re-verify' : 'Verify Fix'}
              </Button>
              {healing.n8n_connection_id && healing.workflow_id && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleAction(onVerify, setIsVerifying, 2)}
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
            onClick={() => handleAction(onPromote, setIsPromoting)}
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
            onClick={() => handleAction(onReject, setIsRejecting)}
            isLoading={isRejecting}
            leftIcon={<X size={14} />}
          >
            Don&apos;t Apply
          </Button>
        </>
      )}
      {showRollback && (
        <Button
          variant="warning"
          size="sm"
          onClick={() => handleAction(onRollback, setIsRollingBack)}
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
  )
}
