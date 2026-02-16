'use client'

import { Card } from '../ui/Card'
import { Clock, Zap } from 'lucide-react'
import type { State } from '@/lib/api'

interface TraceTimelineProps {
  trace?: unknown
  states?: State[]
  isLoading?: boolean
}

export function TraceTimeline({ states, isLoading }: TraceTimelineProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="text-center py-8 text-white/60 font-mono">
          <p className="text-sm">Loading timeline...</p>
        </div>
      </Card>
    )
  }

  if (!states || states.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-white/60 font-mono">
          <p className="text-sm">No state data available</p>
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <div className="space-y-2 max-h-96 overflow-y-auto">
        {states.map((state, idx) => (
          <div
            key={state.id}
            className="flex items-start gap-3 p-3 bg-primary-500/10 border border-primary-500/30 rounded-lg"
          >
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary-500/20 border border-primary-500/50 flex items-center justify-center">
              <span className="text-xs text-primary-500 font-mono">{idx + 1}</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium text-white font-mono truncate">{state.agent_id}</span>
                <span className="text-white/40">•</span>
                <span className="text-white/60 font-mono flex items-center gap-1">
                  <Clock size={12} />
                  {state.latency_ms}ms
                </span>
                <span className="text-white/40">•</span>
                <span className="text-white/60 font-mono flex items-center gap-1">
                  <Zap size={12} />
                  {state.token_count} tokens
                </span>
              </div>
              {state.metadata?.ai_output && (
                <p className="text-xs text-white/60 font-mono mt-1 truncate">
                  {state.metadata.ai_output.slice(0, 100)}...
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
