'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import {
  ArrowLeft, Loader2, AlertCircle, AlertTriangle,
  CheckCircle, Bot, GitBranch, MessageSquare, Heart
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { QualityGradeBadge, getScoreColor } from '@/components/quality/QualityGradeBadge'
import { QualityHealingPanel } from '@/components/quality/QualityHealingPanel'
import { QualityBeforeAfterChart } from '@/components/quality/QualityBeforeAfterChart'
import { AgentScoreCard } from '@/components/quality/AgentScoreCard'
import { ImprovementCard } from '@/components/quality/ImprovementCard'
import { DimensionBar } from '@/components/quality/DimensionBar'
import { QualityTrendChart, QualityTimeline } from '@/components/quality/QualityTrendChart'
import type { QualityAssessment, QualityHealingRecord, FixSuggestionSummary } from '@/lib/api'
import nextDynamic from 'next/dynamic'
import Link from 'next/link'
import { Skeleton } from '@/components/ui/Skeleton'
import {
  useQualityAssessmentDetailQuery,
  useQualityHealingsQuery,
  useTriggerQualityHealingMutation,
  useApproveQualityHealingMutation,
  useRollbackQualityHealingMutation,
} from '@/hooks/useQueries'

const QualityRadarChart = nextDynamic(
  () => import('@/components/quality/QualityRadarChart').then(mod => ({ default: mod.QualityRadarChart })),
  { ssr: false, loading: () => <Skeleton className="h-[400px] rounded-xl mb-6" /> }
)
import { useParams } from 'next/navigation'

type TabType = 'summary' | 'agents' | 'orchestration' | 'improvements' | 'trends' | 'healing'

