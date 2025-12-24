'use client'

import { clsx } from 'clsx'
import { Bot, Activity, CheckCircle, AlertCircle, Clock, Zap, DollarSign, Timer, TrendingUp } from 'lucide-react'
import { AgentInfo, AgentStatus } from './AgentCard'
import { Badge } from '@/components/ui/Badge'

interface AgentDetailHeaderProps {
  agent: AgentInfo
  isLive?: boolean
}

const statusConfig: Record<AgentStatus, { color: string; bgColor: string; label: string }> = {
  idle: { color: 'text-slate-400', bgColor: 'bg-slate-500/20', label: 'Idle' },
  running: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20', label: 'Running' },
  completed: { color: 'text-blue-400', bgColor: 'bg-blue-500/20', label: 'Completed' },
  failed: { color: 'text-red-400', bgColor: 'bg-red-500/20', label: 'Failed' },
  waiting: { color: 'text-amber-400', bgColor: 'bg-amber-500/20', label: 'Waiting' },
}

const typeGradients: Record<AgentInfo['type'], string> = {
  coordinator: 'from-purple-500/20 via-purple-600/10 to-transparent',
  worker: 'from-blue-500/20 via-blue-600/10 to-transparent',
  specialist: 'from-emerald-500/20 via-emerald-600/10 to-transparent',
  validator: 'from-amber-500/20 via-amber-600/10 to-transparent',
}

export function AgentDetailHeader({ agent, isLive }: AgentDetailHeaderProps) {
  const status = statusConfig[agent.status]

  return (
    <div className={clsx(
      'relative rounded-2xl border border-slate-700 overflow-hidden',
      'bg-gradient-to-r',
      typeGradients[agent.type]
    )}>
      {agent.status === 'running' && (
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-shimmer" />
      )}

      <div className="relative p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className={clsx(
              'relative p-4 rounded-2xl border',
              status.bgColor,
              agent.status === 'running' ? 'border-emerald-500/50' : 'border-slate-600'
            )}>
              {agent.status === 'running' && (
                <div className="absolute inset-0 rounded-2xl bg-emerald-500/20 animate-pulse" />
              )}
              <Bot size={32} className={status.color} />
            </div>

            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-2xl font-bold text-white">{agent.name}</h1>
                <Badge
                  variant={agent.status === 'running' ? 'success' : agent.status === 'failed' ? 'error' : 'default'}
                  dot
                  pulse={agent.status === 'running'}
                >
                  {status.label}
                </Badge>
                {isLive && (
                  <Badge variant="purple" size="sm">
                    Live
                  </Badge>
                )}
              </div>
              <p className="text-slate-400 capitalize">{agent.type} Agent</p>
              {agent.currentTask && (
                <p className="text-sm text-slate-500 mt-2 max-w-md truncate">
                  Current: {agent.currentTask}
                </p>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            <button className="px-4 py-2 rounded-lg bg-slate-700/50 text-slate-300 hover:bg-slate-700 transition-colors text-sm font-medium">
              Pause
            </button>
            <button className="px-4 py-2 rounded-lg bg-primary-600 text-white hover:bg-primary-500 transition-colors text-sm font-medium">
              Restart
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <StatCard
            icon={Zap}
            label="Tokens Used"
            value={agent.tokensUsed.toLocaleString()}
            trend="+12%"
            trendUp
          />
          <StatCard
            icon={Timer}
            label="Avg Latency"
            value={`${agent.latencyMs}ms`}
            trend="-5%"
            trendUp
          />
          <StatCard
            icon={Activity}
            label="Steps Completed"
            value={agent.stepCount.toString()}
            trend={`${agent.stepCount} total`}
          />
          <StatCard
            icon={AlertCircle}
            label="Errors"
            value={agent.errorCount.toString()}
            trend={agent.errorCount === 0 ? 'None' : 'Needs attention'}
            isError={agent.errorCount > 0}
          />
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  icon: typeof Zap
  label: string
  value: string
  trend?: string
  trendUp?: boolean
  isError?: boolean
}

function StatCard({ icon: Icon, label, value, trend, trendUp, isError }: StatCardProps) {
  return (
    <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={14} className="text-slate-500" />
        <span className="text-xs text-slate-500">{label}</span>
      </div>
      <div className="text-xl font-bold text-white mb-1">{value}</div>
      {trend && (
        <div className={clsx(
          'text-xs',
          isError ? 'text-red-400' : trendUp ? 'text-emerald-400' : 'text-slate-500'
        )}>
          {trendUp && <TrendingUp size={10} className="inline mr-1" />}
          {trend}
        </div>
      )}
    </div>
  )
}
