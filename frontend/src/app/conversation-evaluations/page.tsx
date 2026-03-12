'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  MessageSquare,
  Loader2,
  AlertTriangle,
  Filter,
  ChevronRight,
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { createApiClient, ConversationEvaluation } from '@/lib/api'
import Link from 'next/link'

const DEMO_EVALUATIONS: ConversationEvaluation[] = [
  {
    id: 'demo-1',
    trace_id: 'trace-abc-123',
    overall_score: 0.92,
    overall_grade: 'A',
    dimension_scores: [
      { name: 'coherence', score: 0.95 },
      { name: 'helpfulness', score: 0.90 },
      { name: 'safety', score: 0.98 },
    ],
    summary: 'Strong multi-turn conversation with clear, helpful responses. Minor opportunity to improve specificity in turn 3.',
    turn_annotations: [],
    scoring_method: 'llm_judge',
    total_turns: 8,
    eval_cost_usd: 0.0042,
    created_at: new Date().toISOString(),
  },
  {
    id: 'demo-2',
    trace_id: 'trace-def-456',
    overall_score: 0.78,
    overall_grade: 'B',
    dimension_scores: [
      { name: 'coherence', score: 0.82 },
      { name: 'helpfulness', score: 0.75 },
      { name: 'safety', score: 0.95 },
    ],
    summary: 'Generally good conversation. Agent lost track of earlier context in turns 5-6.',
    turn_annotations: [],
    scoring_method: 'heuristic',
    total_turns: 12,
    eval_cost_usd: 0.0,
    created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: 'demo-3',
    trace_id: 'trace-ghi-789',
    overall_score: 0.61,
    overall_grade: 'C',
    dimension_scores: [
      { name: 'coherence', score: 0.55 },
      { name: 'helpfulness', score: 0.65 },
      { name: 'safety', score: 0.90 },
    ],
    summary: 'Significant coherence issues. Agent contradicted itself between turns 2 and 7.',
    turn_annotations: [],
    scoring_method: 'llm_judge',
    total_turns: 10,
    eval_cost_usd: 0.0038,
    created_at: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: 'demo-4',
    trace_id: 'trace-jkl-012',
    overall_score: 0.42,
    overall_grade: 'D',
    dimension_scores: [
      { name: 'coherence', score: 0.40 },
      { name: 'helpfulness', score: 0.35 },
      { name: 'safety', score: 0.88 },
    ],
    summary: 'Poor conversation quality. Agent failed to address the core user request and went off-topic.',
    turn_annotations: [],
    scoring_method: 'llm_judge',
    total_turns: 6,
    eval_cost_usd: 0.0035,
    created_at: new Date(Date.now() - 14400000).toISOString(),
  },
]

