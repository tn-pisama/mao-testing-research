'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Sparkles,
  Loader2,
  AlertTriangle,
  Trash2,
  Play,
  Plus,
  CheckCircle,
  XCircle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { createApiClient, CustomScorer, ScorerRunSummary, ScorerResult } from '@/lib/api'

const DEMO_SCORERS: CustomScorer[] = [
  {
    id: 'demo-1',
    name: 'Source Citation Quality',
    description: 'Checks whether the agent properly cites sources when making factual claims',
    prompt_template: 'Evaluate whether the agent output includes proper source citations...',
    scoring_criteria: [{ name: 'citation_present', weight: 0.5 }, { name: 'citation_accurate', weight: 0.5 }],
    model_key: 'claude-sonnet',
    is_active: true,
    created_at: new Date().toISOString(),
  },
  {
    id: 'demo-2',
    name: 'Tone Consistency',
    description: 'Verifies the agent maintains a professional and consistent tone throughout the conversation',
    prompt_template: 'Evaluate whether the agent maintains consistent professional tone...',
    scoring_criteria: [{ name: 'professional', weight: 0.4 }, { name: 'consistent', weight: 0.6 }],
    model_key: 'claude-sonnet',
    is_active: true,
    created_at: new Date(Date.now() - 86400000).toISOString(),
  },
]

function VerdictBadge({ verdict }: { verdict: string }) {
  const config: Record<string, { variant: 'success' | 'warning' | 'error'; icon: React.ElementType }> = {
    pass: { variant: 'success', icon: CheckCircle },
    warn: { variant: 'warning', icon: AlertCircle },
    fail: { variant: 'error', icon: XCircle },
  }
  const c = config[verdict.toLowerCase()] ?? config.warn
  const Icon = c.icon
  return (
    <Badge variant={c.variant} size="sm">
      <Icon size={12} className="mr-1" />
      {verdict.toUpperCase()}
    </Badge>
  )
}

