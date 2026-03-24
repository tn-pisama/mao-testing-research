'use client'

import { useState } from 'react'
import { Layout } from '@/components/common/Layout'
import { Card } from '@/components/ui/Card'
import { Skeleton } from '@/components/ui/Skeleton'
import { Bot, TrendingUp, AlertTriangle, Activity, ChevronDown, ChevronRight, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient } from '@/lib/api'
import API_URL from '@/lib/api-url'

interface AgentQuality {
  agent_id: string
  agent_name: string
  agent_type: string
  avg_score: number
  grade: string
  total_runs: number
  issues_count: number
  min_score: number
  max_score: number
}

interface AgentRun {
  assessment_id: string
  workflow_name: string
  score: number
  grade: string
  issues_count: number
  improvements: any[]
  created_at: string
}

interface AgentDetail {
  agent_id: string
  avg_score: number
  grade: string
  total_runs: number
  runs: AgentRun[]
  score_explanation: string
}

function gradeColor(grade: string) {
  switch (grade) {
    case 'Healthy': return 'text-green-400 bg-green-500/10 border-green-500/20'
    case 'Degraded': return 'text-amber-400 bg-amber-500/10 border-amber-500/20'
    case 'At Risk': return 'text-orange-400 bg-orange-500/10 border-orange-500/20'
    case 'Critical': return 'text-red-400 bg-red-500/10 border-red-500/20'
    default: return 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20'
  }
}

function scoreColor(score: number) {
  if (score >= 90) return 'text-green-400'
  if (score >= 70) return 'text-amber-400'
  if (score >= 50) return 'text-orange-400'
  return 'text-red-400'
}

