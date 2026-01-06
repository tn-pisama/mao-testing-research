'use client'

import { useState, useEffect } from 'react'
import { Layout } from '@/components/common/Layout'
import {
  Sliders,
  Target,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckCircle,
  RefreshCw,
  Info,
} from 'lucide-react'

interface FeedbackStats {
  total_feedback: number
  true_positives: number
  false_positives: number
  false_negatives: number
  true_negatives: number
  precision: number
  recall: number
  f1_score: number
  by_framework: Record<string, { total: number; correct: number; incorrect: number }>
  by_detection_type: Record<string, { total: number; correct: number; incorrect: number }>
  by_method: Record<string, { total: number; correct: number; incorrect: number }>
}

interface ThresholdRecommendation {
  framework: string
  current_structural_threshold: number
  current_semantic_threshold: number
  recommended_structural_threshold: number
  recommended_semantic_threshold: number
  confidence: number
  sample_size: number
  reasoning: string
}

// Demo data - replace with API calls in production
const DEMO_STATS: FeedbackStats = {
  total_feedback: 127,
  true_positives: 89,
  false_positives: 18,
  false_negatives: 12,
  true_negatives: 8,
  precision: 0.832,
  recall: 0.881,
  f1_score: 0.856,
  by_framework: {
    langgraph: { total: 45, correct: 38, incorrect: 7 },
    autogen: { total: 32, correct: 26, incorrect: 6 },
    crewai: { total: 28, correct: 24, incorrect: 4 },
    langchain: { total: 22, correct: 20, incorrect: 2 },
  },
  by_detection_type: {
    infinite_loop: { total: 67, correct: 58, incorrect: 9 },
    state_corruption: { total: 31, correct: 26, incorrect: 5 },
    persona_drift: { total: 29, correct: 24, incorrect: 5 },
  },
  by_method: {
    structural: { total: 52, correct: 47, incorrect: 5 },
    semantic: { total: 43, correct: 35, incorrect: 8 },
    hash: { total: 32, correct: 26, incorrect: 6 },
  },
}

const DEMO_RECOMMENDATIONS: ThresholdRecommendation[] = [
  {
    framework: 'autogen',
    current_structural_threshold: 0.90,
    current_semantic_threshold: 0.80,
    recommended_structural_threshold: 0.91,
    recommended_semantic_threshold: 0.81,
    confidence: 0.64,
    sample_size: 32,
    reasoning: 'Moderate false positive rate (18.8%). Recommend slight threshold increase.',
  },
  {
    framework: 'langgraph',
    current_structural_threshold: 0.92,
    current_semantic_threshold: 0.88,
    recommended_structural_threshold: 0.92,
    recommended_semantic_threshold: 0.88,
    confidence: 0.90,
    sample_size: 45,
    reasoning: 'False positive rate (15.6%) is acceptable. No changes recommended.',
  },
  {
    framework: 'crewai',
    current_structural_threshold: 0.88,
    current_semantic_threshold: 0.82,
    recommended_structural_threshold: 0.86,
    recommended_semantic_threshold: 0.80,
    confidence: 0.56,
    sample_size: 28,
    reasoning: 'Very low false positive rate (14.3%). Could decrease thresholds to catch more issues.',
  },
]

