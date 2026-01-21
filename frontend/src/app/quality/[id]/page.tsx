'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import {
  Star, ArrowLeft, Loader2, AlertCircle, AlertTriangle, Info, Clock,
  CheckCircle, Bot, GitBranch
} from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { QualityGradeBadge, getScoreColor, getGradeColor } from '@/components/quality/QualityGradeBadge'
import { createApiClient, QualityAssessment, QualityDimensionScore, AgentQualityScore, QualityImprovement } from '@/lib/api'
import Link from 'next/link'
import { useParams } from 'next/navigation'

type TabType = 'summary' | 'agents' | 'orchestration' | 'improvements'

const severityConfig = {
  critical: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-500/20', label: 'Critical' },
  high: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/20', label: 'High' },
  medium: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-500/20', label: 'Medium' },
  low: { icon: Info, color: 'text-slate-400', bg: 'bg-slate-500/20', label: 'Low' },
  info: { icon: Info, color: 'text-blue-400', bg: 'bg-blue-500/20', label: 'Info' },
}

const effortColors = {
  low: 'text-green-400',
  medium: 'text-amber-400',
  high: 'text-red-400',
}

function DimensionBar({ dimension }: { dimension: QualityDimensionScore }) {
  const scorePercent = Math.round(dimension.score * 100)
  const barColor = scorePercent >= 80 ? 'bg-green-500' : scorePercent >= 60 ? 'bg-amber-500' : 'bg-red-500'

  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-slate-300 capitalize">
          {dimension.dimension.replace(/_/g, ' ')}
        </span>
        <span className={`text-sm font-medium ${getScoreColor(dimension.score)}`}>
          {scorePercent}%
        </span>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${barColor} transition-all duration-500`}
          style={{ width: `${scorePercent}%` }}
        />
      </div>
      {dimension.issues.length > 0 && (
        <div className="mt-1">
          {dimension.issues.slice(0, 2).map((issue, i) => (
            <p key={i} className="text-xs text-slate-500 truncate">{issue}</p>
          ))}
        </div>
      )}
    </div>
  )
}

function AgentScoreCard({ agent }: { agent: AgentQualityScore }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card className="mb-4">
      <CardContent className="p-4">
        <div
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <Bot size={18} className="text-blue-400" />
            </div>
            <div>
              <h4 className="text-white font-medium">{agent.agent_name}</h4>
              <p className="text-sm text-slate-500">{agent.agent_type}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className={`text-lg font-bold ${getScoreColor(agent.overall_score)}`}>
                {Math.round(agent.overall_score * 100)}%
              </div>
              <div className="text-xs text-slate-500">{agent.issues_count} issues</div>
            </div>
            <QualityGradeBadge grade={agent.grade} size="md" />
          </div>
        </div>

        {expanded && (
          <div className="mt-4 pt-4 border-t border-slate-700">
            <h5 className="text-sm font-medium text-slate-300 mb-3">Dimension Scores</h5>
            {agent.dimensions.map((dim, i) => (
              <DimensionBar key={i} dimension={dim} />
            ))}

            {agent.critical_issues.length > 0 && (
              <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <div className="flex items-center gap-2 text-red-400 mb-2">
                  <AlertCircle size={14} />
                  <span className="text-sm font-medium">Critical Issues</span>
                </div>
                <ul className="text-sm text-red-400/80 space-y-1">
                  {agent.critical_issues.map((issue, i) => (
                    <li key={i}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ImprovementCard({ improvement }: { improvement: QualityImprovement }) {
  const [expanded, setExpanded] = useState(false)
  const config = severityConfig[improvement.severity] || severityConfig.info
  const Icon = config.icon

  return (
    <Card className="mb-3">
      <CardContent className="p-4">
        <div
          className="flex items-start gap-3 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <div className={`p-2 rounded-lg ${config.bg}`}>
            <Icon size={16} className={config.color} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="text-white font-medium">{improvement.title}</h4>
              <Badge
                variant={
                  improvement.severity === 'critical' ? 'error' :
                  improvement.severity === 'high' ? 'warning' : 'default'
                }
              >
                {improvement.severity}
              </Badge>
            </div>
            <p className="text-sm text-slate-400">{improvement.description}</p>

            <div className="flex items-center gap-4 mt-2">
              <span className="text-xs text-slate-500">{improvement.category}</span>
              <span className="text-xs text-slate-500">
                {improvement.target_type}: {improvement.target_id}
              </span>
              <span className={`text-xs flex items-center gap-1 ${effortColors[improvement.effort]}`}>
                <Clock size={10} />
                {improvement.effort} effort
              </span>
            </div>
          </div>
        </div>

        {expanded && (
          <div className="mt-4 pt-4 border-t border-slate-700 space-y-3">
            {improvement.rationale && (
              <div>
                <h5 className="text-xs font-medium text-slate-500 uppercase mb-1">Rationale</h5>
                <p className="text-sm text-slate-300">{improvement.rationale}</p>
              </div>
            )}
            {improvement.suggested_change && (
              <div>
                <h5 className="text-xs font-medium text-slate-500 uppercase mb-1">Suggested Change</h5>
                <p className="text-sm text-slate-300">{improvement.suggested_change}</p>
              </div>
            )}
            {improvement.code_example && (
              <div>
                <h5 className="text-xs font-medium text-slate-500 uppercase mb-1">Code Example</h5>
                <pre className="text-sm text-slate-400 bg-slate-900 p-3 rounded-lg overflow-x-auto">
                  {improvement.code_example}
                </pre>
              </div>
            )}
            {improvement.estimated_impact && (
              <div>
                <h5 className="text-xs font-medium text-slate-500 uppercase mb-1">Estimated Impact</h5>
                <p className="text-sm text-green-400">{improvement.estimated_impact}</p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function QualityDetailPage() {
  const params = useParams()
  const assessmentId = params.id as string
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [assessment, setAssessment] = useState<QualityAssessment | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabType>('summary')

  const loadAssessment = useCallback(async () => {
    setIsLoading(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const result = await api.getQualityAssessment(assessmentId)
      setAssessment(result)
    } catch (err) {
      console.error('Failed to load assessment:', err)
      setAssessment(null)
    }
    setIsLoading(false)
  }, [getToken, tenantId, assessmentId])

  useEffect(() => {
    loadAssessment()
  }, [loadAssessment])

  const tabs: { id: TabType; label: string }[] = [
    { id: 'summary', label: 'Summary' },
    { id: 'agents', label: 'Agent Scores' },
    { id: 'orchestration', label: 'Orchestration' },
    { id: 'improvements', label: 'Improvements' },
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
          <Link href="/quality" className="flex items-center gap-2 text-slate-400 hover:text-white mb-6">
            <ArrowLeft size={18} />
            Back to Quality Assessments
          </Link>
          <Card>
            <div className="text-center py-12">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <p className="text-slate-400">Assessment not found</p>
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
        <Link href="/quality" className="flex items-center gap-2 text-slate-400 hover:text-white mb-6">
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
              <p className="text-slate-400">
                Assessed {new Date(assessment.assessed_at).toLocaleString()}
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className={`text-4xl font-bold ${getScoreColor(assessment.overall_score)}`}>
              {Math.round(assessment.overall_score * 100)}%
            </div>
            <div className="text-sm text-slate-500">Overall Score</div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-slate-800 rounded-lg p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-slate-700 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {tab.label}
              {tab.id === 'improvements' && assessment.improvements.length > 0 && (
                <span className="ml-2 px-1.5 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded">
                  {assessment.improvements.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'summary' && (
          <div className="grid lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Score Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-slate-800 rounded-lg">
                    <div className="flex items-center gap-3">
                      <Bot size={18} className="text-blue-400" />
                      <span className="text-slate-300">Agent Quality (60%)</span>
                    </div>
                    <span className={`font-bold ${getScoreColor(assessment.agent_quality_score)}`}>
                      {Math.round(assessment.agent_quality_score * 100)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-slate-800 rounded-lg">
                    <div className="flex items-center gap-3">
                      <GitBranch size={18} className="text-purple-400" />
                      <span className="text-slate-300">Orchestration Quality (40%)</span>
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
                  <div className="p-3 bg-slate-800 rounded-lg">
                    <div className="text-2xl font-bold text-red-400">{criticalCount}</div>
                    <div className="text-sm text-slate-400">Critical</div>
                  </div>
                  <div className="p-3 bg-slate-800 rounded-lg">
                    <div className="text-2xl font-bold text-orange-400">{highCount}</div>
                    <div className="text-sm text-slate-400">High</div>
                  </div>
                  <div className="p-3 bg-slate-800 rounded-lg">
                    <div className="text-2xl font-bold text-white">{assessment.total_issues}</div>
                    <div className="text-sm text-slate-400">Total Issues</div>
                  </div>
                  <div className="p-3 bg-slate-800 rounded-lg">
                    <div className="text-2xl font-bold text-blue-400">{assessment.agent_scores.length}</div>
                    <div className="text-sm text-slate-400">Agents</div>
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
                      <li key={i} className="flex items-start gap-2 text-slate-300">
                        <CheckCircle size={16} className="text-green-400 mt-0.5 flex-shrink-0" />
                        {finding}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {activeTab === 'agents' && (
          <div>
            {assessment.agent_scores.length === 0 ? (
              <Card>
                <div className="text-center py-12">
                  <Bot className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                  <p className="text-slate-400">No agent scores available</p>
                </div>
              </Card>
            ) : (
              assessment.agent_scores.map((agent, i) => (
                <AgentScoreCard key={i} agent={agent} />
              ))
            )}
          </div>
        )}

        {activeTab === 'orchestration' && (
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
                  <div className="text-sm text-slate-400">
                    {assessment.orchestration_score.issues_count} issues found
                  </div>
                </div>
              </div>

              <h4 className="text-sm font-medium text-slate-300 mb-4">Dimension Scores</h4>
              {assessment.orchestration_score.dimensions.map((dim, i) => (
                <DimensionBar key={i} dimension={dim} />
              ))}
            </CardContent>
          </Card>
        )}

        {activeTab === 'improvements' && (
          <div>
            {assessment.improvements.length === 0 ? (
              <Card>
                <div className="text-center py-12">
                  <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
                  <p className="text-green-400 font-medium mb-2">No improvements needed!</p>
                  <p className="text-slate-500 text-sm">
                    This workflow meets all quality standards
                  </p>
                </div>
              </Card>
            ) : (
              <>
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
              </>
            )}
          </div>
        )}
      </div>
    </Layout>
  )
}
