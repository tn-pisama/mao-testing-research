'use client'

import { Card } from '../ui/Card'
import { Activity } from 'lucide-react'
import clsx from 'clsx'
import type { ActivityEvent } from './index'

interface AgentActivityFeedProps {
  events?: ActivityEvent[]
  isLive?: boolean
  maxHeight?: string
}

const eventTypeColors: Record<ActivityEvent['type'], string> = {
  started: 'bg-blue-400',
  completed: 'bg-green-400',
  failed: 'bg-red-400',
  message_sent: 'bg-purple-400',
  message_received: 'bg-purple-300',
  thinking: 'bg-amber-400',
  tool_call: 'bg-slate-400',
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

export function AgentActivityFeed({ events, isLive, maxHeight }: AgentActivityFeedProps) {
  if (!events || events.length === 0) {
    return (
      <Card>
        <div className="text-center py-12 text-slate-400">
          <Activity size={32} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No activity recorded</p>
          <p className="text-xs mt-1">Agent events will stream here</p>
        </div>
      </Card>
    )
  }

  return (
    <Card padding="none">
      <div className="px-4 py-3 border-b border-slate-700/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-slate-400" />
          <span className="text-sm font-medium text-white">Activity Feed</span>
          <span className="text-xs text-slate-500">({events.length})</span>
        </div>
        {isLive && (
          <div className="flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
            </span>
            <span className="text-xs text-green-400">Live</span>
          </div>
        )}
      </div>
      <div
        className="divide-y divide-slate-800/50 overflow-y-auto"
        style={maxHeight ? { maxHeight } : undefined}
      >
        {events.map((event) => (
          <div key={event.id} className="px-4 py-2.5 hover:bg-slate-800/30 transition-colors">
            <div className="flex items-start gap-3">
              <div className="mt-1.5 flex-shrink-0">
                <div className={clsx('w-2 h-2 rounded-full', eventTypeColors[event.type] ?? 'bg-slate-400')} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white truncate">{event.agentName}</span>
                  <span className="text-xs text-slate-500 capitalize">{event.type.replace('_', ' ')}</span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5 truncate">{event.content}</p>
              </div>
              <span className="text-xs text-slate-600 flex-shrink-0 whitespace-nowrap">
                {formatRelativeTime(event.timestamp)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