export default function ThresholdTuningPage() {
  const [stats, setStats] = useState<FeedbackStats | null>(null)
  const [recommendations, setRecommendations] = useState<ThresholdRecommendation[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedFramework, setSelectedFramework] = useState<string | null>(null)

  useEffect(() => {
    // In production, fetch from API
    // For now, use demo data
    setTimeout(() => {
      setStats(DEMO_STATS)
      setRecommendations(DEMO_RECOMMENDATIONS)
      setLoading(false)
    }, 500)
  }, [])

  if (loading) {
    return (
      <Layout>
        <div className="p-8 flex items-center justify-center min-h-[60vh]">
          <RefreshCw className="animate-spin text-slate-400" size={32} />
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
          </div>
          <p className="text-slate-400">
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
          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-lg font-semibold text-white mb-4">Confusion Matrix</h2>
            <div className="grid grid-cols-2 gap-2 max-w-xs">
              <div className="bg-emerald-500/20 p-4 rounded-lg text-center border border-emerald-500/30">
                <div className="text-2xl font-bold text-emerald-400">{stats?.true_positives}</div>
                <div className="text-xs text-slate-400">True Positives</div>
              </div>
              <div className="bg-red-500/20 p-4 rounded-lg text-center border border-red-500/30">
                <div className="text-2xl font-bold text-red-400">{stats?.false_positives}</div>
                <div className="text-xs text-slate-400">False Positives</div>
              </div>
              <div className="bg-amber-500/20 p-4 rounded-lg text-center border border-amber-500/30">
                <div className="text-2xl font-bold text-amber-400">{stats?.false_negatives}</div>
                <div className="text-xs text-slate-400">False Negatives</div>
              </div>
              <div className="bg-slate-600/30 p-4 rounded-lg text-center border border-slate-600/50">
                <div className="text-2xl font-bold text-slate-300">{stats?.true_negatives}</div>
                <div className="text-xs text-slate-400">True Negatives</div>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 className="text-lg font-semibold text-white mb-4">Accuracy by Framework</h2>
            <div className="space-y-3">
              {Object.entries(stats?.by_framework || {}).map(([fw, data]) => {
                const accuracy = data.total > 0 ? (data.correct / data.total) * 100 : 0
                return (
                  <div key={fw} className="flex items-center gap-3">
                    <span className="text-slate-300 w-24 text-sm">{fw}</span>
                    <div className="flex-1 bg-slate-700 rounded-full h-2">
                      <div
                        className="bg-emerald-500 h-2 rounded-full transition-all"
                        style={{ width: `${accuracy}%` }}
                      />
                    </div>
                    <span className="text-sm text-slate-400 w-16 text-right">{accuracy.toFixed(0)}%</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Threshold Recommendations */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
          <div className="p-4 border-b border-slate-700">
            <h2 className="text-lg font-semibold text-white">Threshold Recommendations</h2>
            <p className="text-sm text-slate-400">Based on {stats?.total_feedback} feedback submissions</p>
          </div>
          <div className="divide-y divide-slate-700">
            {recommendations.map((rec) => (
              <RecommendationRow key={rec.framework} recommendation={rec} />
            ))}
          </div>
          {recommendations.length === 0 && (
            <div className="p-8 text-center text-slate-400">
              <Info size={32} className="mx-auto mb-2 opacity-50" />
              <p>Not enough feedback data to generate recommendations.</p>
              <p className="text-sm">Submit at least 10 feedback items per framework.</p>
            </div>
          )}
        </div>

        {/* By Method */}
        <div className="mt-8 bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Accuracy by Detection Method</h2>
          <div className="grid md:grid-cols-3 gap-4">
            {Object.entries(stats?.by_method || {}).map(([method, data]) => {
              const accuracy = data.total > 0 ? (data.correct / data.total) * 100 : 0
              const fpRate = data.total > 0 ? (data.incorrect / data.total) * 100 : 0
              return (
                <div key={method} className="bg-slate-700/50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white font-medium capitalize">{method}</span>
                    <span className={`text-sm ${accuracy >= 80 ? 'text-emerald-400' : accuracy >= 60 ? 'text-amber-400' : 'text-red-400'}`}>
                      {accuracy.toFixed(0)}% accurate
                    </span>
                  </div>
                  <div className="text-sm text-slate-400">
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
    slate: 'bg-slate-600/20 text-slate-400',
    emerald: 'bg-emerald-600/20 text-emerald-400',
    blue: 'bg-blue-600/20 text-blue-400',
    purple: 'bg-purple-600/20 text-purple-400',
  }

  return (
    <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded ${colorClasses[color]}`}>{icon}</div>
        <span className="text-slate-400 text-sm">{label}</span>
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      {description && (
        <div className="text-xs text-slate-500 mt-1">{description}</div>
      )}
    </div>
  )
}

function RecommendationRow({ recommendation }: { recommendation: ThresholdRecommendation }) {
  const structuralChange = recommendation.recommended_structural_threshold - recommendation.current_structural_threshold
  const semanticChange = recommendation.recommended_semantic_threshold - recommendation.current_semantic_threshold
  const hasChange = Math.abs(structuralChange) > 0.001 || Math.abs(semanticChange) > 0.001

  return (
    <div className="p-4 hover:bg-slate-700/30 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div>
          <span className="text-white font-medium capitalize">{recommendation.framework}</span>
          <span className="text-slate-500 text-sm ml-2">({recommendation.sample_size} samples)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-16 bg-slate-700 rounded-full h-1.5">
            <div
              className="bg-purple-500 h-1.5 rounded-full"
              style={{ width: `${recommendation.confidence * 100}%` }}
            />
          </div>
          <span className="text-xs text-slate-400">{(recommendation.confidence * 100).toFixed(0)}% conf</span>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4 mb-3">
        <ThresholdCard
          label="Structural"
          current={recommendation.current_structural_threshold}
          recommended={recommendation.recommended_structural_threshold}
        />
        <ThresholdCard
          label="Semantic"
          current={recommendation.current_semantic_threshold}
          recommended={recommendation.recommended_semantic_threshold}
        />
      </div>

      <div className="flex items-start gap-2 text-sm">
        {hasChange ? (
          <>
            <AlertCircle size={16} className="text-amber-400 mt-0.5 flex-shrink-0" />
            <span className="text-slate-300">{recommendation.reasoning}</span>
          </>
        ) : (
          <>
            <CheckCircle size={16} className="text-emerald-400 mt-0.5 flex-shrink-0" />
            <span className="text-slate-400">{recommendation.reasoning}</span>
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
}: {
  label: string
  current: number
  recommended: number
}) {
  const change = recommended - current
  const hasChange = Math.abs(change) > 0.001

  return (
    <div className="bg-slate-700/50 rounded-lg p-3">
      <div className="text-xs text-slate-400 mb-1">{label} Threshold</div>
      <div className="flex items-center gap-2">
        <span className="text-slate-300">{(current * 100).toFixed(0)}%</span>
        {hasChange && (
          <>
            <span className="text-slate-500">→</span>
            <span className={change > 0 ? 'text-amber-400' : 'text-emerald-400'}>
              {(recommended * 100).toFixed(0)}%
            </span>
            <span className={`text-xs ${change > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
              ({change > 0 ? '+' : ''}{(change * 100).toFixed(1)}%)
            </span>
          </>
        )}
        {!hasChange && (
          <span className="text-xs text-slate-500">(no change)</span>
        )}
      </div>
    </div>
  )
}
