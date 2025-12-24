'use client'

import { useMemo } from 'react'
import { clsx } from 'clsx'
import {
  Activity,
  Heart,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Cpu,
  Zap,
  Clock,
  TrendingUp,
  Shield,
} from 'lucide-react'
import { AgentInfo } from './AgentCard'

interface AgentHealthDashboardProps {
  agents: AgentInfo[]
}

interface HealthMetric {
  name: string
  value: number
  status: 'healthy' | 'warning' | 'critical'
  trend: 'up' | 'down' | 'stable'
  description: string
}

function calculateHealthScore(agents: AgentInfo[]): number {
  const runningCount = agents.filter((a) => a.status === 'running' || a.status === 'completed').length
  const errorRate = agents.reduce((sum, a) => sum + a.errorCount, 0) / agents.length
  const avgLatency = agents.reduce((sum, a) => sum + a.latencyMs, 0) / agents.length

  let score = 100
  score -= (1 - runningCount / agents.length) * 30
  score -= Math.min(errorRate * 10, 30)
  score -= avgLatency > 1000 ? 20 : avgLatency > 500 ? 10 : 0

  return Math.max(0, Math.min(100, Math.round(score)))
}

function getHealthMetrics(agents: AgentInfo[]): HealthMetric[] {
  const activeAgents = agents.filter((a) => a.status === 'running').length
  const failedAgents = agents.filter((a) => a.status === 'failed').length
  const avgLatency = agents.reduce((sum, a) => sum + a.latencyMs, 0) / agents.length
  const totalErrors = agents.reduce((sum, a) => sum + a.errorCount, 0)
  const avgTokens = agents.reduce((sum, a) => sum + a.tokensUsed, 0) / agents.length

  return [
    {
      name: 'Active Agents',
      value: activeAgents,
      status: activeAgents >= agents.length * 0.7 ? 'healthy' : activeAgents >= agents.length * 0.4 ? 'warning' : 'critical',
      trend: 'up',
      description: `${activeAgents} of ${agents.length} agents currently active`,
    },
    {
      name: 'Failed Agents',
      value: failedAgents,
      status: failedAgents === 0 ? 'healthy' : failedAgents <= 1 ? 'warning' : 'critical',
      trend: failedAgents === 0 ? 'stable' : 'down',
      description: failedAgents === 0 ? 'All agents operational' : `${failedAgents} agent(s) need attention`,
    },
    {
      name: 'Avg Latency',
      value: Math.round(avgLatency),
      status: avgLatency < 300 ? 'healthy' : avgLatency < 800 ? 'warning' : 'critical',
      trend: avgLatency < 500 ? 'up' : 'down',
      description: `${Math.round(avgLatency)}ms average response time`,
    },
    {
      name: 'Error Count',
      value: totalErrors,
      status: totalErrors === 0 ? 'healthy' : totalErrors < 5 ? 'warning' : 'critical',
      trend: totalErrors === 0 ? 'stable' : 'down',
      description: `${totalErrors} total errors across all agents`,
    },
  ]
}

const statusIcons = {
  healthy: CheckCircle,
  warning: AlertTriangle,
  critical: XCircle,
}

const statusColors = {
  healthy: { text: 'text-emerald-400', bg: 'bg-emerald-500/20', border: 'border-emerald-500/30' },
  warning: { text: 'text-amber-400', bg: 'bg-amber-500/20', border: 'border-amber-500/30' },
  critical: { text: 'text-red-400', bg: 'bg-red-500/20', border: 'border-red-500/30' },
}

