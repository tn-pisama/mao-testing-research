'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Play, Pause, SkipForward, RotateCcw,
  GitCompare, Download, Upload, Clock,
  CheckCircle, XCircle, AlertCircle
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import { createApiClient, ReplayBundle, ReplayDiff } from '@/lib/api'

interface DisplayBundle {
  id: string
  name: string
  traceId: string
  createdAt: string
  eventCount: number
  duration: string
  status: 'ready' | 'replaying' | 'completed'
}

interface ReplayResultDisplay {
  step: number
  original: string
  replayed: string
  match: boolean
  similarity: number
}

const DEMO_BUNDLES: DisplayBundle[] = [
  {
    id: 'rb-001',
    name: 'Customer Support Flow',
    traceId: 'trace-abc123',
    createdAt: '2024-12-28',
    eventCount: 47,
    duration: '2m 34s',
    status: 'ready'
  },
  {
    id: 'rb-002',
    name: 'Code Review Agent',
    traceId: 'trace-def456',
    createdAt: '2024-12-27',
    eventCount: 23,
    duration: '1m 12s',
    status: 'completed'
  },
  {
    id: 'rb-003',
    name: 'Research Pipeline',
    traceId: 'trace-ghi789',
    createdAt: '2024-12-26',
    eventCount: 89,
    duration: '5m 45s',
    status: 'ready'
  },
]