function AgentDetailPanel({ agentId }: { agentId: string }) {
  const [detail, setDetail] = useState<AgentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  useState(() => {
    async function load() {
      try {
        const token = await getToken()
        if (!token || !tenantId || tenantId === 'default') return
        const res = await fetch(
          `${API_URL}/tenants/${tenantId}/dashboard/agent-quality/${encodeURIComponent(agentId)}`,
          { headers: { Authorization: `Bearer ${token}` } }
        )
        if (res.ok) {
          setDetail(await res.json())
        } else {
          setError('Failed to load agent details')
        }
      } catch {
        setError('Failed to load agent details')
      } finally {
        setLoading(false)
      }
    }
    load()
  })

  if (loading) {
    return (
      <div className="px-4 py-6 bg-zinc-900/50">
        <Skeleton className="h-4 w-64 mb-3" />
        <Skeleton className="h-20 w-full rounded-lg" />
      </div>
    )
  }

  if (error || !detail) {
    return (
      <div className="px-4 py-4 bg-zinc-900/50 text-sm text-zinc-500">
        {error || 'No details available'}
      </div>
    )
  }

  return (
    <div className="px-4 py-4 bg-zinc-900/50 border-t border-zinc-800">
      {/* Score explanation */}
      <div className="flex items-start gap-2 mb-4 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700">
        <Info size={14} className="text-blue-400 mt-0.5 shrink-0" />
        <p className="text-xs text-zinc-400">{detail.score_explanation}</p>
      </div>

      {/* Run history */}
      <h4 className="text-sm font-medium text-zinc-300 mb-2">
        Recent runs ({detail.total_runs} total)
      </h4>
      <div className="space-y-1.5 max-h-64 overflow-y-auto">
        {detail.runs.map((run) => (
          <div
            key={run.assessment_id}
            className="flex items-center justify-between px-3 py-2 rounded-lg bg-zinc-800/30 hover:bg-zinc-800/60 transition-colors"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className={cn('text-xs font-mono font-medium w-10', scoreColor(run.score))}>
                {run.score}%
              </span>
              <span className="text-sm text-zinc-300 truncate">{run.workflow_name}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {run.issues_count > 0 && (
                <span className="text-xs text-amber-400">{run.issues_count} issue{run.issues_count !== 1 ? 's' : ''}</span>
              )}
              <span className={cn(
                'text-xs px-1.5 py-0.5 rounded border',
                gradeColor(run.grade)
              )}>
                {run.grade}
              </span>
              <span className="text-xs text-zinc-600">
                {run.created_at ? new Date(run.created_at).toLocaleDateString() : ''}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function AgentsClient({ initialAgents }: { initialAgents: AgentQuality[] }) {
  const agents = initialAgents
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)

  const avgScore = agents.length > 0
    ? Math.round(agents.reduce((s, a) => s + a.avg_score, 0) / agents.length)
    : 0
  const totalRuns = agents.reduce((s, a) => s + a.total_runs, 0)
  const totalIssues = agents.reduce((s, a) => s + a.issues_count, 0)

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-blue-600/20 rounded-lg">
            <Bot className="w-6 h-6 text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">Agents</h1>
        </div>
        <p className="text-zinc-400 mb-6">
          Individual agent performance across all workflow runs. Click an agent to see details.
        </p>

        {/* Summary stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
            <div className="flex items-center gap-2 mb-1">
              <Bot size={16} className="text-blue-400" />
              <span className="text-xs text-zinc-400">Total Agents</span>
            </div>
            <div className="text-2xl font-bold text-blue-400">{agents.length}</div>
          </div>
          <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp size={16} className="text-green-400" />
              <span className="text-xs text-zinc-400">Avg Score</span>
            </div>
            <div className={cn('text-2xl font-bold', scoreColor(avgScore))}>{avgScore}%</div>
          </div>
          <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
            <div className="flex items-center gap-2 mb-1">
              <Activity size={16} className="text-zinc-400" />
              <span className="text-xs text-zinc-400">Total Runs</span>
            </div>
            <div className="text-2xl font-bold text-zinc-300">{totalRuns}</div>
          </div>
          <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle size={16} className="text-amber-400" />
              <span className="text-xs text-zinc-400">Total Issues</span>
            </div>
            <div className="text-2xl font-bold text-amber-400">{totalIssues}</div>
          </div>
        </div>

        {/* Agent list */}
        {agents.length === 0 ? (
          <Card>
            <div className="text-center py-12">
              <Bot className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <p className="text-zinc-400 mb-2">No agent data yet</p>
              <p className="text-zinc-500 text-sm">
                Agent quality scores appear after runs are analyzed
              </p>
            </div>
          </Card>
        ) : (
          <div className="rounded-xl bg-zinc-800/50 border border-zinc-700 overflow-hidden">
            <div className="p-4 border-b border-zinc-700">
              <span className="text-sm text-zinc-400">{agents.length} agents found</span>
            </div>
            <div>
              {agents.map((agent) => (
                <div key={agent.agent_id}>
                  <div
                    onClick={() => setSelectedAgent(selectedAgent === agent.agent_id ? null : agent.agent_id)}
                    className="flex items-center px-4 py-3 hover:bg-zinc-800/80 transition-colors cursor-pointer border-b border-zinc-700/50"
                  >
                    {/* Expand icon */}
                    <div className="shrink-0 mr-3 text-zinc-500">
                      {selectedAgent === agent.agent_id
                        ? <ChevronDown size={16} />
                        : <ChevronRight size={16} />
                      }
                    </div>

                    {/* Agent name */}
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className="p-1.5 rounded-lg bg-zinc-700/50 shrink-0">
                        <Bot size={16} className="text-blue-400" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-white">{agent.agent_name}</div>
                        {agent.agent_type && (
                          <div className="text-xs text-zinc-500">{agent.agent_type}</div>
                        )}
                      </div>
                    </div>

                    {/* Grade */}
                    <div className="w-24 shrink-0">
                      <span className={cn(
                        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border',
                        gradeColor(agent.grade)
                      )}>
                        {agent.grade}
                      </span>
                    </div>

                    {/* Score */}
                    <div className="w-16 shrink-0 text-right">
                      <span className={cn('text-sm font-mono font-medium', scoreColor(agent.avg_score))}>
                        {agent.avg_score}%
                      </span>
                    </div>

                    {/* Range */}
                    <div className="w-24 shrink-0 text-right hidden md:block">
                      <span className="text-xs text-zinc-500">
                        {agent.min_score}% – {agent.max_score}%
                      </span>
                    </div>

                    {/* Runs */}
                    <div className="w-16 shrink-0 text-right">
                      <span className="text-sm text-zinc-300">{agent.total_runs}</span>
                    </div>

                    {/* Issues */}
                    <div className="w-16 shrink-0 text-right">
                      {agent.issues_count > 0 ? (
                        <span className="text-sm text-amber-400">{agent.issues_count}</span>
                      ) : (
                        <span className="text-sm text-zinc-500">0</span>
                      )}
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {selectedAgent === agent.agent_id && (
                    <AgentDetailPanel agentId={agent.agent_id} />
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
