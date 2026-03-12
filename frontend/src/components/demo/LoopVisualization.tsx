'use client'

import { Card, CardContent } from '../ui/Card'
import { RefreshCw } from 'lucide-react'
import type { DemoState } from '@/lib/demo-fixtures'

interface LoopVisualizationProps {
  states: DemoState[]
  agents?: unknown[]
  data?: unknown
}

export function LoopVisualization({ states }: LoopVisualizationProps) {
  if (!states || states.length === 0) {
    return (
      <Card className="border-zinc-800 bg-zinc-900">
        <div className="text-center py-12 text-zinc-500">
          <RefreshCw size={32} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No loop data available</p>
        </div>
      </Card>
    )
  }

  // Find repeated state hashes to highlight loop cycles
  const hashCounts: Record<string, number> = {}
  states.forEach((s) => {
    if (s.state_hash) {
      hashCounts[s.state_hash] = (hashCounts[s.state_hash] || 0) + 1
    }
  })
  const repeatedHashes = new Set(
    Object.entries(hashCounts)
      .filter(([, count]) => count > 1)
      .map(([hash]) => hash)
  )

  return (
    <Card className="border-zinc-800 bg-zinc-900">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-4">
          <RefreshCw size={16} className="text-amber-400" />
          <h3 className="text-sm font-medium text-zinc-200">Agent State Timeline</h3>
          <span className="text-xs text-zinc-500 ml-auto">
            {states.length} steps
          </span>
        </div>

        <div className="space-y-1">
          {states.map((state, i) => {
            const isRepeated = state.state_hash ? repeatedHashes.has(state.state_hash) : false
            const prevState = i > 0 ? states[i - 1] : null
            const isBacktrack =
              prevState &&
              state.state_hash &&
              prevState.state_hash !== state.state_hash &&
              states.slice(0, i - 1).some((s) => s.state_hash === state.state_hash)

            return (
              <div
                key={state.id}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-xs transition-colors ${
                  isBacktrack
                    ? 'bg-red-500/10 border border-red-500/20'
                    : isRepeated
                    ? 'bg-amber-500/5 border border-amber-500/10'
                    : 'bg-zinc-800/50'
                }`}
              >
                {/* Step number */}
                <span className="w-6 text-right text-zinc-600 font-mono">{i}</span>

                {/* Connection line */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-2.5 h-2.5 rounded-full ${
                      isBacktrack
                        ? 'bg-red-500'
                        : isRepeated
                        ? 'bg-amber-500'
                        : 'bg-zinc-600'
                    }`}
                  />
                </div>

                {/* Agent + Action */}
                <div className="flex-1 min-w-0">
                  <span className="text-zinc-400">{state.agent_id}</span>
                  <span className="text-zinc-600 mx-1">/</span>
                  <span className="text-zinc-300">{state.action}</span>
                </div>

                {/* Hash badge */}
                {state.state_hash && (
                  <span
                    className={`font-mono px-1.5 py-0.5 rounded ${
                      isRepeated
                        ? 'bg-amber-500/20 text-amber-400'
                        : 'bg-zinc-800 text-zinc-500'
                    }`}
                  >
                    {state.state_hash.slice(0, 10)}
                  </span>
                )}

                {/* Token count */}
                <span className="text-zinc-600 w-12 text-right">
                  {state.token_count}t
                </span>

                {/* Loop indicator */}
                {isBacktrack && (
                  <RefreshCw size={12} className="text-red-400 animate-spin" />
                )}
              </div>
            )
          })}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 mt-4 pt-3 border-t border-zinc-800">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-red-500" />
            <span className="text-xs text-zinc-500">Loop cycle</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-xs text-zinc-500">Repeated hash</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-zinc-600" />
            <span className="text-xs text-zinc-500">Unique state</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
