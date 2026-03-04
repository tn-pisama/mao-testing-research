'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { useThresholdTuning } from '@/hooks/useApiWithFallback'
import { CheckCircle2, XCircle, HelpCircle, SkipForward, ChevronLeft, ChevronRight, AlertCircle, Target, TrendingUp } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, Detection as ApiDetection } from '@/lib/api'
import { cn } from '@/lib/utils'

interface Detection {
  id: string
  type: string
  traceId: string
  agentType: string
  pattern: string
  confidence: number
}

const DETECTION_TYPES = [
  { group: 'System', types: [
    'loop', 'corruption', 'hallucination', 'injection', 'overflow',
    'withholding', 'completion', 'specification', 'decomposition',
    'workflow', 'grounding', 'retrieval_quality',
  ]},
  { group: 'Inter-Agent', types: [
    'coordination', 'persona_drift', 'derailment', 'context', 'communication',
  ]},
]

const SEVERITY_LABELS = ['Minor', 'Low', 'Medium', 'High', 'Critical']

export default function ReviewPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const { feedbackStats: stats } = useThresholdTuning()
  const [detections, setDetections] = useState<Detection[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [filter, setFilter] = useState('all')
  const [reviewed, setReviewed] = useState(0)
  const [showFeedback, setShowFeedback] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const [severityRating, setSeverityRating] = useState<number | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showUnvalidatedOnly, setShowUnvalidatedOnly] = useState(true)

  const loadDetections = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const response = await api.getDetections({
        perPage: 50,
        page: 1,
        type: filter === 'all' ? undefined : filter,
        validated: showUnvalidatedOnly ? false : undefined,
      })
      setDetections(response.items.map((d: ApiDetection) => ({
        id: d.id,
        type: d.detection_type,
        traceId: d.trace_id,
        agentType: d.method,
        pattern: d.explanation || d.detection_type,
        confidence: d.confidence
      })))
    } catch (err) {
      console.error('Failed to load detections:', err)
      setError('Failed to load detections for review.')
    }
    setIsLoading(false)
  }, [getToken, tenantId, filter, showUnvalidatedOnly])

  useEffect(() => {
    loadDetections()
  }, [loadDetections])

  const current = detections[currentIndex]
  const pending = detections.length - reviewed

  const handleLabel = useCallback(async (label: 'correct' | 'false_positive' | 'unclear' | 'skip') => {
    if (!current || isSubmitting) return

    if (label === 'skip') {
      setShowFeedback('Skipped')
      setTimeout(() => {
        setShowFeedback(null)
        if (currentIndex < detections.length - 1) {
          setCurrentIndex(i => i + 1)
        }
      }, 500)
      return
    }

    setIsSubmitting(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      const isCorrect = label === 'correct'
      const reason = label === 'unclear'
        ? (notes ? `unclear - ${notes}` : 'unclear')
        : (notes || undefined)

      await api.submitFeedback(current.id, isCorrect, {
        reason,
        severityRating: severityRating ?? undefined,
      })

      setReviewed(r => r + 1)

      const feedbackMap = {
        correct: 'Marked as correct',
        false_positive: 'Marked as false positive',
        unclear: 'Marked as unclear',
      }
      setShowFeedback(feedbackMap[label])
      setNotes('')
      setSeverityRating(null)

      setTimeout(() => {
        setShowFeedback(null)
        if (currentIndex < detections.length - 1) {
          setCurrentIndex(i => i + 1)
        }
      }, 500)
    } catch (err: any) {
      if (err?.status === 409) {
        // Already reviewed — silently advance
        setReviewed(r => r + 1)
        setShowFeedback('Already reviewed')
        setNotes('')
        setSeverityRating(null)
        setTimeout(() => {
          setShowFeedback(null)
          if (currentIndex < detections.length - 1) {
            setCurrentIndex(i => i + 1)
          }
        }, 500)
      } else {
        console.error('Failed to submit feedback:', err)
        setShowFeedback('Error submitting feedback')
        setTimeout(() => setShowFeedback(null), 2000)
      }
    } finally {
      setIsSubmitting(false)
    }
  }, [current, currentIndex, detections.length, isSubmitting, getToken, tenantId, notes, severityRating])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      switch (e.key.toLowerCase()) {
        case 'c': handleLabel('correct'); break
        case 'f': handleLabel('false_positive'); break
        case 'u': handleLabel('unclear'); break
        case 's': handleLabel('skip'); break
        case 'arrowleft': setCurrentIndex(i => Math.max(0, i - 1)); break
        case 'arrowright': setCurrentIndex(i => Math.min(detections.length - 1, i + 1)); break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleLabel, detections.length])

  if (isLoading) {
    return (
      <Layout>
        <div className="p-6 animate-pulse">
          <div className="h-8 w-64 bg-zinc-700 rounded mb-6" />
          <div className="h-64 bg-zinc-700 rounded-xl" />
        </div>
      </Layout>
    )
  }

  if (error) {
    return (
      <Layout>
        <div className="p-6 flex flex-col items-center justify-center h-[60vh]">
          <AlertCircle className="text-red-400 mb-4" size={64} />
          <h2 className="text-xl font-semibold text-white mb-2">Failed to load detections</h2>
          <p className="text-zinc-400 mb-4">{error}</p>
          <Button onClick={loadDetections}>Try Again</Button>
        </div>
      </Layout>
    )
  }

  if (detections.length === 0) {
    return (
      <Layout>
        <div className="p-6 flex flex-col items-center justify-center h-[60vh]">
          <CheckCircle2 className="text-emerald-400 mb-4" size={64} />
          <h2 className="text-xl font-semibold text-white mb-2">All caught up!</h2>
          <p className="text-zinc-400">No detections pending review.</p>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-4 md:p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">Detection Review Queue</h1>
            <p className="text-zinc-400 text-sm mt-1">
              {reviewed} reviewed today - {pending} pending
            </p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer">
              <input
                type="checkbox"
                checked={showUnvalidatedOnly}
                onChange={(e) => {
                  setShowUnvalidatedOnly(e.target.checked)
                  setCurrentIndex(0)
                }}
                className="rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-blue-500"
              />
              Unvalidated only
            </label>
            <select
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value)
                setCurrentIndex(0)
              }}
              className="bg-zinc-700 border border-zinc-600 rounded-lg px-3 py-2 text-white text-sm"
            >
              <option value="all">All Types</option>
              {DETECTION_TYPES.map(group => (
                <optgroup key={group.group} label={group.group}>
                  {group.types.map(type => (
                    <option key={type} value={type}>
                      {type.replace(/_/g, ' ')}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
        </div>

        {/* Stats strip */}
        {stats && stats.total_feedback > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
              <div className="flex items-center gap-1.5 mb-1">
                <Target size={14} className="text-zinc-400" />
                <span className="text-xs text-zinc-400">Reviewed</span>
              </div>
              <span className="text-lg font-bold text-white">{stats.total_feedback}</span>
            </div>
            <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
              <div className="flex items-center gap-1.5 mb-1">
                <CheckCircle2 size={14} className="text-emerald-400" />
                <span className="text-xs text-zinc-400">Precision</span>
              </div>
              <span className="text-lg font-bold text-white">{(stats.precision * 100).toFixed(1)}%</span>
            </div>
            <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
              <div className="flex items-center gap-1.5 mb-1">
                <TrendingUp size={14} className="text-blue-400" />
                <span className="text-xs text-zinc-400">Recall</span>
              </div>
              <span className="text-lg font-bold text-white">{(stats.recall * 100).toFixed(1)}%</span>
            </div>
            <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
              <div className="flex items-center gap-1.5 mb-1">
                <Target size={14} className="text-purple-400" />
                <span className="text-xs text-zinc-400">F1</span>
              </div>
              <span className="text-lg font-bold text-white">{(stats.f1_score * 100).toFixed(1)}%</span>
            </div>
            <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
              <div className="flex items-center gap-1.5 mb-1">
                <XCircle size={14} className="text-red-400" />
                <span className="text-xs text-zinc-400">False Positives</span>
              </div>
              <span className="text-lg font-bold text-white">{stats.false_positives}</span>
            </div>
          </div>
        )}

        {/* Progress bar */}
        <div className="bg-zinc-800 rounded-lg p-4 mb-6 border border-zinc-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-zinc-400 text-sm">Session Progress</span>
            <span className="text-white font-medium">{reviewed}/{detections.length}</span>
          </div>
          <div className="w-full bg-zinc-700 rounded-full h-2">
            <div
              className="bg-emerald-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(reviewed / detections.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Review card */}
        {current && (
          <div className="bg-zinc-800 rounded-xl p-6 border border-zinc-700 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Detection #{current.id.slice(-6)} - {current.type.replace(/_/g, ' ')}
                </h2>
                <p className="text-zinc-400 text-sm mt-1">
                  Trace: {current.traceId.slice(0, 12)}... | Agent: {current.agentType}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentIndex(i => Math.max(0, i - 1))}
                  disabled={currentIndex === 0}
                >
                  <ChevronLeft size={16} />
                </Button>
                <span className="text-zinc-400 text-sm">
                  {currentIndex + 1} of {detections.length}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentIndex(i => Math.min(detections.length - 1, i + 1))}
                  disabled={currentIndex === detections.length - 1}
                >
                  <ChevronRight size={16} />
                </Button>
              </div>
            </div>

            <div className="bg-zinc-700/50 rounded-lg p-4 mb-4">
              <p className="text-zinc-300 mb-2">
                <strong>Pattern:</strong> {current.pattern}
              </p>
              <p className="text-zinc-300">
                <strong>Confidence:</strong>{' '}
                <span className={current.confidence >= 90 ? 'text-emerald-400' : current.confidence >= 70 ? 'text-amber-400' : 'text-red-400'}>
                  {current.confidence.toFixed(1)}%
                </span>
              </p>
            </div>

            <div className="flex items-center gap-3 mb-4">
              <Button variant="ghost" size="sm">View Trace</Button>
              <Button variant="ghost" size="sm">View Suggestion</Button>
            </div>

            {/* Severity rating */}
            <div className="mb-4">
              <p className="text-zinc-400 text-sm mb-2">Severity (optional)</p>
              <div className="flex items-center gap-2">
                {SEVERITY_LABELS.map((label, i) => (
                  <button
                    key={i}
                    onClick={() => setSeverityRating(severityRating === i + 1 ? null : i + 1)}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                      severityRating === i + 1
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                        : 'bg-zinc-700/50 text-zinc-400 border border-zinc-600 hover:border-zinc-500'
                    )}
                  >
                    {i + 1} - {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Notes */}
            <div className="mb-4">
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Why is this correct or a false positive? (optional)"
                rows={2}
                className="w-full px-3 py-2 bg-zinc-700/50 border border-zinc-600 rounded-lg text-white text-sm placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
            </div>

            {/* Feedback toast */}
            {showFeedback && (
              <div className="bg-zinc-700 rounded-lg p-3 mb-4 text-center">
                <span className="text-white">{showFeedback}</span>
                <span className="text-zinc-400 text-sm ml-2">Auto-advancing...</span>
              </div>
            )}

            {/* Label buttons */}
            <div className="border-t border-zinc-700 pt-4">
              <p className="text-zinc-400 text-sm mb-3">Was this detection correct?</p>
              <div className="flex items-center gap-3 flex-wrap">
                <Button
                  variant="success"
                  onClick={() => handleLabel('correct')}
                  leftIcon={<CheckCircle2 size={16} />}
                  disabled={isSubmitting}
                  loading={isSubmitting}
                >
                  Correct <kbd className="ml-2 text-xs opacity-60 bg-emerald-700 px-1 rounded">C</kbd>
                </Button>
                <Button
                  variant="danger"
                  onClick={() => handleLabel('false_positive')}
                  leftIcon={<XCircle size={16} />}
                  disabled={isSubmitting}
                >
                  False Positive <kbd className="ml-2 text-xs opacity-60 bg-red-700 px-1 rounded">F</kbd>
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => handleLabel('unclear')}
                  leftIcon={<HelpCircle size={16} />}
                  disabled={isSubmitting}
                >
                  Unclear <kbd className="ml-2 text-xs opacity-60 bg-zinc-600 px-1 rounded">U</kbd>
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => handleLabel('skip')}
                  leftIcon={<SkipForward size={16} />}
                  disabled={isSubmitting}
                >
                  Skip <kbd className="ml-2 text-xs opacity-60 bg-zinc-600 px-1 rounded">S</kbd>
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Keyboard shortcuts */}
        <div className="bg-zinc-800/50 rounded-lg p-4 border border-zinc-700">
          <p className="text-zinc-400 text-sm">
            <strong>Keyboard shortcuts:</strong>{' '}
            <kbd className="bg-zinc-700 px-1.5 py-0.5 rounded text-xs">C</kbd> Correct{' '}
            <kbd className="bg-zinc-700 px-1.5 py-0.5 rounded text-xs">F</kbd> False Positive{' '}
            <kbd className="bg-zinc-700 px-1.5 py-0.5 rounded text-xs">U</kbd> Unclear{' '}
            <kbd className="bg-zinc-700 px-1.5 py-0.5 rounded text-xs">S</kbd> Skip{' '}
            <kbd className="bg-zinc-700 px-1.5 py-0.5 rounded text-xs">&larr;/&rarr;</kbd> Navigate
          </p>
        </div>
      </div>
    </Layout>
  )
}