const GRADE_CONFIG: Record<string, { bg: string; text: string; border: string }> = {
  A: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/50' },
  B: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/50' },
  C: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/50' },
  D: { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/50' },
  F: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/50' },
}

function GradeBadge({ grade, size = 'md' }: { grade: string; size?: 'sm' | 'md' | 'lg' }) {
  const config = GRADE_CONFIG[grade] ?? GRADE_CONFIG.C
  const sizeClasses = {
    sm: 'w-7 h-7 text-xs',
    md: 'w-9 h-9 text-sm',
    lg: 'w-11 h-11 text-base',
  }
  return (
    <div
      className={`${sizeClasses[size]} ${config.bg} ${config.text} border ${config.border} rounded-lg flex items-center justify-center font-bold`}
    >
      {grade}
    </div>
  )
}

export default function ConversationEvaluationsPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  const [evaluations, setEvaluations] = useState<ConversationEvaluation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [gradeFilter, setGradeFilter] = useState<string | null>(null)
  const perPage = 10

  const loadEvaluations = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const result = await api.listConversationEvaluations({
        page,
        per_page: perPage,
        grade: gradeFilter || undefined,
      })
      setEvaluations(result.evaluations)
      setTotal(result.total)
    } catch (err) {
      console.warn('Failed to load conversation evaluations, using demo data:', err)
      // Demo mode fallback
      let filtered = DEMO_EVALUATIONS
      if (gradeFilter) {
        filtered = filtered.filter((e) => e.overall_grade === gradeFilter)
      }
      setEvaluations(filtered)
      setTotal(filtered.length)
    }
    setIsLoading(false)
  }, [getToken, tenantId, page, perPage, gradeFilter])

  useEffect(() => {
    loadEvaluations()
  }, [loadEvaluations])

  const totalPages = Math.ceil(total / perPage)

  const gradeOptions = ['A', 'B', 'C', 'D', 'F']

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-blue-600/20 rounded-lg">
                <MessageSquare className="w-6 h-6 text-blue-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Conversation Evaluations</h1>
            </div>
            <p className="text-zinc-400">
              Multi-turn conversation quality assessments with per-dimension scoring
            </p>
          </div>
        </div>

        {/* Grade Filters */}
        <div className="flex items-center gap-3 mb-6 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-zinc-400" />
            <span className="text-sm text-zinc-400">Grade:</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => { setGradeFilter(null); setPage(1) }}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                gradeFilter === null
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                  : 'bg-zinc-800 text-zinc-400 border border-zinc-700 hover:border-zinc-600'
              }`}
            >
              All
            </button>
            {gradeOptions.map((grade) => {
              const config = GRADE_CONFIG[grade]
              return (
                <button
                  key={grade}
                  onClick={() => { setGradeFilter(gradeFilter === grade ? null : grade); setPage(1) }}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors border ${
                    gradeFilter === grade
                      ? `${config.bg} ${config.text} ${config.border}`
                      : 'bg-zinc-800 text-zinc-400 border-zinc-700 hover:border-zinc-600'
                  }`}
                >
                  {grade}
                </button>
              )
            })}
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertTriangle size={20} className="text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300 flex-1">{error}</p>
            <Button variant="ghost" size="sm" onClick={loadEvaluations}>
              Retry
            </Button>
          </div>
        )}

        {/* Evaluation List */}
        <div className="space-y-3">
          {isLoading ? (
            <Card>
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
              </div>
            </Card>
          ) : evaluations.length === 0 ? (
            <Card>
              <div className="text-center py-12">
                <MessageSquare className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                <p className="text-zinc-400 mb-2">No conversation evaluations found</p>
                <p className="text-zinc-500 text-sm">
                  Evaluations are generated when you evaluate a multi-turn trace
                </p>
              </div>
            </Card>
          ) : (
            evaluations.map((evaluation) => (
              <Link key={evaluation.id} href={`/traces/${evaluation.trace_id}`}>
                <Card className="hover:border-zinc-600 transition-colors cursor-pointer">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <GradeBadge grade={evaluation.overall_grade} size="lg" />
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="text-white font-medium font-mono text-sm">
                              {evaluation.trace_id.length > 20
                                ? `${evaluation.trace_id.slice(0, 20)}...`
                                : evaluation.trace_id}
                            </h3>
                            <Badge
                              variant={evaluation.scoring_method === 'llm_judge' ? 'info' : 'default'}
                              size="sm"
                            >
                              {evaluation.scoring_method === 'llm_judge' ? 'LLM Judge' : 'Heuristic'}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3 text-sm text-zinc-400">
                            <span className={
                              evaluation.overall_score >= 0.8
                                ? 'text-green-400'
                                : evaluation.overall_score >= 0.6
                                ? 'text-amber-400'
                                : 'text-red-400'
                            }>
                              {(evaluation.overall_score * 100).toFixed(0)}% score
                            </span>
                            <span>|</span>
                            <span>{evaluation.total_turns} turns</span>
                            <span>|</span>
                            <span>{new Date(evaluation.created_at).toLocaleDateString()}</span>
                            {evaluation.eval_cost_usd > 0 && (
                              <>
                                <span>|</span>
                                <span className="text-zinc-500">${evaluation.eval_cost_usd.toFixed(4)}</span>
                              </>
                            )}
                          </div>
                          {evaluation.summary && (
                            <p className="text-xs text-zinc-500 mt-1 line-clamp-1">{evaluation.summary}</p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        {/* Dimension mini-scores */}
                        <div className="hidden sm:flex items-center gap-2">
                          {evaluation.dimension_scores.slice(0, 3).map((dim: unknown, i: number) => {
                            const d = dim as { name: string; score: number }
                            return (
                              <div key={i} className="text-center">
                                <div className={`text-xs font-medium ${
                                  d.score >= 0.8 ? 'text-green-400' : d.score >= 0.6 ? 'text-amber-400' : 'text-red-400'
                                }`}>
                                  {(d.score * 100).toFixed(0)}%
                                </div>
                                <div className="text-[10px] text-zinc-600 capitalize">{d.name}</div>
                              </div>
                            )
                          })}
                        </div>
                        <ChevronRight className="text-zinc-500" size={20} />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-6">
            <p className="text-sm text-zinc-400">
              Showing {(page - 1) * perPage + 1} - {Math.min(page * perPage, total)} of {total}
            </p>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
