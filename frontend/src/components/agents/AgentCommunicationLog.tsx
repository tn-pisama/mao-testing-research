'use client'

import { useMemo } from 'react'
import { clsx } from 'clsx'
import { ArrowRight, ArrowLeft, MessageSquare, AlertTriangle, CheckCircle } from 'lucide-react'
import { AgentInfo } from './AgentCard'
import { formatDistanceToNow } from 'date-fns'

interface Message {
  id: string
  from: string
  to: string
  type: 'task' | 'result' | 'error' | 'delegation'
  content: string
  timestamp: string
}

interface AgentCommunicationLogProps {
  agentId: string
  messages: Message[]
  agents: AgentInfo[]
}

const messageStyles = {
  task: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', icon: 'text-blue-400' },
  result: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', icon: 'text-emerald-400' },
  error: { bg: 'bg-red-500/10', border: 'border-red-500/30', icon: 'text-red-400' },
  delegation: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', icon: 'text-purple-400' },
}

export function AgentCommunicationLog({ agentId, messages, agents }: AgentCommunicationLogProps) {
  const relevantMessages = useMemo(() => {
    return messages
      .filter((m) => m.from === agentId || m.to === agentId)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  }, [messages, agentId])

  const getAgentName = (id: string) => {
    return agents.find((a) => a.id === id)?.name || id
  }

  const stats = useMemo(() => {
    const sent = relevantMessages.filter((m) => m.from === agentId).length
    const received = relevantMessages.filter((m) => m.to === agentId).length
    const errors = relevantMessages.filter((m) => m.type === 'error').length
    return { sent, received, errors, total: relevantMessages.length }
  }, [relevantMessages, agentId])

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-4">
        <StatBox label="Total Messages" value={stats.total} />
        <StatBox label="Sent" value={stats.sent} color="text-blue-400" />
        <StatBox label="Received" value={stats.received} color="text-emerald-400" />
        <StatBox label="Errors" value={stats.errors} color="text-red-400" />
      </div>

      <div className="space-y-3">
        {relevantMessages.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <MessageSquare size={32} className="mx-auto mb-2 opacity-50" />
            <p>No communication history</p>
          </div>
        ) : (
          relevantMessages.map((message) => {
            const isSent = message.from === agentId
            const styles = messageStyles[message.type]
            const otherAgent = isSent ? message.to : message.from

            return (
              <div
                key={message.id}
                className={clsx(
                  'p-4 rounded-xl border transition-all hover:scale-[1.01]',
                  styles.bg,
                  styles.border
                )}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {isSent ? (
                      <ArrowRight size={14} className={styles.icon} />
                    ) : (
                      <ArrowLeft size={14} className={styles.icon} />
                    )}
                    <span className="text-xs font-medium text-slate-300">
                      {isSent ? 'Sent to' : 'Received from'}{' '}
                      <span className="text-white">{getAgentName(otherAgent)}</span>
                    </span>
                    <span className={clsx(
                      'px-2 py-0.5 rounded text-[10px] font-medium uppercase',
                      styles.bg,
                      styles.icon
                    )}>
                      {message.type}
                    </span>
                  </div>
                  <span className="text-xs text-slate-500">
                    {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
                  </span>
                </div>
                <p className="text-sm text-slate-300">{message.content}</p>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

function StatBox({ label, value, color = 'text-white' }: { label: string; value: number; color?: string }) {
  return (
    <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700 text-center">
      <div className={clsx('text-2xl font-bold', color)}>{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  )
}
