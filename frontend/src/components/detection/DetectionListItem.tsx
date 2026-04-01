import Link from 'next/link'
import { formatDistanceToNow } from 'date-fns'
import { cn } from '@/lib/utils'
import {
  CheckCircle,
  XCircle,
  ThumbsUp,
  ThumbsDown,
  ChevronRight,
  Wrench,
  Loader2,
} from 'lucide-react'
import { detectionTypeConfig, severityConfig, plainEnglishLabels } from './DetectionTypeConfig'

interface DetectionListItemProps {
  detection: {
    id: string
    detection_type: string
    trace_id: string
    confidence: number
    method: string
    validated: boolean
    false_positive?: boolean
    created_at: string
    details?: {
      severity?: string
      affected_agents?: number
    }
  }
  showSimplifiedView: boolean
  inlineValidated: Record<string, { validated: boolean; false_positive: boolean }>
  submittingId: string | null
  onInlineValidate: (e: React.MouseEvent, detectionId: string, isFalsePositive: boolean) => void
}

export function DetectionListItem({
  detection,
  showSimplifiedView,
  inlineValidated,
  submittingId,
  onInlineValidate,
}: DetectionListItemProps) {
  const typeConfig = detectionTypeConfig[detection.detection_type] || detectionTypeConfig.infinite_loop
  const severity = severityConfig[detection.details?.severity || 'medium']
  const TypeIcon = typeConfig.icon
  const displayLabel = showSimplifiedView
    ? (plainEnglishLabels[detection.detection_type] || typeConfig.label)
    : typeConfig.label

  return (
    <Link
      href={showSimplifiedView ? `/healing?detection=${detection.id}` : `/traces/${detection.trace_id}`}
      className="flex items-center gap-4 p-4 hover:bg-zinc-700/30 transition-colors"
    >
      <div className={cn('p-2 rounded-lg', severity.bg)}>
        <TypeIcon size={16} className={typeConfig.color} />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-white">{displayLabel}</span>
          <span className={cn('text-xs px-2 py-0.5 rounded-full', severity.bg, severity.color)}>
            {severity.label}
          </span>
          {detection.validated && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
              {showSimplifiedView ? 'Confirmed' : 'Validated'}
            </span>
          )}
          {detection.false_positive && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-500/20 text-zinc-400">
              {showSimplifiedView ? 'Not an Issue' : 'False Positive'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs text-zinc-400">
          {showSimplifiedView ? (
            <>
              <span>{formatDistanceToNow(new Date(detection.created_at), { addSuffix: true })}</span>
              {severity.label !== 'Low' && (
                <span className="text-amber-400">Recommended to fix</span>
              )}
            </>
          ) : (
            <>
              <span>{Math.round(detection.confidence)}% confidence</span>
              <span>via {detection.method.replace('_', ' ')}</span>
              <span>{detection.details?.affected_agents} agents affected</span>
            </>
          )}
        </div>
      </div>

      <div className="text-right">
        {showSimplifiedView ? (
          <div className="flex items-center gap-2">
            <Link
              href={`/healing?detection=${detection.id}`}
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
            >
              <Wrench size={14} />
              Fix
            </Link>
          </div>
        ) : (
          <>
            <div className="text-xs text-zinc-400 mb-1">
              {formatDistanceToNow(new Date(detection.created_at), { addSuffix: true })}
            </div>
            <div className="flex items-center gap-1">
              {(() => {
                const effective = inlineValidated[detection.id] ?? { validated: detection.validated, false_positive: detection.false_positive }
                if (effective.validated) {
                  return effective.false_positive ? (
                    <span className="flex items-center gap-1 text-xs text-zinc-400">
                      <XCircle size={14} /> FP
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-emerald-400">
                      <CheckCircle size={14} />
                    </span>
                  )
                }
                return (
                  <>
                    <button
                      onClick={(e) => onInlineValidate(e, detection.id, false)}
                      disabled={submittingId === detection.id}
                      className="p-1.5 rounded hover:bg-emerald-500/20 text-zinc-400 hover:text-emerald-400 transition-colors disabled:opacity-50"
                      title="Mark as valid"
                      aria-label="Mark detection as valid"
                    >
                      {submittingId === detection.id ? <Loader2 size={14} className="animate-spin" /> : <ThumbsUp size={14} />}
                    </button>
                    <button
                      onClick={(e) => onInlineValidate(e, detection.id, true)}
                      disabled={submittingId === detection.id}
                      className="p-1.5 rounded hover:bg-red-500/20 text-zinc-400 hover:text-red-400 transition-colors disabled:opacity-50"
                      title="Mark as false positive"
                      aria-label="Mark detection as false positive"
                    >
                      <ThumbsDown size={14} />
                    </button>
                  </>
                )
              })()}
              <ChevronRight size={14} className="text-zinc-500" />
            </div>
          </>
        )}
      </div>
    </Link>
  )
}