export function AgentHealthDashboard({ agents }: AgentHealthDashboardProps) {
  const healthScore = useMemo(() => calculateHealthScore(agents), [agents])
  const metrics = useMemo(() => getHealthMetrics(agents), [agents])

  const overallStatus = healthScore >= 80 ? 'healthy' : healthScore >= 50 ? 'warning' : 'critical'
  const StatusIcon = statusIcons[overallStatus]
  const colors = statusColors[overallStatus]

  return (
    <div className="space-y-6">
      <div className={clsx(
        'relative p-6 rounded-2xl border overflow-hidden',
        colors.border,
        colors.bg
      )}>
        <div className="absolute inset-0 bg-gradient-to-br from-transparent via-white/5 to-transparent opacity-50" />
        
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={clsx(
              'relative p-4 rounded-2xl',
              colors.bg,
              overallStatus === 'healthy' && 'animate-pulse-subtle'
            )}>
              <Heart size={32} className={colors.text} />
              {overallStatus === 'healthy' && (
                <div className="absolute inset-0 rounded-2xl bg-emerald-500/20 animate-ping" style={{ animationDuration: '2s' }} />
              )}
            </div>
            <div>
              <h2 className="text-2xl font-bold text-white mb-1">System Health</h2>
              <div className="flex items-center gap-2">
                <StatusIcon size={16} className={colors.text} />
                <span className={clsx('text-sm font-medium capitalize', colors.text)}>
                  {overallStatus}
                </span>
              </div>
            </div>
          </div>

          <div className="text-right">
            <div className="text-5xl font-bold text-white mb-1">{healthScore}</div>
            <div className="text-sm text-slate-400">Health Score</div>
          </div>
        </div>

        <div className="relative mt-6">
          <div className="h-3 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={clsx(
                'h-full rounded-full transition-all duration-1000',
                healthScore >= 80 ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' :
                healthScore >= 50 ? 'bg-gradient-to-r from-amber-500 to-amber-400' :
                'bg-gradient-to-r from-red-500 to-red-400'
              )}
              style={{ width: `${healthScore}%` }}
            />
          </div>
          <div className="flex justify-between mt-2 text-xs text-slate-500">
            <span>0</span>
            <span>50</span>
            <span>100</span>
          </div>
        </div>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((metric) => {
          const Icon = statusIcons[metric.status]
          const mColors = statusColors[metric.status]

          return (
            <div
              key={metric.name}
              className={clsx(
                'p-4 rounded-xl border transition-all hover:scale-[1.02]',
                'bg-slate-800/50',
                mColors.border
              )}
            >
              <div className="flex items-start justify-between mb-3">
                <div className={clsx('p-2 rounded-lg', mColors.bg)}>
                  <Icon size={16} className={mColors.text} />
                </div>
                <div className={clsx(
                  'flex items-center gap-1 text-xs',
                  metric.trend === 'up' ? 'text-emerald-400' :
                  metric.trend === 'down' ? 'text-red-400' :
                  'text-slate-400'
                )}>
                  <TrendingUp
                    size={12}
                    className={clsx(
                      metric.trend === 'down' && 'rotate-180',
                      metric.trend === 'stable' && 'rotate-90'
                    )}
                  />
                  <span>{metric.trend}</span>
                </div>
              </div>
              <div className="text-2xl font-bold text-white mb-1">
                {metric.name === 'Avg Latency' ? `${metric.value}ms` : metric.value}
              </div>
              <div className="text-xs text-slate-400">{metric.name}</div>
              <p className="text-xs text-slate-500 mt-2">{metric.description}</p>
            </div>
          )
        })}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Shield size={16} className="text-primary-400" />
            Agent Status Distribution
          </h3>
          <div className="space-y-3">
            {['running', 'completed', 'idle', 'waiting', 'failed'].map((status) => {
              const count = agents.filter((a) => a.status === status).length
              const percentage = (count / agents.length) * 100

              return (
                <div key={status} className="flex items-center gap-3">
                  <span className="text-xs text-slate-400 w-20 capitalize">{status}</span>
                  <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={clsx(
                        'h-full rounded-full transition-all duration-500',
                        status === 'running' ? 'bg-emerald-500' :
                        status === 'completed' ? 'bg-blue-500' :
                        status === 'failed' ? 'bg-red-500' :
                        status === 'waiting' ? 'bg-amber-500' :
                        'bg-slate-500'
                      )}
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                  <span className="text-xs text-white w-8 text-right">{count}</span>
                </div>
              )
            })}
          </div>
        </div>

        <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Activity size={16} className="text-primary-400" />
            Quick Actions
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <button className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 transition-colors text-sm font-medium">
              Restart Failed
            </button>
            <button className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-400 hover:bg-blue-500/20 transition-colors text-sm font-medium">
              Run Diagnostics
            </button>
            <button className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/30 text-purple-400 hover:bg-purple-500/20 transition-colors text-sm font-medium">
              Clear Caches
            </button>
            <button className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 transition-colors text-sm font-medium">
              View Logs
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