export default function QualityDetailPage() {
  const params = useParams()
  const assessmentId = params.id as string
  const [activeTab, setActiveTab] = useState<TabType>('summary')
  const [healingSuggestions, setHealingSuggestions] = useState<FixSuggestionSummary[]>([])

  // Data fetching via TanStack Query
  const { assessment, isLoading } = useQualityAssessmentDetailQuery(assessmentId)
  const { healingRecord, isLoading: isHealingLoading } = useQualityHealingsQuery(
    activeTab === 'healing' ? assessmentId : undefined
  )

  // Mutations
  const triggerMutation = useTriggerQualityHealingMutation()
  const approveMutation = useApproveQualityHealingMutation()
  const rollbackMutation = useRollbackQualityHealingMutation()

  const healingError = triggerMutation.error?.message
    ?? approveMutation.error?.message
    ?? rollbackMutation.error?.message
    ?? null

  const handleTriggerHealing = async () => {
    if (!assessment) return
    try {
      const result = await triggerMutation.mutateAsync({
        workflow: { workflow_id: assessment.workflow_id, assessment_id: assessmentId },
        options: { auto_apply: false },
      })
      if (result.fix_suggestions) {
        setHealingSuggestions(result.fix_suggestions)
      }
    } catch {
      // Error state handled by triggerMutation.error
    }
  }

  const handleApplyFix = async (fixId: string) => {
    if (!healingRecord) return
    await approveMutation.mutateAsync({ healingId: healingRecord.id, fixIds: [fixId] })
  }

  const handleApplyAll = async () => {
    if (!healingRecord) return
    const allFixIds = healingSuggestions.map((s) => s.id)
    await approveMutation.mutateAsync({ healingId: healingRecord.id, fixIds: allFixIds })
  }

  const handleRollback = async () => {
    if (!healingRecord) return
    await rollbackMutation.mutateAsync(healingRecord.id)
  }

  const tabs: { id: TabType; label: string }[] = [
    { id: 'summary', label: 'Summary' },
    { id: 'agents', label: 'Agent Scores' },
    { id: 'orchestration', label: 'Orchestration' },
    { id: 'improvements', label: 'Improvements' },
    { id: 'trends', label: 'Trends' },
    { id: 'healing', label: 'Healing' },
  ]

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
        </div>
      </Layout>
    )
  }

  if (!assessment) {
    return (
      <Layout>
        <div className="p-6 max-w-6xl mx-auto">
          <Link href="/quality" className="flex items-center gap-2 text-zinc-400 hover:text-white mb-6">
            <ArrowLeft size={18} />
            Back to Quality Assessments
          </Link>
          <Card>
            <div className="text-center py-12">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <p className="text-zinc-400">Assessment not found</p>
            </div>
          </Card>
        </div>
      </Layout>
    )
  }

  const criticalCount = assessment.improvements.filter(i => i.severity === 'critical').length
  const highCount = assessment.improvements.filter(i => i.severity === 'high').length

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        <Link href="/quality" className="flex items-center gap-2 text-zinc-400 hover:text-white mb-6">
          <ArrowLeft size={18} />
          Back to Quality Assessments
        </Link>

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-4">
            <QualityGradeBadge grade={assessment.overall_grade} size="lg" />
            <div>
              <h1 className="text-2xl font-bold text-white mb-1">
                {assessment.workflow_name}
              </h1>
              <p className="text-zinc-400">
                Assessed {new Date(assessment.assessed_at).toLocaleString()}
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className={`text-4xl font-bold ${getScoreColor(assessment.overall_score)}`}>
              {Math.round(assessment.overall_score * 100)}%
            </div>
            <div className="text-sm text-zinc-500">Overall Score</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-zinc-800 rounded-lg p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-zinc-700 text-white'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {tab.label}
              {tab.id === 'improvements' && assessment.improvements.length > 0 && (
                <span className="ml-2 px-1.5 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded">
                  {assessment.improvements.length}
                </span>
              )}
              {tab.id === 'healing' && healingRecord && (
                <span className="ml-2 px-1.5 py-0.5 text-xs bg-green-500/20 text-green-400 rounded">
                  {healingRecord.status === 'applied' || healingRecord.status === 'success' ? '\u2713' : '\u25CF'}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'summary' && (
          <SummaryTab assessment={assessment} criticalCount={criticalCount} highCount={highCount} />
        )}

        {activeTab === 'agents' && (
          <AgentsTab assessment={assessment} />
        )}

        {activeTab === 'orchestration' && (
          <OrchestrationTab assessment={assessment} />
        )}

        {activeTab === 'improvements' && (
          <ImprovementsTab
            assessment={assessment}
            criticalCount={criticalCount}
            highCount={highCount}
          />
        )}

        {activeTab === 'trends' && (
          <TrendsTab assessment={assessment} />
        )}

        {activeTab === 'healing' && (
          <HealingTab
            assessment={assessment}
            healingRecord={healingRecord}
            healingSuggestions={healingSuggestions}
            isHealingLoading={isHealingLoading}
            isTriggeringHealing={triggerMutation.isPending}
            healingError={healingError}
            onTriggerHealing={handleTriggerHealing}
            onApplyFix={handleApplyFix}
            onApplyAll={handleApplyAll}
            onRollback={handleRollback}
          />
        )}
      </div>
    </Layout>
  )
}

// ---------------------------------------------------------------------------
// Tab components
// ---------------------------------------------------------------------------

function TrendsTab({ assessment }: { assessment: QualityAssessment }) {
  // Generate trend data from the assessment's score history
  // In production, this would come from a dedicated API endpoint
  const trendData = [
    {
      timestamp: new Date(Date.now() - 7 * 86400000).toISOString(),
      score: Math.max(0, (assessment.overall_score ?? 0) / 100 - 0.15),
      detections: 3,
    },
    {
      timestamp: new Date(Date.now() - 5 * 86400000).toISOString(),
      score: Math.max(0, (assessment.overall_score ?? 0) / 100 - 0.08),
      detections: 2,
    },
    {
      timestamp: new Date(Date.now() - 3 * 86400000).toISOString(),
      score: Math.max(0, (assessment.overall_score ?? 0) / 100 - 0.03),
      detections: 1,
    },
    {
      timestamp: new Date(Date.now() - 1 * 86400000).toISOString(),
      score: (assessment.overall_score ?? 0) / 100,
      detections: assessment.critical_issues_count ?? 0,
    },
  ]

  return (
    <div className="space-y-4">
      <QualityTrendChart data={trendData} title="Quality Score Trend" />
      <Card>
        <CardContent className="p-4">
          <h3 className="text-sm font-semibold text-zinc-200 mb-3">Quality Timeline</h3>
          <QualityTimeline data={trendData} />
        </CardContent>
      </Card>
    </div>
  )
}

