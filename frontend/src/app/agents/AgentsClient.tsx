'use client'

import { Layout } from '@/components/common/Layout'
import { Card, CardContent } from '@/components/ui/Card'
import { Bot, TrendingUp, AlertTriangle, Activity } from 'lucide-react'
import { cn } from '@/lib/utils'

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

export function AgentsClient({ initialAgents }: { initialAgents: AgentQuality[] }) {
  const agents = initialAgents
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
          Individual agent performance across all workflow runs
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
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700 text-left text-xs text-zinc-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Agent</th>
                  <th className="px-4 py-3">Grade</th>
                  <th className="px-4 py-3">Avg Score</th>
                  <th className="px-4 py-3">Range</th>
                  <th className="px-4 py-3">Runs</th>
                  <th className="px-4 py-3">Issues</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-700/50">
                {agents.map((agent) => (
                  <tr key={agent.agent_id} className="hover:bg-zinc-800/80 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="p-1.5 rounded-lg bg-zinc-700/50">
                          <Bot size={16} className="text-blue-400" />
                        </div>
                        <div>
                          <div className="text-sm font-medium text-white">{agent.agent_name}</div>
                          {agent.agent_type && (
                            <div className="text-xs text-zinc-500">{agent.agent_type}</div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border',
                        gradeColor(agent.grade)
                      )}>
                        {agent.grade}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn('text-sm font-mono font-medium', scoreColor(agent.avg_score))}>
                        {agent.avg_score}%
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-zinc-500">
                        {agent.min_score}% – {agent.max_score}%
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-zinc-300">{agent.total_runs}</span>
                    </td>
                    <td className="px-4 py-3">
                      {agent.issues_count > 0 ? (
                        <span className="text-sm text-amber-400">{agent.issues_count}</span>
                      ) : (
                        <span className="text-sm text-zinc-500">0</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  )
}
