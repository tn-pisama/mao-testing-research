'use client'

import { Check, Clock, AlertTriangle, RotateCcw, X, Loader2 } from 'lucide-react'

interface HealingTimelineProps {
  healing: {
    status: string
    metadata?: Record<string, any>
  }
}

const STEPS = [
  { key: 'created', label: 'Created', icon: Clock },
  { key: 'analyzing', label: 'Analyzing', icon: Loader2 },
  { key: 'generating_fix', label: 'Fix Generated', icon: Check },
  { key: 'staged', label: 'Staged', icon: Clock },
  { key: 'applying_fix', label: 'Applying', icon: Loader2 },
  { key: 'validating', label: 'Validating', icon: Loader2 },
]

const TERMINAL_STATES: Record<string, { label: string; icon: typeof Check; color: string }> = {
  success: { label: 'Success', icon: Check, color: 'text-green-400 border-green-400' },
  partial_success: { label: 'Partial Success', icon: AlertTriangle, color: 'text-yellow-400 border-yellow-400' },
  failed: { label: 'Failed', icon: X, color: 'text-red-400 border-red-400' },
  rollback: { label: 'Rolled Back', icon: RotateCcw, color: 'text-zinc-400 border-zinc-400' },
  rolled_back: { label: 'Rolled Back', icon: RotateCcw, color: 'text-zinc-400 border-zinc-400' },
}

function getStatusIndex(status: string): number {
  const idx = STEPS.findIndex((s) => s.key === status)
  if (idx >= 0) return idx
  // Terminal states are past all steps
  if (status in TERMINAL_STATES) return STEPS.length
  return 0
}

export function HealingTimeline({ healing }: HealingTimelineProps) {
  const currentIdx = getStatusIndex(healing.status)
  const terminal = TERMINAL_STATES[healing.status]
  const metadata = healing.metadata || {}

  return (
    <div className="flex items-center gap-0">
      {STEPS.map((step, idx) => {
        const isComplete = idx < currentIdx
        const isCurrent = idx === currentIdx && !terminal
        const Icon = step.icon

        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center border-2 ${
                  isComplete
                    ? 'bg-green-500/20 border-green-400 text-green-400'
                    : isCurrent
                    ? 'bg-blue-500/20 border-blue-400 text-blue-400'
                    : 'bg-zinc-800 border-zinc-600 text-zinc-500'
                }`}
              >
                {isComplete ? (
                  <Check size={14} />
                ) : isCurrent ? (
                  <Icon size={14} className="animate-pulse" />
                ) : (
                  <span className="text-xs">{idx + 1}</span>
                )}
              </div>
              <span
                className={`text-xs mt-1 whitespace-nowrap ${
                  isComplete || isCurrent ? 'text-zinc-300' : 'text-zinc-500'
                }`}
              >
                {step.label}
              </span>
              {metadata[`${step.key}_at`] && (
                <span className="text-[10px] text-zinc-600">
                  {new Date(metadata[`${step.key}_at`]).toLocaleTimeString()}
                </span>
              )}
            </div>
            {idx < STEPS.length - 1 && (
              <div
                className={`w-8 h-0.5 mt-[-16px] ${
                  idx < currentIdx ? 'bg-green-400/50' : 'bg-zinc-700'
                }`}
              />
            )}
          </div>
        )
      })}

      {/* Terminal state */}
      {terminal && (
        <>
          <div className={`w-8 h-0.5 mt-[-16px] ${
            terminal.color.includes('green') ? 'bg-green-400/50' : 'bg-zinc-600'
          }`} />
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 ${terminal.color} bg-zinc-800`}>
              <terminal.icon size={14} />
            </div>
            <span className={`text-xs mt-1 whitespace-nowrap ${terminal.color.split(' ')[0]}`}>
              {terminal.label}
            </span>
          </div>
        </>
      )}
    </div>
  )
}
