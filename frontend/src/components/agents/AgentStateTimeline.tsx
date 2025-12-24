'use client'

import { useState } from 'react'
import { clsx } from 'clsx'
import { 
  Play, 
  CheckCircle, 
  XCircle, 
  Clock, 
  MessageSquare, 
  Wrench, 
  Brain,
  ChevronDown,
  ChevronUp,
  Zap
} from 'lucide-react'
import { ActivityEvent } from './AgentActivityFeed'
import { formatDistanceToNow } from 'date-fns'

interface AgentStateTimelineProps {
  events: ActivityEvent[]
}

const eventIcons: Record<ActivityEvent['type'], typeof Play> = {
  started: Play,
  completed: CheckCircle,
  failed: XCircle,
  message_sent: MessageSquare,
  message_received: MessageSquare,
  thinking: Brain,
  tool_call: Wrench,
}

const eventColors: Record<ActivityEvent['type'], { bg: string; border: string; icon: string }> = {
  started: { bg: 'bg-blue-500/20', border: 'border-blue-500', icon: 'text-blue-400' },
  completed: { bg: 'bg-emerald-500/20', border: 'border-emerald-500', icon: 'text-emerald-400' },
  failed: { bg: 'bg-red-500/20', border: 'border-red-500', icon: 'text-red-400' },
  message_sent: { bg: 'bg-purple-500/20', border: 'border-purple-500', icon: 'text-purple-400' },
  message_received: { bg: 'bg-cyan-500/20', border: 'border-cyan-500', icon: 'text-cyan-400' },
  thinking: { bg: 'bg-amber-500/20', border: 'border-amber-500', icon: 'text-amber-400' },
  tool_call: { bg: 'bg-indigo-500/20', border: 'border-indigo-500', icon: 'text-indigo-400' },
}

export function AgentStateTimeline({ events }: AgentStateTimelineProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filter, setFilter] = useState<ActivityEvent['type'] | 'all'>('all')

  const filteredEvents = filter === 'all' 
    ? events 
    : events.filter((e) => e.type === filter)

  const filters: Array<{ value: ActivityEvent['type'] | 'all'; label: string }> = [
    { value: 'all', label: 'All' },
    { value: 'started', label: 'Started' },
    { value: 'completed', label: 'Completed' },
    { value: 'tool_call', label: 'Tool Calls' },
    { value: 'message_sent', label: 'Messages' },
    { value: 'thinking', label: 'Thinking' },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              filter === f.value
                ? 'bg-primary-600 text-white'
                : 'bg-slate-800 text-slate-400 hover:bg-slate-700'
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="relative">
        <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-primary-500 via-slate-600 to-transparent" />

        <div className="space-y-4">
          {filteredEvents.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <Clock size={32} className="mx-auto mb-2 opacity-50" />
              <p>No events to display</p>
            </div>
          ) : (
            filteredEvents.map((event, index) => {
              const Icon = eventIcons[event.type]
              const colors = eventColors[event.type]
              const isExpanded = expandedId === event.id
              const isFirst = index === 0

              return (
                <div key={event.id} className="relative pl-14">
                  <div
                    className={clsx(
                      'absolute left-4 w-5 h-5 rounded-full border-2 flex items-center justify-center',
                      colors.bg,
                      colors.border,
                      isFirst && 'animate-pulse'
                    )}
                  >
                    <Icon size={10} className={colors.icon} />
                  </div>

                  <button
                    onClick={() => setExpandedId(isExpanded ? null : event.id)}
                    className={clsx(
                      'w-full text-left p-4 rounded-xl border transition-all',
                      'bg-slate-800/50 hover:bg-slate-800',
                      isExpanded ? 'border-primary-500/50' : 'border-slate-700'
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={clsx('text-xs font-medium capitalize', colors.icon)}>
                            {event.type.replace('_', ' ')}
                          </span>
                          <span className="text-xs text-slate-500">
                            {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                          </span>
                        </div>
                        <p className="text-sm text-white">{event.content}</p>
                      </div>
                      {isExpanded ? (
                        <ChevronUp size={16} className="text-slate-500" />
                      ) : (
                        <ChevronDown size={16} className="text-slate-500" />
                      )}
                    </div>

                    {isExpanded && (
                      <div className="mt-4 pt-4 border-t border-slate-700 animate-fade-in">
                        <div className="grid grid-cols-2 gap-4 text-xs">
                          <div>
                            <span className="text-slate-500">Event ID</span>
                            <p className="text-slate-300 font-mono mt-1">{event.id}</p>
                          </div>
                          <div>
                            <span className="text-slate-500">Timestamp</span>
                            <p className="text-slate-300 mt-1">
                              {new Date(event.timestamp).toLocaleString()}
                            </p>
                          </div>
                          {event.metadata && (
                            <div className="col-span-2">
                              <span className="text-slate-500">Metadata</span>
                              <pre className="text-slate-300 mt-1 p-2 rounded bg-slate-900 overflow-x-auto">
                                {JSON.stringify(event.metadata, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </button>
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}
