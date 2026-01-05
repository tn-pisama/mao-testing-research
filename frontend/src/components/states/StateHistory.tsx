'use client'

import { useState } from 'react'
import type { State } from '@/lib/api'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface StateHistoryProps {
  states: State[]
  isLoading: boolean
}

export function StateHistory({ states, isLoading }: StateHistoryProps) {
  const [expandedState, setExpandedState] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-8 flex justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 max-h-96 overflow-y-auto scrollbar-thin">
      {states.map((state) => (
        <div key={state.id} className="border-b border-slate-700 last:border-b-0">
          <button
            onClick={() => setExpandedState(expandedState === state.id ? null : state.id)}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-700/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              {expandedState === state.id ? (
                <ChevronDown size={16} className="text-slate-400" />
              ) : (
                <ChevronRight size={16} className="text-slate-400" />
              )}
              <span className="text-sm font-medium text-white">{state.agent_id}</span>
              <span className="text-xs text-slate-400">#{state.sequence_num}</span>
            </div>
            <span className="text-xs font-mono text-slate-500">{state.state_hash}</span>
          </button>
          {expandedState === state.id && (
            <div className="px-4 pb-4 space-y-3">
              {/* LLM Interaction Content (Claude Code) */}
              {state.metadata?.user_input && (
                <div>
                  <div className="text-xs font-semibold text-blue-400 mb-1">User Input</div>
                  <pre className="bg-slate-900 rounded-lg p-3 text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap">
                    {state.metadata.user_input}
                  </pre>
                </div>
              )}
              {state.metadata?.reasoning && (
                <div>
                  <div className="text-xs font-semibold text-purple-400 mb-1">Reasoning (Extended Thinking)</div>
                  <pre className="bg-slate-900 rounded-lg p-3 text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-48 overflow-y-auto">
                    {state.metadata.reasoning}
                  </pre>
                </div>
              )}
              {state.metadata?.ai_output && (
                <div>
                  <div className="text-xs font-semibold text-green-400 mb-1">AI Output</div>
                  <pre className="bg-slate-900 rounded-lg p-3 text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap">
                    {state.metadata.ai_output}
                  </pre>
                </div>
              )}
              {/* Token usage */}
              {(state.metadata?.input_tokens || state.metadata?.output_tokens) && (
                <div className="flex gap-4 text-xs text-slate-400">
                  {state.metadata.model && <span>Model: {state.metadata.model}</span>}
                  {state.metadata.input_tokens && <span>Input: {state.metadata.input_tokens.toLocaleString()} tokens</span>}
                  {state.metadata.output_tokens && <span>Output: {state.metadata.output_tokens.toLocaleString()} tokens</span>}
                  {state.metadata.cost_usd && <span>Cost: ${state.metadata.cost_usd.toFixed(4)}</span>}
                </div>
              )}
              {/* State delta (fallback for non-Claude Code traces) */}
              {!state.metadata?.user_input && !state.metadata?.reasoning && !state.metadata?.ai_output && (
                <pre className="bg-slate-900 rounded-lg p-3 text-xs text-slate-300 overflow-x-auto">
                  {JSON.stringify(state.state_delta, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
