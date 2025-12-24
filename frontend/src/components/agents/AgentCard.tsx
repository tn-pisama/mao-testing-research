'use client'

import { clsx } from 'clsx'
import { Bot, Cpu, Zap, AlertCircle, CheckCircle, Clock, Activity } from 'lucide-react'

export type AgentStatus = 'idle' | 'running' | 'completed' | 'failed' | 'waiting'

export interface AgentInfo {
  id: string
  name: string
  type: 'coordinator' | 'worker' | 'specialist' | 'validator'
  status: AgentStatus
  currentTask?: string
  tokensUsed: number
  latencyMs: number
  stepCount: number
  errorCount: number
  lastActiveAt?: string
}

const statusConfig: Record<AgentStatus, { color: string; icon: typeof CheckCircle; label: string }> = {
  idle: { color: 'text-slate-400', icon: Clock, label: 'Idle' },
  running: { color: 'text-emerald-400', icon: Activity, label: 'Running' },
  completed: { color: 'text-blue-400', icon: CheckCircle, label: 'Completed' },
  failed: { color: 'text-red-400', icon: AlertCircle, label: 'Failed' },
  waiting: { color: 'text-amber-400', icon: Clock, label: 'Waiting' },
}

const typeConfig: Record<AgentInfo['type'], { color: string; bgColor: string }> = {
  coordinator: { color: 'text-purple-400', bgColor: 'bg-purple-500/20' },
  worker: { color: 'text-blue-400', bgColor: 'bg-blue-500/20' },
  specialist: { color: 'text-emerald-400', bgColor: 'bg-emerald-500/20' },
  validator: { color: 'text-amber-400', bgColor: 'bg-amber-500/20' },
}

interface AgentCardProps {
  agent: AgentInfo
  isActive?: boolean
  onClick?: () => void
}

export function AgentCard({ agent, isActive, onClick }: AgentCardProps) {
  const status = statusConfig[agent.status]
  const type = typeConfig[agent.type]
  const StatusIcon = status.icon

  return (
    <div
      onClick={onClick}
      className={clsx(
        'relative p-4 rounded-xl border transition-all duration-300 cursor-pointer group',
        'bg-slate-800/50 hover:bg-slate-800',
        isActive
          ? 'border-primary-500 shadow-lg shadow-primary-500/20'
          : 'border-slate-700 hover:border-slate-600',
        agent.status === 'running' && 'animate-pulse-subtle'
      )}
    >
      {agent.status === 'running' && (
        <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-primary-500/10 to-emerald-500/10 animate-shimmer" />
      )}
      
      <div className="relative">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={clsx('p-2 rounded-lg', type.bgColor)}>
              <Bot size={20} className={type.color} />
            </div>
            <div>
              <h3 className="font-semibold text-white text-sm">{agent.name}</h3>
              <span className={clsx('text-xs capitalize', type.color)}>{agent.type}</span>
            </div>
          </div>
          <div className={clsx('flex items-center gap-1.5 px-2 py-1 rounded-full text-xs', status.color)}>
            <StatusIcon size={12} className={agent.status === 'running' ? 'animate-spin' : ''} />
            <span>{status.label}</span>
          </div>
        </div>

        {agent.currentTask && (
          <div className="mb-3 p-2 rounded-lg bg-slate-900/50 border border-slate-700">
            <p className="text-xs text-slate-400 truncate">{agent.currentTask}</p>
          </div>
        )}

        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 rounded-lg bg-slate-900/50">
            <div className="text-xs text-slate-400 mb-1">Tokens</div>
            <div className="text-sm font-mono text-white">{agent.tokensUsed.toLocaleString()}</div>
          </div>
          <div className="p-2 rounded-lg bg-slate-900/50">
            <div className="text-xs text-slate-400 mb-1">Steps</div>
            <div className="text-sm font-mono text-white">{agent.stepCount}</div>
          </div>
          <div className="p-2 rounded-lg bg-slate-900/50">
            <div className="text-xs text-slate-400 mb-1">Latency</div>
            <div className="text-sm font-mono text-white">{agent.latencyMs}ms</div>
          </div>
        </div>

        {agent.errorCount > 0 && (
          <div className="mt-3 flex items-center gap-2 text-red-400 text-xs">
            <AlertCircle size={12} />
            <span>{agent.errorCount} error{agent.errorCount > 1 ? 's' : ''} detected</span>
          </div>
        )}
      </div>
    </div>
  )
}
