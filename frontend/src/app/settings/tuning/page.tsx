'use client'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { Button } from '@/components/ui/Button'
import {
  useFeedbackStatsQuery,
  useThresholdRecommendationsQuery,
  useUpdateThresholdsMutation,
  useResetThresholdsMutation,
} from '@/hooks/useQueries'
import {
  Sliders,
  Target,
  TrendingUp,
  AlertCircle,
  CheckCircle,
  RefreshCw,
  Info,
  WifiOff,
  RotateCcw,
} from 'lucide-react'

export default function ThresholdTuningPage() {
  const { data: stats, isLoading: statsLoading, isDemoMode } = useFeedbackStatsQuery()
  const { data: recommendations, isLoading: recsLoading } = useThresholdRecommendationsQuery()
  const loading = statsLoading || recsLoading
  const recs = recommendations ?? []
  const updateMutation = useUpdateThresholdsMutation()
  const resetMutation = useResetThresholdsMutation()

  const [applyingFramework, setApplyingFramework] = useState<string | null>(null)
  const [appliedFrameworks, setAppliedFrameworks] = useState<Set<string>>(new Set())
  const [applyError, setApplyError] = useState<string | null>(null)
  const [applyingAll, setApplyingAll] = useState(false)
  const [showResetConfirm, setShowResetConfirm] = useState(false)

  const handleApplyRecommendation = async (rec: any) => {
    setApplyingFramework(rec.framework)
    setApplyError(null)
    try {
      await updateMutation.mutateAsync({
        framework_thresholds: {
          [rec.framework]: {
            structural_threshold: rec.recommended_structural_threshold,
            semantic_threshold: rec.recommended_semantic_threshold,
          },
        },
      })
      setAppliedFrameworks(prev => new Set([...prev, rec.framework]))
    } catch (err) {
      console.error('Failed to apply recommendation:', err)
      setApplyError(`Failed to apply ${rec.framework} thresholds`)
    } finally {
      setApplyingFramework(null)
    }
  }

  const handleApplyAll = async () => {
    const pendingRecs = recs.filter(rec => {
      const structChange = rec.recommended_structural_threshold - rec.current_structural_threshold
      const semChange = rec.recommended_semantic_threshold - rec.current_semantic_threshold
      return (Math.abs(structChange) > 0.001 || Math.abs(semChange) > 0.001) && !appliedFrameworks.has(rec.framework)
    })
    if (pendingRecs.length === 0) return

    setApplyingAll(true)
    setApplyError(null)
    try {
      const frameworkThresholds: Record<string, { structural_threshold: number; semantic_threshold: number }> = {}
      for (const rec of pendingRecs) {
        frameworkThresholds[rec.framework] = {
          structural_threshold: rec.recommended_structural_threshold,
          semantic_threshold: rec.recommended_semantic_threshold,
        }
      }
      await updateMutation.mutateAsync({ framework_thresholds: frameworkThresholds })
      setAppliedFrameworks(prev => new Set([...prev, ...pendingRecs.map(r => r.framework)]))
    } catch (err) {
      console.error('Failed to apply all recommendations:', err)
      setApplyError('Failed to apply recommendations')
    } finally {
      setApplyingAll(false)
    }
  }

  const handleReset = async () => {
    setApplyError(null)
    try {
      await resetMutation.mutateAsync()
      setAppliedFrameworks(new Set())
      setShowResetConfirm(false)
    } catch (err) {
      console.error('Failed to reset thresholds:', err)
      setApplyError('Failed to reset thresholds')
    }
  }

  const pendingRecommendations = recs.filter(rec => {
    const structChange = rec.recommended_structural_threshold - rec.current_structural_threshold
    const semChange = rec.recommended_semantic_threshold - rec.current_semantic_threshold
    return (Math.abs(structChange) > 0.001 || Math.abs(semChange) > 0.001) && !appliedFrameworks.has(rec.framework)
  })

  if (loading) {
    return (
      <Layout>
        <div className="p-8 flex items-center justify-center min-h-[60vh]">
          <RefreshCw className="animate-spin text-zinc-400" size={32} />
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-8 max-w-7xl mx-auto">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-600/20 rounded-lg">
              <Sliders className="w-6 h-6 text-purple-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">Threshold Tuning</h1>
            {isDemoMode && (
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/30">
                <WifiOff size={14} className="text-amber-400" />
                <span className="text-xs font-medium text-amber-200">Demo Mode</span>
              </div>
            )}
          </div>
          <p className="text-zinc-400">
            Optimize detection accuracy based on user feedback. Adjust thresholds to reduce false positives and improve detection rates.
          </p>
        </div>

        {/* Overall Stats */}
        <div className="grid md:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Total Feedback"
            value={stats?.total_feedback || 0}
            icon={<Target size={20} />}
            color="slate"
          />
          <StatCard
            label="Precision"
            value={`${((stats?.precision || 0) * 100).toFixed(1)}%`}
            icon={<CheckCircle size={20} />}
            color="emerald"
            description="True positives / (TP + FP)"
          />
          <StatCard
            label="Recall"
            value={`${((stats?.recall || 0) * 100).toFixed(1)}%`}
            icon={<TrendingUp size={20} />}
            color="blue"
            description="True positives / (TP + FN)"
          />
          <StatCard
            label="F1 Score"
            value={`${((stats?.f1_score || 0) * 100).toFixed(1)}%`}
            icon={<Target size={20} />}
            color="purple"
            description="Harmonic mean of precision and recall"
          />
        </div>

        {/* Confusion Matrix */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          <div className="bg-zinc-800 rounded-lg p-6 border border-zinc-700">
            <h2 className="text-lg font-semibold text-white mb-4">Confusion Matrix</h2>
            <div className="grid grid-cols-2 gap-2 max-w-xs">
              <div className="bg-emerald-500/20 p-4 rounded-lg text-center border border-emerald-500/30">
                <div className="text-2xl font-bold text-emerald-400">{stats?.true_positives}</div>
                <div className="text-xs text-zinc-400">True Positives</div>
              </div>
              <div className="bg-red-500/20 p-4 rounded-lg text-center border border-red-500/30">
                <div className="text-2xl font-bold text-red-400">{stats?.false_positives}</div>
                <div className="text-xs text-zinc-400">False Positives</div>
              </div>
              <div className="bg-amber-500/20 p-4 rounded-lg text-center border border-amber-500/30">
                <div className="text-2xl font-bold text-amber-400">{stats?.false_negatives}</div>
                <div className="text-xs text-zinc-400">False Negatives</div>
              </div>
              <div className="bg-zinc-600/30 p-4 rounded-lg text-center border border-zinc-600/50">
                <div className="text-2xl font-bold text-zinc-300">{stats?.true_negatives}</div>
                <div className="text-xs text-zinc-400">True Negatives</div>
              </div>
            </div>
          </div>

          <div className="bg-zinc-800 rounded-lg p-6 border border-zinc-700">
            <h2 className="text-lg font-semibold text-white mb-4">Accuracy by Framework</h2>
            <div className="space-y-3">
              {Object.entries(stats?.by_framework || {}).map(([fw, data]: [string, any]) => {
                const accuracy = data.total > 0 ? (data.correct / data.total) * 100 : 0
                return (
                  <div key={fw} className="flex items-center gap-3">
                    <span className="text-zinc-300 w-24 text-sm">{fw}</span>
                    <div className="flex-1 bg-zinc-700 rounded-full h-2">
                      <div
                        className="bg-emerald-500 h-2 rounded-full transition-all"
                        style={{ width: `${accuracy}%` }}
                      />
                    </div>
                    <span className="text-sm text-zinc-400 w-16 text-right">{accuracy.toFixed(0)}%</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Error banner */}
        {applyError && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-3">
            <AlertCircle size={18} className="text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300 flex-1">{applyError}</p>
            <button onClick={() => setApplyError(null)} className="text-red-400 hover:text-red-300 text-sm">
              Dismiss
            </button>
          </div>
        )}

        {/* Threshold Recommendations */}
        <div className="bg-zinc-800 rounded-lg border border-zinc-700 overflow-hidden">
          <div className="p-4 border-b border-zinc-700 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">Threshold Recommendations</h2>
              <p className="text-sm text-zinc-400">Based on {stats?.total_feedback} feedback submissions</p>
            </div>
            {pendingRecommendations.length > 0 && (
              <Button
                size="sm"
                onClick={handleApplyAll}
                loading={applyingAll}
                disabled={applyingAll || isDemoMode}
              >
                Apply All ({pendingRecommendations.length})
              </Button>
            )}
          </div>
          <div className="divide-y divide-zinc-700">
            {recs.map((rec) => (
              <RecommendationRow
                key={rec.framework}
                recommendation={rec}
                onApply={() => handleApplyRecommendation(rec)}
                isApplying={applyingFramework === rec.framework}
                isApplied={appliedFrameworks.has(rec.framework)}
                isDemoMode={isDemoMode}
              />
            ))}
          </div>
          {recs.length === 0 && (
            <div className="p-8 text-center text-zinc-400">
              <Info size={32} className="mx-auto mb-2 opacity-50" />
              <p>Not enough feedback data to generate recommendations.</p>
              <p className="text-sm">Submit at least 10 feedback items per framework.</p>
            </div>
          )}
        </div>

        {/* Reset to defaults */}
        <div className="mt-6 flex items-center justify-end gap-3">
          {showResetConfirm ? (
            <div className="flex items-center gap-3 bg-zinc-800 border border-zinc-700 rounded-lg p-3">
              <span className="text-sm text-zinc-300">Reset all thresholds to factory defaults?</span>
              <Button size="sm" variant="danger" onClick={handleReset} loading={resetMutation.isPending} disabled={resetMutation.isPending}>
                Confirm Reset
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowResetConfirm(false)} disabled={resetMutation.isPending}>
                Cancel
              </Button>
            </div>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              leftIcon={<RotateCcw size={14} />}
              onClick={() => setShowResetConfirm(true)}
              disabled={isDemoMode}
            >
              Reset to Defaults
            </Button>
          )}
        </div>

        {/* By Method */}
        <div className="mt-8 bg-zinc-800 rounded-lg p-6 border border-zinc-700">
          <h2 className="text-lg font-semibold text-white mb-4">Accuracy by Detection Method</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {Object.entries(stats?.by_method || {}).map(([method, data]: [string, any]) => {
              const accuracy = data.total > 0 ? (data.correct / data.total) * 100 : 0
              const fpRate = data.total > 0 ? (data.incorrect / data.total) * 100 : 0
              return (
                <div key={method} className="bg-zinc-700/50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white font-medium capitalize">{method}</span>
                    <span className={`text-sm ${accuracy >= 80 ? 'text-emerald-400' : accuracy >= 60 ? 'text-amber-400' : 'text-red-400'}`}>
                      {accuracy.toFixed(0)}% accurate
                    </span>
                  </div>
                  <div className="text-sm text-zinc-400">
                    {data.total} samples • {data.incorrect} FP ({fpRate.toFixed(1)}%)
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </Layout>
  )
}

function StatCard({
  label,
  value,
  icon,
  color,
  description,
}: {
  label: string
  value: string | number
  icon: React.ReactNode
  color: 'slate' | 'emerald' | 'blue' | 'purple'
  description?: string
}) {
  const colorClasses = {
    slate: 'bg-zinc-600/20 text-zinc-400',
    emerald: 'bg-emerald-600/20 text-emerald-400',
    blue: 'bg-blue-600/20 text-blue-400',
    purple: 'bg-purple-600/20 text-purple-400',
  }

  return (
    <div className="bg-zinc-800 rounded-lg p-4 border border-zinc-700">
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded ${colorClasses[color]}`}>{icon}</div>
        <span className="text-zinc-400 text-sm">{label}</span>
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {description && (
        <div className="text-xs text-zinc-500 mt-1">{description}</div>
      )}
    </div>
  )
}

function RecommendationRow({
  recommendation,
  onApply,
  isApplying,
  isApplied,
  isDemoMode,
}: {
  recommendation: any
  onApply: () => void
  isApplying: boolean
  isApplied: boolean
  isDemoMode: boolean
}) {
  const structuralChange = recommendation.recommended_structural_threshold - recommendation.current_structural_threshold
  const semanticChange = recommendation.recommended_semantic_threshold - recommendation.current_semantic_threshold
  const hasChange = Math.abs(structuralChange) > 0.001 || Math.abs(semanticChange) > 0.001

  return (
    <div className="p-4 hover:bg-zinc-700/30 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div>
          <span className="text-white font-medium capitalize">{recommendation.framework}</span>
          <span className="text-zinc-500 text-sm ml-2">({recommendation.sample_size} samples)</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-16 bg-zinc-700 rounded-full h-1.5">
              <div
                className="bg-purple-500 h-1.5 rounded-full"
                style={{ width: `${recommendation.confidence * 100}%` }}
              />
            </div>
            <span className="text-xs text-zinc-400">{(recommendation.confidence * 100).toFixed(0)}% conf</span>
          </div>
          {hasChange && !isApplied && (
            <Button
              size="sm"
              onClick={onApply}
              loading={isApplying}
              disabled={isApplying || isDemoMode}
            >
              Apply
            </Button>
          )}
          {isApplied && (
            <span className="flex items-center gap-1 text-sm text-emerald-400">
              <CheckCircle size={14} />
              Applied
            </span>
          )}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4 mb-3">
        <ThresholdCard
          label="Structural"
          current={recommendation.current_structural_threshold}
          recommended={recommendation.recommended_structural_threshold}
          isApplied={isApplied}
        />
        <ThresholdCard
          label="Semantic"
          current={recommendation.current_semantic_threshold}
          recommended={recommendation.recommended_semantic_threshold}
          isApplied={isApplied}
        />
      </div>

      <div className="flex items-start gap-2 text-sm">
        {hasChange ? (
          <>
            <AlertCircle size={16} className="text-amber-400 mt-0.5 flex-shrink-0" />
            <span className="text-zinc-300">{recommendation.reasoning}</span>
          </>
        ) : (
          <>
            <CheckCircle size={16} className="text-emerald-400 mt-0.5 flex-shrink-0" />
            <span className="text-zinc-400">{recommendation.reasoning}</span>
          </>
        )}
      </div>
    </div>
  )
}

function ThresholdCard({
  label,
  current,
  recommended,
  isApplied,
}: {
  label: string
  current: number
  recommended: number
  isApplied?: boolean
}) {
  const change = recommended - current
  const hasChange = Math.abs(change) > 0.001

  return (
    <div className="bg-zinc-700/50 rounded-lg p-3">
      <div className="text-xs text-zinc-400 mb-1">{label} Threshold</div>
      <div className="flex items-center gap-2">
        <span className={isApplied && hasChange ? 'text-zinc-500 line-through' : 'text-zinc-300'}>
          {(current * 100).toFixed(0)}%
        </span>
        {hasChange && (
          <>
            <span className="text-zinc-500">&rarr;</span>
            <span className={isApplied ? 'text-emerald-400 font-medium' : change > 0 ? 'text-amber-400' : 'text-emerald-400'}>
              {(recommended * 100).toFixed(0)}%
            </span>
            <span className={`text-xs ${change > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
              ({change > 0 ? '+' : ''}{(change * 100).toFixed(1)}%)
            </span>
          </>
        )}
        {!hasChange && (
          <span className="text-xs text-zinc-500">(no change)</span>
        )}
      </div>
    </div>
  )
}
