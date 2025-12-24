'use client'

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Bot, Activity, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { clsx } from 'clsx'
import { AgentInfo, AgentStatus } from './AgentCard'

const statusConfig: Record<AgentStatus, { color: string; borderColor: string; icon: typeof CheckCircle }> = {
  idle: { color: 'text-slate-400', borderColor: 'border-slate-600', icon: Clock },
  running: { color: 'text-emerald-400', borderColor: 'border-emerald-500', icon: Activity },
  completed: { color: 'text-blue-400', borderColor: 'border-blue-500', icon: CheckCircle },
  failed: { color: 'text-red-400', borderColor: 'border-red-500', icon: AlertCircle },
  waiting: { color: 'text-amber-400', borderColor: 'border-amber-500', icon: Clock },
}

const typeColors: Record<AgentInfo['type'], string> = {
  coordinator: 'from-purple-500/30 to-purple-600/10',
  worker: 'from-blue-500/30 to-blue-600/10',
  specialist: 'from-emerald-500/30 to-emerald-600/10',
  validator: 'from-amber-500/30 to-amber-600/10',
}

interface AgentNodeData {
  agent: AgentInfo
  isActive?: boolean
  onClick?: () => void
}

function AgentNodeComponent({ data }: NodeProps<AgentNodeData>) {
  const { agent, isActive, onClick } = data
  const status = statusConfig[agent.status]
  const StatusIcon = status.icon

  return (
    <>
      <Handle type="target" position={Position.Top} className="!bg-slate-500" />
      <Handle type="target" position={Position.Left} className="!bg-slate-500" />
      <div
        onClick={onClick}
        className={clsx(
          'relative p-4 rounded-xl border-2 transition-all duration-300 cursor-pointer min-w-[160px]',
          'bg-gradient-to-br',
          typeColors[agent.type],
          status.borderColor,
          isActive && 'ring-2 ring-primary-500 ring-offset-2 ring-offset-slate-900',
          agent.status === 'running' && 'animate-pulse-subtle'
        )}
      >
        {agent.status === 'running' && (
          <div className="absolute -inset-1 rounded-xl bg-gradient-to-r from-emerald-500/20 to-blue-500/20 animate-spin-slow blur-sm" />
        )}

        <div className="relative flex flex-col items-center gap-2">
          <div className={clsx('p-3 rounded-full bg-slate-800/80', status.borderColor, 'border')}>
            <Bot size={24} className={status.color} />
          </div>
          <div className="text-center">
            <div className="font-semibold text-white text-sm">{agent.name}</div>
            <div className="flex items-center justify-center gap-1 mt-1">
              <StatusIcon size={12} className={clsx(status.color, agent.status === 'running' && 'animate-spin')} />
              <span className={clsx('text-xs', status.color)}>{agent.status}</span>
            </div>
          </div>
          <div className="flex gap-3 text-xs text-slate-400 mt-1">
            <span>{agent.tokensUsed.toLocaleString()} tok</span>
            <span>{agent.stepCount} steps</span>
          </div>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-slate-500" />
      <Handle type="source" position={Position.Right} className="!bg-slate-500" />
    </>
  )
}

export const AgentNode = memo(AgentNodeComponent)