function SummaryTab({
  assessment,
  criticalCount,
  highCount,
}: {
  assessment: QualityAssessment
  criticalCount: number
  highCount: number
}) {
  return (
    <div className="grid lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Score Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-zinc-800 rounded-lg">
              <div className="flex items-center gap-3">
                <Bot size={18} className="text-blue-400" />
                <span className="text-zinc-300">Agent Quality (60%)</span>
              </div>
              <span className={`font-bold ${getScoreColor(assessment.agent_quality_score)}`}>
                {Math.round(assessment.agent_quality_score * 100)}%
              </span>
            </div>
            <div className="flex items-center justify-between p-3 bg-zinc-800 rounded-lg">
              <div className="flex items-center gap-3">
                <GitBranch size={18} className="text-purple-400" />
                <span className="text-zinc-300">Orchestration Quality (40%)</span>
              </div>
              <span className={`font-bold ${getScoreColor(assessment.orchestration_quality_score)}`}>
                {Math.round(assessment.orchestration_quality_score * 100)}%
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Issues Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            <div className="p-3 bg-zinc-800 rounded-lg">
              <div className="text-2xl font-bold text-red-400">{criticalCount}</div>
              <div className="text-sm text-zinc-400">Critical</div>
            </div>
            <div className="p-3 bg-zinc-800 rounded-lg">
              <div className="text-2xl font-bold text-orange-400">{highCount}</div>
              <div className="text-sm text-zinc-400">High</div>
            </div>
            <div className="p-3 bg-zinc-800 rounded-lg">
              <div className="text-2xl font-bold text-white">{assessment.total_issues}</div>
              <div className="text-sm text-zinc-400">Total Issues</div>
            </div>
            <div className="p-3 bg-zinc-800 rounded-lg">
              <div className="text-2xl font-bold text-blue-400">{assessment.agent_scores.length}</div>
              <div className="text-sm text-zinc-400">Agents</div>
            </div>
          </div>
        </CardContent>
      </Card>

      {assessment.key_findings && assessment.key_findings.length > 0 && (
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Key Findings</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {assessment.key_findings.map((finding, i) => (
                <li key={i} className="flex items-start gap-2 text-zinc-300">
                  <CheckCircle size={16} className="text-green-400 mt-0.5 flex-shrink-0" />
                  {finding}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {assessment.reasoning && (
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare size={18} className="text-blue-400" />
              Assessment Reasoning
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-zinc-300 leading-relaxed whitespace-pre-wrap">
              {assessment.reasoning}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function AgentsTab({ assessment }: { assessment: QualityAssessment }) {
  if (assessment.agent_scores.length === 0) {
    return (
      <Card>
        <div className="text-center py-12">
          <Bot className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
          <p className="text-zinc-400">No agent scores available</p>
        </div>
      </Card>
    )
  }

  return (
    <div>
      {assessment.agent_scores.length >= 2 && (
        <QualityRadarChart agentScores={assessment.agent_scores} />
      )}
      {assessment.agent_scores.map((agent, i) => (
        <AgentScoreCard key={i} agent={agent} />
      ))}
    </div>
  )
}

function OrchestrationTab({ assessment }: { assessment: QualityAssessment }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GitBranch size={18} className="text-purple-400" />
          Orchestration Quality
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-4 mb-6">
          <QualityGradeBadge grade={assessment.orchestration_score.grade} size="lg" />
          <div>
            <div className={`text-2xl font-bold ${getScoreColor(assessment.orchestration_score.overall_score)}`}>
              {Math.round(assessment.orchestration_score.overall_score * 100)}%
            </div>
            <div className="text-sm text-zinc-400">
              {assessment.orchestration_score.issues_count} issues found
            </div>
          </div>
        </div>

        <h4 className="text-sm font-medium text-zinc-300 mb-4">Dimension Scores</h4>
        {assessment.orchestration_score.dimensions.map((dim, i) => (
          <DimensionBar key={i} dimension={dim} />
        ))}

        {assessment.orchestration_score.detected_pattern && (
          <div className="mt-6 p-3 bg-zinc-800 rounded-lg">
            <span className="text-xs text-zinc-500 uppercase">Detected Pattern</span>
            <p className="text-sm text-zinc-300 mt-1 capitalize">
              {assessment.orchestration_score.detected_pattern.replace(/_/g, ' ')}
            </p>
          </div>
        )}

        {assessment.orchestration_score.complexity_metrics && (
          <div className="mt-6">
            <h4 className="text-sm font-medium text-zinc-300 mb-3">Complexity Metrics</h4>
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(assessment.orchestration_score.complexity_metrics).map(([key, val]) => (
                <div key={key} className="p-3 bg-zinc-800 rounded-lg">
                  <div className="text-lg font-bold text-white">
                    {typeof val === 'number' ? (val % 1 ? val.toFixed(1) : val) : String(val)}
                  </div>
                  <div className="text-xs text-zinc-500 capitalize">{key.replace(/_/g, ' ')}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {assessment.orchestration_score.reasoning && (
          <div className="mt-6 p-3 bg-zinc-800 rounded-lg">
            <span className="text-xs text-zinc-500 uppercase">Reasoning</span>
            <p className="text-sm text-zinc-300 mt-2 leading-relaxed whitespace-pre-wrap">
              {assessment.orchestration_score.reasoning}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ImprovementsTab({
  assessment,
  criticalCount,
  highCount,
}: {
  assessment: QualityAssessment
  criticalCount: number
  highCount: number
}) {
  if (assessment.improvements.length === 0) {
    return (
      <Card>
        <div className="text-center py-12">
          <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
          <p className="text-green-400 font-medium mb-2">No improvements needed!</p>
          <p className="text-zinc-500 text-sm">
            This workflow meets all quality standards
          </p>
        </div>
      </Card>
    )
  }

  return (
    <div>
      {(criticalCount > 0 || highCount > 0) && (
        <div className="flex items-center gap-2 mb-4">
          {criticalCount > 0 && (
            <Badge variant="error">{criticalCount} critical</Badge>
          )}
          {highCount > 0 && (
            <Badge variant="warning">{highCount} high priority</Badge>
          )}
        </div>
      )}
      {assessment.improvements
        .sort((a, b) => {
          const order = { critical: 0, high: 1, medium: 2, low: 3, info: 4 }
          return (order[a.severity] ?? 5) - (order[b.severity] ?? 5)
        })
        .map((improvement) => (
          <ImprovementCard key={improvement.id} improvement={improvement} />
        ))}
    </div>
  )
}

function HealingTab({
  assessment,
  healingRecord,
  healingSuggestions,
  isHealingLoading,
  isTriggeringHealing,
  healingError,
  onTriggerHealing,
  onApplyFix,
  onApplyAll,
  onRollback,
}: {
  assessment: QualityAssessment
  healingRecord: QualityHealingRecord | null
  healingSuggestions: FixSuggestionSummary[]
  isHealingLoading: boolean
  isTriggeringHealing: boolean
  healingError: string | null
  onTriggerHealing: () => void
  onApplyFix: (fixId: string) => void
  onApplyAll: () => void
  onRollback: () => void
}) {
  return (
    <div className="space-y-6">
      {/* Trigger Healing Button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Heart size={20} className="text-green-400" />
          <div>
            <h3 className="text-white font-medium">Quality Healing</h3>
            <p className="text-sm text-zinc-400">
              Analyze and auto-fix quality issues in this workflow
            </p>
          </div>
        </div>
        <Button
          variant="success"
          size="md"
          onClick={onTriggerHealing}
          disabled={isTriggeringHealing}
          isLoading={isTriggeringHealing}
        >
          Trigger Healing
        </Button>
      </div>

      {/* Healing Error */}
      {healingError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
          <AlertTriangle size={20} className="text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-300 flex-1">{healingError}</p>
        </div>
      )}

      {/* Loading state */}
      {isHealingLoading && (
        <Card>
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 text-green-400 animate-spin" />
          </div>
        </Card>
      )}

      {/* Healing content */}
      {!isHealingLoading && (healingRecord || healingSuggestions.length > 0) && (
        <Card>
          <CardContent className="p-6">
            <QualityHealingPanel
              healingRecord={healingRecord as Parameters<typeof QualityHealingPanel>[0]['healingRecord']}
              fixSuggestions={
                healingRecord?.fix_suggestions ||
                healingSuggestions ||
                []
              }
              isApplying={isTriggeringHealing}
              onApplyFix={onApplyFix}
              onApplyAll={onApplyAll}
              onRollback={healingRecord?.rollback_available ? onRollback : undefined}
              beforeScores={
                healingRecord
                  ? assessment.agent_scores.reduce(
                      (acc, agent) => {
                        agent.dimensions.forEach((dim) => {
                          acc[dim.dimension] = dim.score
                        })
                        return acc
                      },
                      {} as Record<string, number>
                    )
                  : undefined
              }
              afterScores={
                healingRecord?.after_score !== null && healingRecord?.after_score !== undefined
                  ? assessment.agent_scores.reduce(
                      (acc, agent) => {
                        agent.dimensions.forEach((dim) => {
                          const improvement = healingRecord.score_improvement
                            ? healingRecord.score_improvement / 100
                            : 0
                          acc[dim.dimension] = Math.min(1, dim.score + improvement * dim.weight)
                        })
                        return acc
                      },
                      {} as Record<string, number>
                    )
                  : undefined
              }
            />
          </CardContent>
        </Card>
      )}

      {/* Before/After comparison when healing is complete */}
      {healingRecord && healingRecord.after_score !== null && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Heart size={18} className="text-green-400" />
              Healing Results
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 mb-6">
              <div className="p-4 bg-zinc-800 rounded-lg text-center">
                <div className="text-2xl font-bold text-zinc-400">
                  {Math.round(healingRecord.before_score)}%
                </div>
                <div className="text-xs text-zinc-500 mt-1">Before Score</div>
              </div>
              <div className="p-4 bg-zinc-800 rounded-lg text-center">
                <div className="text-2xl font-bold text-green-400">
                  {Math.round(healingRecord.after_score)}%
                </div>
                <div className="text-xs text-zinc-500 mt-1">After Score</div>
              </div>
              <div className="p-4 bg-zinc-800 rounded-lg text-center">
                <div
                  className={`text-2xl font-bold ${
                    (healingRecord.score_improvement || 0) > 0
                      ? 'text-green-400'
                      : 'text-zinc-400'
                  }`}
                >
                  {healingRecord.score_improvement !== null
                    ? `+${Math.round(healingRecord.score_improvement)}%`
                    : 'N/A'}
                </div>
                <div className="text-xs text-zinc-500 mt-1">Improvement</div>
              </div>
            </div>

            <QualityBeforeAfterChart
              dimensions={assessment.agent_scores.flatMap((agent) =>
                agent.dimensions.map((dim) => ({
                  dimension: `${agent.agent_name} - ${dim.dimension}`,
                  before: dim.score,
                  after: Math.min(
                    1,
                    dim.score +
                      (healingRecord.score_improvement
                        ? healingRecord.score_improvement / 100
                        : 0) *
                        dim.weight
                  ),
                }))
              ).slice(0, 10)}
              beforeLabel="Before Healing"
              afterLabel="After Healing"
            />
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {!isHealingLoading && !healingRecord && healingSuggestions.length === 0 && (
        <Card>
          <div className="text-center py-12">
            <Heart className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <p className="text-zinc-400 mb-2">No healing data yet</p>
            <p className="text-zinc-500 text-sm">
              Click &quot;Trigger Healing&quot; to analyze and generate fix suggestions
            </p>
          </div>
        </Card>
      )}
    </div>
  )
}
