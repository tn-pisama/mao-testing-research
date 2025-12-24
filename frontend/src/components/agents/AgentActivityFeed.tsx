'use client'

import { useEffect, useRef } from 'react'
import { clsx } from 'clsx'
import { Bot, MessageSquare, AlertTriangle, CheckCircle, ArrowRight, Loader2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

export interface ActivityEvent {
  id: string
  agentId: string
  agentName: string
  type: 'started' | 'completed' | 'failed' | 'message_sent' | 'message_received' | 'thinking' | 'tool_call'
  content: string
  timestamp: string
  metadata?: Record<string, any>
}

interface AgentActivityFeedProps {
  events: ActivityEvent[]
  isLive?: boolean
  maxHeight?: string
}

const eventConfig: Record<ActivityEvent['type'], { color: string; icon: typeof Bot; label: string }> = {
  started: { color: 'text-blue-400', icon: ArrowRight, label: 'Started' },
  completed: { color: 'text-emerald-400', icon: CheckCircle, label: 'Completed' },
  failed: { color: 'text-red-400', icon: AlertTriangle, label: 'Failed' },
  message_sent: { color: 'text-purple-400', icon: MessageSquare, label: 'Sent' },
  message_received: { color: 'text-cyan-400', icon: MessageSquare, label: 'Received' },
  thinking: { color: 'text-amber-400', icon: Loader2, label: 'Thinking' },
  tool_call: { color: 'text-indigo-400', icon: Bot, label: 'Tool Call' },
}

export function AgentActivityFeed({ events, isLive, maxHeight = '400px' }: AgentActivityFeedProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isLive && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [events, isLive])

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
        <h3 className="font-semibold text-white text-sm">Activity Feed</h3>
        {isLive && (
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            <span className="text-xs text-emerald-400">Live</span>
          </div>
        )}
      </div>

      <div
        ref={scrollRef}
        className="overflow-y-auto scrollbar-thin"
        style={{ maxHeight }}
      >
        {events.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <Bot size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">No activity yet</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-700/50">
            {events.map((event, index) => {
              const config = eventConfig[event.type]
              const Icon = config.icon
              const isLatest = index === events.length - 1 && isLive

              return (
                <div
                  key={event.id}
                  className={clsx(
                    'px-4 py-3 transition-colors',
                    isLatest && 'bg-slate-700/30 animate-fade-in'
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className={clsx('p-1.5 rounded-lg bg-slate-900/50', config.color)}>
                      <Icon
                        size={14}
                        className={event.type === 'thinking' ? 'animate-spin' : ''}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-white text-sm">{event.agentName}</span>
                        <span className={clsx('text-xs', config.color)}>{config.label}</span>
                      </div>
                      <p className="text-sm text-slate-400 break-words">{event.content}</p>
                      {event.metadata && (
                        <div className="mt-2 p-2 rounded bg-slate-900/50 text-xs font-mono text-slate-500">
                          {JSON.stringify(event.metadata, null, 2).slice(0, 100)}
                        </div>
                      )}
                    </div>
                    <div className="text-xs text-slate-500 whitespace-nowrap">
                      {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
