'use client'

import { AlertTriangle, RefreshCcw, CheckCircle, XCircle } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import type { Detection } from '@/lib/api'
import { clsx } from 'clsx'

interface FailureCardProps {
  detection: Detection
  onValidate?: (id: string, falsePositive: boolean) => void
}

export function FailureCard({ detection, onValidate }: FailureCardProps) {
  const icons = {
    loop: RefreshCcw,
    corruption: AlertTriangle,
    persona: AlertTriangle,
    coordination: AlertTriangle,
  }
  const Icon = icons[detection.detection_type as keyof typeof icons] || AlertTriangle

  return (
    <div
      className={clsx(
        'bg-slate-800 rounded-lg border p-4',
        detection.false_positive === true
          ? 'border-slate-600'
          : detection.validated
          ? 'border-success-500/50'
          : 'border-danger-500/50'
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={clsx(
            'p-2 rounded-lg',
            detection.false_positive === true
              ? 'bg-slate-700 text-slate-400'
              : 'bg-danger-500/20 text-danger-500'
          )}
        >
          <Icon size={20} />
        </div>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <h4 className="font-medium text-white capitalize">
              {detection.detection_type} Detected
            </h4>
            <span className="text-xs text-slate-400">
              {formatDistanceToNow(new Date(detection.created_at), { addSuffix: true })}
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm text-slate-400 mb-2">
            <span>Confidence: {detection.confidence}%</span>
            <span>Method: {detection.method}</span>
          </div>
          {detection.details && Object.keys(detection.details).length > 0 && (
            <pre className="bg-slate-900 rounded p-2 text-xs text-slate-300 overflow-x-auto">
              {JSON.stringify(detection.details, null, 2)}
            </pre>
          )}
          {!detection.validated && onValidate && (
            <div className="flex gap-2 mt-3">
              <button
                onClick={() => onValidate(detection.id, false)}
                className="flex items-center gap-1 px-3 py-1.5 bg-success-500/20 text-success-500 rounded-lg text-sm hover:bg-success-500/30 transition-colors"
              >
                <CheckCircle size={14} />
                Confirm
              </button>
              <button
                onClick={() => onValidate(detection.id, true)}
                className="flex items-center gap-1 px-3 py-1.5 bg-slate-700 text-slate-300 rounded-lg text-sm hover:bg-slate-600 transition-colors"
              >
                <XCircle size={14} />
                False Positive
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
