'use client'

import { CheckCircle2, Circle, XCircle, Loader2 } from 'lucide-react'
import type { HealingRecord } from '@/lib/api'

type StepState = 'completed' | 'current' | 'pending' | 'failed'

interface Step {
  label: string
  state: StepState
}

function getSteps(healing: HealingRecord): Step[] {
  const { status, deployment_stage, validation_status } = healing

  const isStaged = deployment_stage === 'staged' || deployment_stage === 'promoted'
  const isPromoted = deployment_stage === 'promoted'
  const isVerified = validation_status === 'passed'
  const isVerifyFailed = validation_status === 'failed'
  const isFailed = status === 'failed'
  const isRejected = status === 'rejected' || deployment_stage === 'rejected'

  // Step 1: Detected — always completed (the record exists)
  const detected: Step = { label: 'Detected', state: 'completed' }

  // Step 2: Staged
  let staged: Step
  if (isFailed && !isPromoted) {
    staged = { label: 'Staged', state: 'failed' }
  } else if (isStaged) {
    staged = { label: 'Staged', state: 'completed' }
  } else if (status === 'in_progress') {
    staged = { label: 'Staging', state: 'current' }
  } else {
    staged = { label: 'Staged', state: status === 'pending' ? 'current' : 'pending' }
  }

  // Step 3: Verified
  let verified: Step
  if (isVerifyFailed) {
    verified = { label: 'Verified', state: 'failed' }
  } else if (isVerified) {
    verified = { label: 'Verified', state: 'completed' }
  } else if (isStaged && !isPromoted) {
    verified = { label: 'Verify', state: 'current' }
  } else {
    verified = { label: 'Verify', state: 'pending' }
  }

  // Step 4: Promoted
  let promoted: Step
  if (isRejected) {
    promoted = { label: 'Rejected', state: 'failed' }
  } else if (isPromoted) {
    promoted = { label: 'Promoted', state: 'completed' }
  } else if (isVerified && isStaged) {
    promoted = { label: 'Promote', state: 'current' }
  } else {
    promoted = { label: 'Promote', state: 'pending' }
  }

  return [detected, staged, verified, promoted]
}

const stateStyles = {
  completed: {
    circle: 'bg-green-500/20 text-green-400',
    connector: 'bg-green-500/40',
    label: 'text-green-400',
  },
  current: {
    circle: 'bg-blue-500/20 text-blue-400 ring-2 ring-blue-500/40',
    connector: 'bg-slate-600',
    label: 'text-blue-400 font-medium',
  },
  pending: {
    circle: 'bg-slate-700 text-slate-500',
    connector: 'bg-slate-700',
    label: 'text-slate-500',
  },
  failed: {
    circle: 'bg-red-500/20 text-red-400',
    connector: 'bg-red-500/40',
    label: 'text-red-400',
  },
}

function StepIcon({ state }: { state: StepState }) {
  switch (state) {
    case 'completed':
      return <CheckCircle2 size={16} />
    case 'current':
      return <Circle size={16} className="animate-pulse" />
    case 'failed':
      return <XCircle size={16} />
    case 'pending':
      return <Circle size={16} />
  }
}

export function PipelineStepper({ healing }: { healing: HealingRecord }) {
  const steps = getSteps(healing)

  return (
    <div className="flex items-center w-full">
      {steps.map((step, i) => (
        <div key={step.label} className="flex items-center flex-1 last:flex-none">
          {/* Step */}
          <div className="flex flex-col items-center gap-1">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center ${stateStyles[step.state].circle}`}>
              <StepIcon state={step.state} />
            </div>
            <span className={`text-[10px] whitespace-nowrap ${stateStyles[step.state].label}`}>
              {step.label}
            </span>
          </div>
          {/* Connector */}
          {i < steps.length - 1 && (
            <div className={`h-0.5 flex-1 mx-2 rounded-full ${stateStyles[step.state === 'completed' ? 'completed' : 'pending'].connector}`} />
          )}
        </div>
      ))}
    </div>
  )
}