const DEMO_RESULTS: ReplayResultDisplay[] = [
  { step: 1, original: 'Analyzed user query...', replayed: 'Analyzed user query...', match: true, similarity: 1.0 },
  { step: 2, original: 'Retrieved 5 documents from KB', replayed: 'Retrieved 5 documents from KB', match: true, similarity: 1.0 },
  { step: 3, original: 'Generated response with citations', replayed: 'Generated response with sources', match: false, similarity: 0.87 },
  { step: 4, original: 'Applied formatting rules', replayed: 'Applied formatting rules', match: true, similarity: 1.0 },
]

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}m ${remainingSeconds}s`
}

function mapBundleToDisplay(bundle: ReplayBundle): DisplayBundle {
  return {
    id: bundle.id,
    name: bundle.name,
    traceId: bundle.trace_id,
    createdAt: new Date(bundle.created_at).toLocaleDateString(),
    eventCount: bundle.event_count,
    duration: formatDuration(bundle.duration_ms),
    status: bundle.status as 'ready' | 'replaying' | 'completed'
  }
}

function mapDiffToResult(diff: ReplayDiff): ReplayResultDisplay {
  return {
    step: diff.step,
    original: diff.original,
    replayed: diff.replayed,
    match: diff.match,
    similarity: diff.similarity
  }
}

export default function ReplayPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [bundles, setBundles] = useState<DisplayBundle[]>([])
  const [replayResults, setReplayResults] = useState<ReplayResultDisplay[]>([])
  const [selectedBundle, setSelectedBundle] = useState<string | null>(null)
  const [isReplaying, setIsReplaying] = useState(false)
  const [replayMode, setReplayMode] = useState<'full' | 'partial' | 'whatif'>('full')
  const [showResults, setShowResults] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)
  const [overallSimilarity, setOverallSimilarity] = useState(0)

  const loadBundles = useCallback(async () => {
    setIsLoading(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const bundlesData = await api.getReplayBundles(20, 0)
      setBundles(bundlesData.map(mapBundleToDisplay))
      setIsDemoMode(false)
    } catch (err) {
      console.warn('API unavailable, using demo data:', err)
      setBundles(DEMO_BUNDLES)
      setIsDemoMode(true)
    }
    setIsLoading(false)
  }, [getToken, tenantId])

  useEffect(() => {
    loadBundles()
  }, [loadBundles])

  const startReplay = async () => {
    if (!selectedBundle) return
    setIsReplaying(true)

    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      // Start the replay
      await api.startReplay(selectedBundle, replayMode === 'full' ? 'deterministic' : replayMode)

      // Wait a moment then get comparison results
      await new Promise(resolve => setTimeout(resolve, 1500))

      // Get comparison results
      const comparison = await api.compareReplay(selectedBundle, { test: true })
      setReplayResults(comparison.diffs.map(mapDiffToResult))
      setOverallSimilarity(comparison.overall_similarity)
      setShowResults(true)
      setIsDemoMode(false)
    } catch (err) {
      console.warn('Replay API unavailable, using demo results:', err)
      // Fallback to demo results
      setTimeout(() => {
        setReplayResults(DEMO_RESULTS)
        setOverallSimilarity(0.968)
        setShowResults(true)
        setIsDemoMode(true)
      }, 1500)
    }

    setIsReplaying(false)
  }

  const matchingSteps = replayResults.filter(r => r.match).length
  const totalSteps = replayResults.length

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <RotateCcw className="text-purple-400" />
              Deterministic Replay
              {isDemoMode && (
                <span className="text-xs bg-amber-500/20 text-amber-400 px-2 py-1 rounded-full ml-2">
                  Demo Mode
                </span>
              )}
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Record and replay agent executions for debugging and testing
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" leftIcon={<Upload size={16} />}>
              Import Bundle
            </Button>
            <Button
              onClick={startReplay}
              disabled={!selectedBundle || isReplaying}
              loading={isReplaying}
              leftIcon={<Play size={16} />}
            >
              {isReplaying ? 'Replaying...' : 'Start Replay'}
            </Button>
          </div>
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4">Replay Bundles</h2>
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-400"></div>
                </div>
              ) : (
                <div className="space-y-2">
                  {bundles.map((bundle) => (
                    <button
                      key={bundle.id}
                      onClick={() => setSelectedBundle(bundle.id)}
                      className={`w-full p-4 rounded-lg border text-left transition-all ${
                        selectedBundle === bundle.id
                          ? 'border-primary-500 bg-primary-500/10'
                          : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-white font-medium">{bundle.name}</span>
                          <div className="flex items-center gap-4 mt-1">
                            <span className="text-slate-500 text-sm font-mono">{bundle.traceId}</span>
                            <span className="text-slate-500 text-sm">{bundle.createdAt}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-slate-400">
                            {bundle.eventCount} events
                          </span>
                          <span className="text-slate-400 flex items-center gap-1">
                            <Clock size={14} />
                            {bundle.duration}
                          </span>
                          <span className={`px-2 py-0.5 rounded-full text-xs ${
                            bundle.status === 'completed' ? 'bg-emerald-400/10 text-emerald-400' :
                            bundle.status === 'replaying' ? 'bg-amber-400/10 text-amber-400' :
                            'bg-slate-400/10 text-slate-400'
                          }`}>
                            {bundle.status}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4">Replay Mode</h2>
              <div className="space-y-2">
                {[
                  { id: 'full', name: 'Full Replay', desc: 'Replay entire trace' },
                  { id: 'partial', name: 'Partial Replay', desc: 'Replay from checkpoint' },
                  { id: 'whatif', name: 'What-If', desc: 'Modify inputs and compare' },
                ].map((mode) => (
                  <button
                    key={mode.id}
                    onClick={() => setReplayMode(mode.id as typeof replayMode)}
                    className={`w-full p-3 rounded-lg border text-left transition-all ${
                      replayMode === mode.id
                        ? 'border-purple-500 bg-purple-500/10'
                        : 'border-slate-600 bg-slate-700/50 hover:border-slate-500'
                    }`}
                  >
                    <span className="text-white text-sm">{mode.name}</span>
                    <p className="text-slate-500 text-xs mt-0.5">{mode.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
              <h2 className="text-lg font-semibold text-white mb-4">Statistics</h2>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Bundles</span>
                  <span className="text-white font-mono">{bundles.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Avg Match Rate</span>
                  <span className="text-emerald-400 font-mono">
                    {showResults ? `${(overallSimilarity * 100).toFixed(1)}%` : '94.2%'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Completed</span>
                  <span className="text-white font-mono">
                    {bundles.filter(b => b.status === 'completed').length}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {showResults && (
          <div className="bg-slate-800 rounded-xl p-6 border border-slate-700">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <GitCompare className="text-purple-400" />
                Replay Results
              </h2>
              <Button variant="ghost" size="sm" leftIcon={<Download size={14} />}>
                Export Diff
              </Button>
            </div>

            <div className="space-y-2">
              {replayResults.map((result) => (
                <div
                  key={result.step}
                  className={`p-4 rounded-lg border ${
                    result.match
                      ? 'border-slate-600 bg-slate-700/30'
                      : 'border-amber-500/30 bg-amber-500/5'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      {result.match ? (
                        <CheckCircle className="text-emerald-400" size={18} />
                      ) : (
                        <AlertCircle className="text-amber-400" size={18} />
                      )}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-slate-400 text-sm">Step {result.step}</span>
                        <span className={`text-sm font-mono ${
                          result.similarity >= 0.95 ? 'text-emerald-400' :
                          result.similarity >= 0.8 ? 'text-amber-400' : 'text-red-400'
                        }`}>
                          {(result.similarity * 100).toFixed(0)}% match
                        </span>
                      </div>
                      <div className="grid md:grid-cols-2 gap-4">
                        <div>
                          <span className="text-slate-500 text-xs block mb-1">Original</span>
                          <p className="text-slate-300 text-sm bg-slate-800 p-2 rounded">
                            {result.original}
                          </p>
                        </div>
                        <div>
                          <span className="text-slate-500 text-xs block mb-1">Replayed</span>
                          <p className={`text-sm p-2 rounded ${
                            result.match ? 'text-slate-300 bg-slate-800' : 'text-amber-300 bg-amber-900/20'
                          }`}>
                            {result.replayed}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 p-4 bg-slate-700/50 rounded-lg flex items-center justify-between">
              <div>
                <span className="text-white font-medium">Overall Match Rate</span>
                <p className="text-slate-400 text-sm">{matchingSteps} of {totalSteps} steps matched exactly</p>
              </div>
              <span className="text-2xl font-bold text-emerald-400">
                {(overallSimilarity * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
