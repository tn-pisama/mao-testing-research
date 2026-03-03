'use client'

import { useState } from 'react'
import { Clock, Cpu, DollarSign, CheckCircle, AlertTriangle, ChevronDown, ChevronRight, Loader2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import type { Trace, State } from '@/lib/api'

interface TraceViewerProps {
  trace?: Trace
  states?: State[]
  isLoading?: boolean
}

function getStatusBadge(status: string) {
  switch (status.toLowerCase()) {
    case 'completed':
      return <Badge variant="success"><CheckCircle size={12} className="mr-1" />Completed</Badge>
    case 'running':
    case 'in_progress':
      return <Badge variant="default"><Loader2 size={12} className="mr-1 animate-spin" />Running</Badge>
    case 'failed':
    case 'error':
      return <Badge variant="error"><AlertTriangle size={12} className="mr-1" />Failed</Badge>
    default:
      return <Badge variant="default">{status}</Badge>
  }
}

function formatCost(cents: number) {
  if (cents < 1) return '<$0.01'
  return `$${(cents / 100).toFixed(2)}`
}

function StateItem({ state, isFirst }: { state: State; isFirst: boolean }) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="relative">
      {/* Timeline connector */}
      {!isFirst && (
        <div className="absolute left-4 -top-4 w-0.5 h-4 bg-zinc-800" />
      )}

      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-start gap-3 p-3 bg-zinc-800/50 border border-zinc-800 rounded-lg cursor-pointer hover:bg-zinc-800 transition-all"
      >
        {/* Timeline dot */}
        <div className="flex-shrink-0 w-8 h-8 bg-blue-500/10 border border-zinc-700 rounded-full flex items-center justify-center text-sm font-medium text-blue-400 font-mono">
          {state.sequence_num}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <span className="text-white font-medium">{state.agent_id}</span>
              <span className="text-xs text-white/40 font-mono">
                {new Date(state.created_at).toLocaleTimeString()}
              </span>
            </div>
            <div className="flex items-center gap-3 text-sm text-white/60 font-mono">
              <span className="flex items-center gap-1">
                <Clock size={12} />
                {state.latency_ms}ms
              </span>
              <span className="flex items-center gap-1">
                <Cpu size={12} />
                {state.token_count} tokens
              </span>
              {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </div>
          </div>

          {state.metadata?.user_input && (
            <p className="text-sm text-white/60 font-mono truncate">
              {state.metadata.user_input}
            </p>
          )}
        </div>
      </div>

      {/* Expanded state details */}
      {isExpanded && (
        <div className="mt-2 ml-11 p-3 bg-zinc-950 rounded-lg border border-zinc-800">
          {state.metadata?.user_input && (
            <div className="mb-3">
              <p className="text-xs font-medium text-white/40 font-mono mb-1">Input</p>
              <p className="text-sm text-white font-mono">{state.metadata.user_input}</p>
            </div>
          )}

          {state.metadata?.reasoning && (
            <div className="mb-3">
              <p className="text-xs font-medium text-white/40 font-mono mb-1">Reasoning</p>
              <p className="text-sm text-white font-mono">{state.metadata.reasoning}</p>
            </div>
          )}

          {state.metadata?.ai_output && (
            <div className="mb-3">
              <p className="text-xs font-medium text-white/40 font-mono mb-1">Output</p>
              <p className="text-sm text-white font-mono whitespace-pre-wrap">{state.metadata.ai_output}</p>
            </div>
          )}

          <div className="pt-2 border-t border-zinc-800">
            <p className="text-xs font-medium text-white/40 font-mono mb-1">State Delta</p>
            <pre className="text-xs text-zinc-400 overflow-x-auto p-2 bg-zinc-950 rounded border border-zinc-800 font-mono">
              {JSON.stringify(state.state_delta, null, 2)}
            </pre>
          </div>

          <div className="mt-2 text-xs text-white/40 font-mono">
            Hash: {state.state_hash}
          </div>
        </div>
      )}
    </div>
  )
}

export function TraceViewer({ trace, states, isLoading }: TraceViewerProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="text-center py-8 text-white/60 font-mono">
          <Loader2 size={24} className="mx-auto mb-2 animate-spin" />
          <p className="text-sm">Loading trace details...</p>
        </div>
      </Card>
    )
  }

  if (!trace) {
    return (
      <Card>
        <div className="text-center py-8 text-white/60 font-mono">
          <p className="text-sm">No trace selected</p>
          <p className="text-xs mt-1 text-white/40">Select a trace to view its details</p>
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Trace Summary */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Trace Details</CardTitle>
            {getStatusBadge(trace.status)}
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-white/40 font-mono mb-1">Session ID</p>
              <p className="text-sm text-white font-mono truncate">{trace.session_id}</p>
            </div>
            <div>
              <p className="text-xs text-white/40 font-mono mb-1">Framework</p>
              <p className="text-sm text-white font-mono">{trace.framework}</p>
            </div>
            <div>
              <p className="text-xs text-white/40 font-mono mb-1">Total Tokens</p>
              <p className="text-sm text-white font-mono flex items-center gap-1">
                <Cpu size={14} className="text-white/60" />
                {trace.total_tokens.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-white/40 font-mono mb-1">Cost</p>
              <p className="text-sm text-white font-mono flex items-center gap-1">
                <DollarSign size={14} className="text-white/60" />
                {formatCost(trace.total_cost_cents)}
              </p>
            </div>
            <div>
              <p className="text-xs text-white/40 font-mono mb-1">Started</p>
              <p className="text-sm text-white font-mono">{new Date(trace.created_at).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-xs text-white/40 font-mono mb-1">Completed</p>
              <p className="text-sm text-white font-mono">
                {trace.completed_at ? new Date(trace.completed_at).toLocaleString() : '-'}
              </p>
            </div>
            <div>
              <p className="text-xs text-white/40 font-mono mb-1">States</p>
              <p className="text-sm text-white font-mono">{trace.state_count}</p>
            </div>
            <div>
              <p className="text-xs text-white/40 font-mono mb-1">Issues Detected</p>
              <p className={`text-sm font-mono ${trace.detection_count > 0 ? 'text-violet-500' : 'text-white'}`}>
                {trace.detection_count > 0 ? (
                  <span className="flex items-center gap-1">
                    <AlertTriangle size={14} />
                    {trace.detection_count}
                  </span>
                ) : (
                  '0'
                )}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* State Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>State Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {!states || states.length === 0 ? (
            <div className="text-center py-6 text-white/60 font-mono">
              <p className="text-sm">No states recorded for this trace</p>
            </div>
          ) : (
            <div className="space-y-4">
              {states
                .sort((a, b) => a.sequence_num - b.sequence_num)
                .map((state, index) => (
                  <StateItem key={state.id} state={state} isFirst={index === 0} />
                ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
