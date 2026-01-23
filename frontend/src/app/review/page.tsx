'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { CheckCircle2, XCircle, HelpCircle, SkipForward, Filter, ChevronLeft, ChevronRight, AlertCircle } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, Detection as ApiDetection } from '@/lib/api'

interface Detection {
  id: string
  type: string
  traceId: string
  agentType: string
  pattern: string
  confidence: number
}

export default function ReviewPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [detections, setDetections] = useState<Detection[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [filter, setFilter] = useState('all')
  const [reviewed, setReviewed] = useState(0)
  const [showFeedback, setShowFeedback] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadDetections = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const data = await api.getDetections({ perPage: 50, page: 1, type: filter === 'all' ? undefined : filter })
      setDetections(data.map((d: ApiDetection) => ({
        id: d.id,
        type: d.detection_type,
        traceId: d.trace_id,
        agentType: d.method,
        pattern: d.explanation || d.detection_type,
        confidence: d.confidence * 100
      })))
    } catch (err) {
      console.error('Failed to load detections:', err)
      setError('Failed to load detections for review.')
    }
    setIsLoading(false)
  }, [getToken, tenantId, filter])

  useEffect(() => {
    loadDetections()
  }, [loadDetections])

  const current = detections[currentIndex]
  const pending = detections.length - reviewed

  const handleLabel = useCallback(async (label: 'correct' | 'false_positive' | 'unclear' | 'skip') => {
    if (!current) return
    
    if (label !== 'skip') {
      setReviewed(r => r + 1)
    }
    
    const feedbackMap = {
      correct: 'Marked as correct',
      false_positive: 'Marked as false positive',
      unclear: 'Marked as unclear',
      skip: 'Skipped'
    }
    setShowFeedback(feedbackMap[label])
    
    setTimeout(() => {
      setShowFeedback(null)
      if (currentIndex < detections.length - 1) {
        setCurrentIndex(i => i + 1)
      }
    }, 1000)
  }, [current, currentIndex, detections.length])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      
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
          <div className="h-8 w-64 bg-slate-700 rounded mb-6" />
          <div className="h-64 bg-slate-700 rounded-xl" />
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
          <p className="text-slate-400 mb-4">{error}</p>
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
          <p className="text-slate-400">No detections pending review.</p>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Detection Review Queue</h1>
            <p className="text-slate-400 text-sm mt-1">
              {reviewed} reviewed today - {pending} pending
            </p>
          </div>
          <div className="flex items-center gap-3">
            <select 
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white"
            >
              <option value="all">All Types</option>
              <option value="infinite_loop">Infinite Loop</option>
              <option value="state_corruption">State Corruption</option>
              <option value="persona_drift">Persona Drift</option>
              <option value="deadlock">Deadlock</option>
            </select>
            <Button variant="ghost" leftIcon={<Filter size={16} />}>
              High Confidence
            </Button>
          </div>
        </div>

        <div className="bg-slate-800 rounded-lg p-4 mb-6 border border-slate-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-slate-400 text-sm">Session Progress</span>
            <span className="text-white font-medium">{reviewed}/{detections.length}</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-2">
            <div 
              className="bg-emerald-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${(reviewed / detections.length) * 100}%` }}
            />
          </div>
        </div>

        {current && (
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  Detection #{current.id.slice(-6)} - {current.type.replace('_', ' ')}
                </h2>
                <p className="text-slate-400 text-sm mt-1">
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
                <span className="text-slate-400 text-sm">
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

            <div className="bg-slate-700/50 rounded-lg p-4 mb-4">
              <p className="text-slate-300 mb-2">
                <strong>Pattern:</strong> {current.pattern}
              </p>
              <p className="text-slate-300">
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

            {showFeedback && (
              <div className="bg-slate-700 rounded-lg p-3 mb-4 text-center">
                <span className="text-white">{showFeedback}</span>
                <span className="text-slate-400 text-sm ml-2">Auto-advancing...</span>
              </div>
            )}

            <div className="border-t border-slate-700 pt-4">
              <p className="text-slate-400 text-sm mb-3">Was this detection correct?</p>
              <div className="flex items-center gap-3 flex-wrap">
                <Button 
                  variant="success" 
                  onClick={() => handleLabel('correct')}
                  leftIcon={<CheckCircle2 size={16} />}
                >
                  Correct <kbd className="ml-2 text-xs opacity-60 bg-emerald-700 px-1 rounded">C</kbd>
                </Button>
                <Button 
                  variant="danger" 
                  onClick={() => handleLabel('false_positive')}
                  leftIcon={<XCircle size={16} />}
                >
                  False Positive <kbd className="ml-2 text-xs opacity-60 bg-red-700 px-1 rounded">F</kbd>
                </Button>
                <Button 
                  variant="secondary" 
                  onClick={() => handleLabel('unclear')}
                  leftIcon={<HelpCircle size={16} />}
                >
                  Unclear <kbd className="ml-2 text-xs opacity-60 bg-slate-600 px-1 rounded">U</kbd>
                </Button>
                <Button 
                  variant="ghost" 
                  onClick={() => handleLabel('skip')}
                  leftIcon={<SkipForward size={16} />}
                >
                  Skip <kbd className="ml-2 text-xs opacity-60 bg-slate-600 px-1 rounded">S</kbd>
                </Button>
              </div>
            </div>
          </div>
        )}

        <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
          <p className="text-slate-400 text-sm">
            <strong>Keyboard shortcuts:</strong>{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">C</kbd> Correct{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">F</kbd> False Positive{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">U</kbd> Unclear{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">S</kbd> Skip{' '}
            <kbd className="bg-slate-700 px-1.5 py-0.5 rounded text-xs">←/→</kbd> Navigate
          </p>
        </div>
      </div>
    </Layout>
  )
}
