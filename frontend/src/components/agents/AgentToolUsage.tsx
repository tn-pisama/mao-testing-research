'use client'

import { useMemo } from 'react'
import { clsx } from 'clsx'
import { Wrench, Clock, CheckCircle, XCircle, TrendingUp } from 'lucide-react'
import { AgentInfo } from './AgentCard'

interface ToolUsage {
  name: string
  calls: number
  successRate: number
  avgLatency: number
  lastUsed: string
  trend: 'up' | 'down' | 'stable'
}

interface AgentToolUsageProps {
  agent: AgentInfo
}

function generateToolUsage(): ToolUsage[] {
  return [
    { name: 'search_documents', calls: 156, successRate: 98.2, avgLatency: 234, lastUsed: '2 min ago', trend: 'up' },
    { name: 'generate_response', calls: 89, successRate: 95.5, avgLatency: 1250, lastUsed: '5 min ago', trend: 'stable' },
    { name: 'validate_output', calls: 67, successRate: 100, avgLatency: 45, lastUsed: '1 min ago', trend: 'up' },
    { name: 'fetch_context', calls: 45, successRate: 91.1, avgLatency: 890, lastUsed: '8 min ago', trend: 'down' },
    { name: 'analyze_intent', calls: 34, successRate: 97.1, avgLatency: 156, lastUsed: '3 min ago', trend: 'stable' },
    { name: 'format_output', calls: 28, successRate: 100, avgLatency: 12, lastUsed: '1 min ago', trend: 'up' },
  ]
}

export function AgentToolUsage({ agent }: AgentToolUsageProps) {
  const tools = useMemo(() => generateToolUsage(), [])
  const totalCalls = tools.reduce((sum, t) => sum + t.calls, 0)
  const avgSuccess = tools.reduce((sum, t) => sum + t.successRate, 0) / tools.length

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-gradient-to-br from-purple-500/20 to-purple-600/10 border border-purple-500/30">
          <div className="flex items-center gap-2 mb-2">
            <Wrench size={14} className="text-purple-400" />
            <span className="text-xs text-purple-400">Total Tools</span>
          </div>
          <div className="text-2xl font-bold text-white">{tools.length}</div>
        </div>
        <div className="p-4 rounded-xl bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/30">
          <div className="flex items-center gap-2 mb-2">
            <Clock size={14} className="text-blue-400" />
            <span className="text-xs text-blue-400">Total Calls</span>
          </div>
          <div className="text-2xl font-bold text-white">{totalCalls}</div>
        </div>
        <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-500/20 to-emerald-600/10 border border-emerald-500/30">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle size={14} className="text-emerald-400" />
            <span className="text-xs text-emerald-400">Avg Success</span>
          </div>
          <div className="text-2xl font-bold text-white">{avgSuccess.toFixed(1)}%</div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-800/50">
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-400">Tool Name</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-400">Calls</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-400">Success Rate</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-400">Avg Latency</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-400">Last Used</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-slate-400">Trend</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {tools.map((tool) => (
              <tr key={tool.name} className="hover:bg-slate-800/30 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded bg-slate-700/50">
                      <Wrench size={12} className="text-slate-400" />
                    </div>
                    <span className="text-sm font-mono text-white">{tool.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-right text-sm text-slate-300">{tool.calls}</td>
                <td className="px-4 py-3 text-right">
                  <span className={clsx(
                    'text-sm font-medium',
                    tool.successRate >= 95 ? 'text-emerald-400' : 
                    tool.successRate >= 80 ? 'text-amber-400' : 'text-red-400'
                  )}>
                    {tool.successRate}%
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-sm text-slate-300">{tool.avgLatency}ms</td>
                <td className="px-4 py-3 text-right text-xs text-slate-500">{tool.lastUsed}</td>
                <td className="px-4 py-3 text-center">
                  <TrendingUp
                    size={14}
                    className={clsx(
                      'inline',
                      tool.trend === 'up' ? 'text-emerald-400' :
                      tool.trend === 'down' ? 'text-red-400 rotate-180' :
                      'text-slate-500 rotate-90'
                    )}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
