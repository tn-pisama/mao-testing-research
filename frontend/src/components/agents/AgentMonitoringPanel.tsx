'use client'

import { Card } from '../ui/Card'
import { Monitor } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentInfo, ActivityEvent } from './index'

interface AgentMonitoringPanelProps {
  agents?: AgentInfo[]
  events?: ActivityEvent[]
  isLive?: boolean
}

const statusColors: Record<string, string> = {
  running: 'bg-green-500/20 text-green-400 border-green-500/30',
  idle: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
  completed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  waiting: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
}

const statusBarColors: Record<string, string> = {
  running: 'bg-green-500',
  idle: 'bg-zinc-500',
  completed: 'bg-blue-500',
  failed: 'bg-red-500',
  waiting: 'bg-amber-500',
}

function formatRelativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ago`
}

export function AgentMonitoringPanel({ agents, events, isLive }: AgentMonitoringPanelProps) {
  if (!agents || agents.length === 0) {
    return (
      <Card>
        <div className="text-center py-12 text-zinc-400">
          <Monitor size={32} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No monitoring data</p>
          <p className="text-xs mt-1">Real-time agent status will appear here</p>
        </div>
      </Card>
    )
  }

  const statusCounts: Record<string, number> = {}
  for (const agent of agents) {
    statusCounts[agent.status] = (statusCounts[agent.status] ?? 0) + 1
  }

  const sortedAgents = [...agents].sort((a, b) => {
    if (a.status === 'running' && b.status !== 'running') return -1
    if (a.status !== 'running' && b.status === 'running') return 1
    return a.latencyMs - b.latencyMs
  })

  return (
    <div className="space-y-4">
      <Card padding="none">
        <div className="px-4 py-3 border-b border-zinc-700/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Monitor size={16} className="text-zinc-400" />
            <span className="text-sm font-medium text-white">Status Distribution</span>
          </div>
          {isLive && (
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
              </span>
              <span className="text-xs text-green-400">Monitoring</span>
            </div>
          )}
        </div>
        <div className="p-4">
          <div className="flex rounded-full h-3 overflow-hidden bg-zinc-800">
            {Object.entries(statusCounts).map(([status, count]) => (
              <div
                key={status}
                className={cn('h-full transition-all', statusBarColors[status] ?? 'bg-zinc-500')}
                style={{ width: `${(count / agents.length) * 100}%` }}
                title={`${status}: ${count}`}
              />
            ))}
          </div>
          <div className="flex gap-4 mt-2">
            {Object.entries(statusCounts).map(([status, count]) => (
              <div key={status} className="flex items-center gap-1.5">
                <div className={cn('w-2 h-2 rounded-full', statusBarColors[status] ?? 'bg-zinc-500')} />
                <span className="text-xs text-zinc-400 capitalize">{status}</span>
                <span className="text-xs text-zinc-500">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <Card padding="none">
        <div className="px-4 py-3 border-b border-zinc-700/50">
          <span className="text-sm font-medium text-white">Agent Status</span>
        </div>
        <div className="divide-y divide-zinc-800/50">
          {sortedAgents.map((agent) => {
            const tokens = agent.tokensUsed
            return (
              <div key={agent.id} className="px-4 py-3 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-white truncate">{agent.name}</div>
                  <div className="text-xs text-zinc-500 capitalize">{agent.type}</div>
                </div>
                <span className={cn(
                  'px-2 py-0.5 text-xs font-medium rounded-full border flex-shrink-0',
                  statusColors[agent.status] ?? statusColors.idle
                )}>
                  {agent.status}
                </span>
                <div className="text-right flex-shrink-0 w-16">
                  <div className="text-xs text-white font-medium">
                    {tokens >= 1000 ? `${(tokens / 1000).toFixed(1)}k` : tokens}
                  </div>
                  <div className="text-xs text-zinc-500">tokens</div>
                </div>
                <div className="text-right flex-shrink-0 w-16">
                  <div className="text-xs text-white font-medium">{agent.latencyMs}ms</div>
                  <div className="text-xs text-zinc-500">latency</div>
                </div>
                <div className="text-right flex-shrink-0 w-16">
                  <div className="text-xs text-zinc-400">{formatRelativeTime(agent.lastActiveAt)}</div>
                </div>
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}
