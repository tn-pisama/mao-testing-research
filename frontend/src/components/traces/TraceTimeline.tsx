'use client'

import { formatDistanceToNow } from 'date-fns'
import type { State } from '@/lib/api'
import { clsx } from 'clsx'

interface TraceTimelineProps {
  states: State[]
  isLoading: boolean
}

export function TraceTimeline({ states, isLoading }: TraceTimelineProps) {
  if (isLoading) {
    return (
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-8 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-4 max-h-96 overflow-y-auto scrollbar-thin">
      <div className="relative">
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-700"></div>
        {states.map((state, index) => (
          <div key={state.id} className="relative pl-10 pb-6 last:pb-0">
            <div
              className={clsx(
                'absolute left-2.5 w-3 h-3 rounded-full border-2',
                index === states.length - 1
                  ? 'bg-primary-500 border-primary-500'
                  : 'bg-slate-800 border-slate-500'
              )}
            ></div>
            <div className="bg-slate-700/50 rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-white">
                  {state.agent_id}
                </span>
                <span className="text-xs text-slate-400">
                  #{state.sequence_num}
                </span>
              </div>
              <div className="text-xs text-slate-400 flex gap-4">
                <span>{state.token_count} tokens</span>
                <span>{state.latency_ms}ms</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
