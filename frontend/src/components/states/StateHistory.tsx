'use client'

import { useState } from 'react'
import { Card } from '../ui/Card'
import { ChevronDown, ChevronRight, Hash } from 'lucide-react'
import type { State } from '@/lib/api'

interface StateHistoryProps {
  states?: State[]
  isLoading?: boolean
}

export function StateHistory({ states, isLoading }: StateHistoryProps) {
  const [expandedState, setExpandedState] = useState<string | null>(null)

  if (isLoading) {
    return (
      <Card>
        <div className="text-center py-8 text-slate-400">
          <p className="text-sm">Loading state history...</p>
        </div>
      </Card>
    )
  }

  if (!states || states.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-slate-400">
          <p className="text-sm">No state history available</p>
        </div>
      </Card>
    )
  }

  return (
    <Card>
      <div className="space-y-1 max-h-96 overflow-y-auto">
        {states.map((state) => {
          const isExpanded = expandedState === state.id
          const hasDelta = state.state_delta && Object.keys(state.state_delta).length > 0

          return (
            <div key={state.id} className="border-b border-slate-700/50 last:border-0">
              <button
                onClick={() => setExpandedState(isExpanded ? null : state.id)}
                className="w-full flex items-center gap-2 p-2 hover:bg-slate-700/30 rounded text-left"
              >
                {hasDelta ? (
                  isExpanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />
                ) : (
                  <div className="w-3.5" />
                )}
                <span className="text-xs text-slate-500 font-mono">#{state.sequence_num}</span>
                <span className="text-sm text-white truncate flex-1">{state.agent_id}</span>
                <span className="text-xs text-slate-500 font-mono flex items-center gap-1">
                  <Hash size={10} />
                  {state.state_hash.slice(0, 8)}
                </span>
              </button>
              {isExpanded && hasDelta && (
                <div className="px-6 pb-2">
                  <pre className="text-xs text-slate-400 bg-slate-800 p-2 rounded overflow-x-auto">
                    {JSON.stringify(state.state_delta, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