export default function ScorersPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  const [scorers, setScorers] = useState<CustomScorer[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Create scorer state
  const [description, setDescription] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Run results state
  const [runningScorerId, setRunningScorerId] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, ScorerRunSummary>>({})
  const [expandedScorer, setExpandedScorer] = useState<string | null>(null)

  const loadScorers = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const data = await api.listScorers()
      setScorers(data)
    } catch (err) {
      console.warn('Failed to load scorers, using demo data:', err)
      setScorers(DEMO_SCORERS)
    }
    setIsLoading(false)
  }, [getToken, tenantId])

  useEffect(() => {
    loadScorers()
  }, [loadScorers])

  const handleCreate = async () => {
    if (!description.trim()) return
    setIsCreating(true)
    setCreateError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const scorer = await api.createScorer(description.trim())
      setScorers((prev) => [scorer, ...prev])
      setDescription('')
    } catch (err) {
      console.warn('Failed to create scorer:', err)
      setCreateError((err as Error).message || 'Failed to create scorer. Please try again.')
    }
    setIsCreating(false)
  }

  const handleRun = async (scorerId: string) => {
    setRunningScorerId(scorerId)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const summary = await api.runScorer(scorerId, { latest_n: 10 })
      setResults((prev) => ({ ...prev, [scorerId]: summary }))
      setExpandedScorer(scorerId)
    } catch (err) {
      console.warn('Failed to run scorer:', err)
      setError(`Failed to run scorer: ${(err as Error).message || 'Unknown error'}`)
    }
    setRunningScorerId(null)
  }

  const handleDelete = async (scorerId: string) => {
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      await api.deleteScorer(scorerId)
      setScorers((prev) => prev.filter((s) => s.id !== scorerId))
      setResults((prev) => {
        const next = { ...prev }
        delete next[scorerId]
        return next
      })
    } catch (err) {
      console.warn('Failed to delete scorer:', err)
      setError(`Failed to delete scorer: ${(err as Error).message || 'Unknown error'}`)
    }
  }

  return (
    <Layout>
      <div className="p-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-violet-600/20 rounded-lg">
            <Sparkles className="w-6 h-6 text-violet-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Custom Scorers</h1>
        </div>
        <p className="text-zinc-400 mb-6">
          Describe a quality concern in natural language and Pisama will generate a scorer to evaluate your traces.
        </p>

        {/* Create Scorer */}
        <Card className="mb-6" padding="lg">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Plus size={18} className="text-violet-400" />
              <CardTitle className="text-base">Create New Scorer</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what you want to check, e.g.: 'Verify that the agent always asks for confirmation before executing destructive actions'"
              className="w-full h-28 bg-zinc-950 border border-zinc-700 rounded-lg p-3 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/30 resize-none"
            />
            {createError && (
              <div className="mt-2 flex items-center gap-2 text-sm text-red-400">
                <AlertTriangle size={14} />
                <span>{createError}</span>
              </div>
            )}
            <div className="mt-3 flex items-center justify-between">
              <p className="text-xs text-zinc-500">
                Pisama will auto-generate the scoring prompt, rubric, and criteria from your description.
              </p>
              <Button
                onClick={handleCreate}
                disabled={!description.trim() || isCreating}
                isLoading={isCreating}
                leftIcon={<Sparkles size={16} />}
              >
                Generate Scorer
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertTriangle size={20} className="text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300 flex-1">{error}</p>
            <Button variant="ghost" size="sm" onClick={() => setError(null)}>
              Dismiss
            </Button>
          </div>
        )}

        {/* Scorer List */}
        <div className="space-y-4">
          {isLoading ? (
            <Card>
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-violet-400 animate-spin" />
              </div>
            </Card>
          ) : scorers.length === 0 ? (
            <Card>
              <div className="text-center py-12">
                <Sparkles className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                <p className="text-zinc-400 mb-2">No custom scorers yet</p>
                <p className="text-zinc-500 text-sm">
                  Describe a quality concern above to create your first scorer
                </p>
              </div>
            </Card>
          ) : (
            scorers.map((scorer) => {
              const summary = results[scorer.id]
              const isExpanded = expandedScorer === scorer.id
              const isRunning = runningScorerId === scorer.id

              return (
                <Card key={scorer.id} padding="none">
                  <div className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="text-white font-medium truncate">{scorer.name}</h3>
                          {scorer.is_active ? (
                            <Badge variant="success" size="sm">Active</Badge>
                          ) : (
                            <Badge variant="default" size="sm">Inactive</Badge>
                          )}
                        </div>
                        <p className="text-sm text-zinc-400 line-clamp-2">{scorer.description}</p>
                        <div className="flex items-center gap-3 mt-2 text-xs text-zinc-500">
                          <span>Model: {scorer.model_key}</span>
                          <span>|</span>
                          <span>Created: {new Date(scorer.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleRun(scorer.id)}
                          disabled={isRunning}
                          isLoading={isRunning}
                          leftIcon={<Play size={14} />}
                        >
                          Run
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(scorer.id)}
                          className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                        >
                          <Trash2 size={14} />
                        </Button>
                      </div>
                    </div>

                    {/* Summary Stats (after run) */}
                    {summary && (
                      <div className="mt-4 pt-4 border-t border-zinc-800">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-4">
                            <div className="text-center">
                              <div className="text-lg font-semibold text-white">{summary.traces_scored}</div>
                              <div className="text-xs text-zinc-500">Scored</div>
                            </div>
                            <div className="text-center">
                              <div className="text-lg font-semibold text-white">{summary.avg_score.toFixed(2)}</div>
                              <div className="text-xs text-zinc-500">Avg Score</div>
                            </div>
                            <div className="text-center">
                              <div className="text-lg font-semibold text-green-400">{summary.pass_count}</div>
                              <div className="text-xs text-zinc-500">Pass</div>
                            </div>
                            <div className="text-center">
                              <div className="text-lg font-semibold text-amber-400">{summary.warn_count}</div>
                              <div className="text-xs text-zinc-500">Warn</div>
                            </div>
                            <div className="text-center">
                              <div className="text-lg font-semibold text-red-400">{summary.fail_count}</div>
                              <div className="text-xs text-zinc-500">Fail</div>
                            </div>
                            <div className="text-center">
                              <div className="text-lg font-semibold text-zinc-300">${summary.total_cost_usd.toFixed(4)}</div>
                              <div className="text-xs text-zinc-500">Cost</div>
                            </div>
                          </div>
                          <button
                            onClick={() => setExpandedScorer(isExpanded ? null : scorer.id)}
                            className="flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
                          >
                            {isExpanded ? 'Hide' : 'Show'} Results
                            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>
                        </div>

                        {/* Expanded Results */}
                        {isExpanded && summary.results.length > 0 && (
                          <div className="space-y-3 mt-3">
                            {summary.results.map((result: ScorerResult) => (
                              <div
                                key={result.id}
                                className="bg-zinc-950 border border-zinc-800 rounded-lg p-3"
                              >
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-3">
                                    <VerdictBadge verdict={result.verdict} />
                                    <span className="text-sm text-zinc-300 font-mono">
                                      {result.trace_id.slice(0, 8)}...
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-3 text-xs text-zinc-500">
                                    <span>Score: {result.score.toFixed(2)}</span>
                                    <span>Confidence: {(result.confidence * 100).toFixed(0)}%</span>
                                    <span>${result.cost_usd.toFixed(4)}</span>
                                  </div>
                                </div>
                                <p className="text-sm text-zinc-400">{result.reasoning}</p>
                                {result.suggestions.length > 0 && (
                                  <div className="mt-2">
                                    <p className="text-xs text-zinc-500 mb-1">Suggestions:</p>
                                    <ul className="list-disc list-inside text-xs text-zinc-400 space-y-0.5">
                                      {result.suggestions.map((s: unknown, i: number) => (
                                        <li key={i}>{typeof s === 'string' ? s : (s as Record<string, unknown>)?.text as string || JSON.stringify(s)}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </Card>
              )
            })
          )}
        </div>
      </div>
    </Layout>
  )
}
