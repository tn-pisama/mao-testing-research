'use client'

import { Card } from '../ui/Card'
import { Network, ArrowRight } from 'lucide-react'
import clsx from 'clsx'
import type { AgentInfo } from './index'

interface Message {
  id: string
  from: string
  to: string
  type: 'task' | 'result' | 'error' | 'delegation'
  content: string
  timestamp: string
}

interface AgentOrchestrationViewProps {
  agents?: AgentInfo[]
  messages?: Message[]
  activeAgentId?: string
  onAgentClick?: (agentId: string) => void
}

const statusColors: Record<string, string> = {
  running: 'border-green-500/50 bg-green-500/5',
  idle: 'border-slate-500/50 bg-slate-500/5',
  completed: 'border-blue-500/50 bg-blue-500/5',
  failed: 'border-red-500/50 bg-red-500/5',
  waiting: 'border-amber-500/50 bg-amber-500/5',
}

const statusDots: Record<string, string> = {
  running: 'bg-green-400',
  idle: 'bg-slate-400',
  completed: 'bg-blue-400',
  failed: 'bg-red-400',
  waiting: 'bg-amber-400',
}

const messageTypeColors: Record<string, string> = {
  task: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  result: 'text-green-400 bg-green-500/10 border-green-500/30',
  error: 'text-red-400 bg-red-500/10 border-red-500/30',
  delegation: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
}

export function AgentOrchestrationView({
  agents,
  messages,
  activeAgentId,
  onAgentClick,
}: AgentOrchestrationViewProps) {
  if (!agents || agents.length === 0) {
    return (
      <Card>
        <div className="text-center py-12 text-slate-400">
          <Network size={32} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No orchestration data</p>
          <p className="text-xs mt-1">Agent workflow visualization will appear here</p>
        </div>
      </Card>
    )
  }

  const agentMap = new Map(agents.map((a) => [a.id, a]))

  return (
    <div className="space-y-4">
      <Card padding="none">
        <div className="px-4 py-3 border-b border-slate-700/50 flex items-center gap-2">
          <Network size={16} className="text-slate-400" />
          <span className="text-sm font-medium text-white">Agent Nodes</span>
        </div>
        <div className="p-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
          {agents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => onAgentClick?.(agent.id)}
              className={clsx(
                'p-3 rounded-lg border transition-all text-left',
                statusColors[agent.status] ?? statusColors.idle,
                activeAgentId === agent.id && 'ring-2 ring-blue-500'
              )}
            >
              <div className="flex items-center gap-2 mb-1">
                <div className={clsx('w-2 h-2 rounded-full', statusDots[agent.status] ?? statusDots.idle)} />
                <span className="text-sm font-medium text-white truncate">{agent.name}</span>
              </div>
              <div className="text-xs text-slate-500 capitalize">{agent.type}</div>
              {agent.currentTask && (
                <div className="text-xs text-slate-400 mt-1 truncate">{agent.currentTask}</div>
              )}
            </button>
          ))}
        </div>
      </Card>

      {messages && messages.length > 0 && (
        <Card padding="none">
          <div className="px-4 py-3 border-b border-slate-700/50 flex items-center gap-2">
            <ArrowRight size={16} className="text-slate-400" />
            <span className="text-sm font-medium text-white">Message Flow</span>
            <span className="text-xs text-slate-500">({messages.length})</span>
          </div>
          <div className="divide-y divide-slate-800/50 max-h-64 overflow-y-auto">
            {messages.map((msg) => {
              const fromAgent = agentMap.get(msg.from)
              const toAgent = agentMap.get(msg.to)
              return (
                <div key={msg.id} className="px-4 py-2.5 hover:bg-slate-800/30 transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm text-white font-medium">{fromAgent?.name ?? 'Unknown'}</span>
                    <ArrowRight size={12} className="text-slate-500" />
                    <span className="text-sm text-white font-medium">{toAgent?.name ?? 'Unknown'}</span>
                    <span className={clsx(
                      'px-1.5 py-0.5 text-xs rounded border ml-auto',
                      messageTypeColors[msg.type] ?? messageTypeColors.task
                    )}>
                      {msg.type}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 truncate">{msg.content}</p>
                </div>
              )
            })}
          </div>
        </Card>
      )}
    </div>
  )
}
