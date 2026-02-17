'use client'

import { Card } from '../ui/Card'
import clsx from 'clsx'
import type { AgentInfo } from './index'

interface AgentCardProps {
  agent?: AgentInfo
  onClick?: () => void
  isActive?: boolean
}

const statusColors: Record<string, string> = {
  running: 'bg-green-500/20 text-green-400 border-green-500/30',
  idle: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
  completed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  waiting: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
}

export function AgentCard({ agent, onClick, isActive }: AgentCardProps) {
  const status = agent?.status ?? 'idle'
  const tokens = agent?.tokensUsed ?? 0

  return (
    <Card
      className={clsx(
        'cursor-pointer hover:bg-slate-800 transition-colors',
        isActive && 'ring-2 ring-blue-500'
      )}
      onClick={onClick}
    >
      <div className="p-4 space-y-3">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-sm font-medium text-white">{agent?.name ?? 'Agent'}</div>
            <div className="text-xs text-slate-500 capitalize">{agent?.type ?? 'worker'}</div>
          </div>
          <span className={clsx('px-2 py-0.5 text-xs font-medium rounded-full border', statusColors[status] ?? statusColors.idle)}>
            {status}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div>
            <div className="text-sm font-semibold text-white">{agent?.stepCount ?? 0}</div>
            <div className="text-xs text-slate-500">steps</div>
          </div>
          <div>
            <div className="text-sm font-semibold text-white">
              {tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}k` : tokens}
            </div>
            <div className="text-xs text-slate-500">tokens</div>
          </div>
          <div>
            <div className="text-sm font-semibold text-white">{agent?.latencyMs ?? 0}ms</div>
            <div className="text-xs text-slate-500">latency</div>
          </div>
        </div>
      </div>
    </Card>
  )
}
