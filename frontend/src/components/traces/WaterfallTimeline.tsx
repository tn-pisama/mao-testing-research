'use client'

import { useState, useMemo } from 'react'
import { Clock, Cpu, Zap } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import type { State } from '@/lib/api'

const AGENT_COLORS = [
  '#3b82f6', // blue
  '#8b5cf6', // purple
  '#ec4899', // pink
  '#f59e0b', // amber
  '#22c55e', // green
  '#06b6d4', // cyan
  '#f97316', // orange
  '#6366f1', // indigo
]

interface WaterfallTimelineProps {
  states: State[]
  onStateClick?: (state: State) => void
  selectedStateId?: string
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function WaterfallTimeline({ states, onStateClick, selectedStateId }: WaterfallTimelineProps) {
  const [hoveredStateId, setHoveredStateId] = useState<string | null>(null)

  const { swimlanes, timeRange, agentColorMap, timeMarkers } = useMemo(() => {
    if (!states || states.length === 0) {
      return { swimlanes: [], timeRange: { start: 0, end: 0, duration: 0 }, agentColorMap: new Map(), timeMarkers: [] }
    }

    const sorted = [...states].sort((a, b) => a.sequence_num - b.sequence_num)

    // Assign colors to agents
    const uniqueAgents = [...new Set(sorted.map(s => s.agent_id))]
    const colorMap = new Map<string, string>()
    uniqueAgents.forEach((agent, i) => {
      colorMap.set(agent, AGENT_COLORS[i % AGENT_COLORS.length])
    })

    // Calculate time range
    const times = sorted.map(s => new Date(s.created_at).getTime())
    const traceStart = Math.min(...times)
    const traceEnd = Math.max(...sorted.map(s => new Date(s.created_at).getTime() + s.latency_ms))
    const totalDuration = Math.max(traceEnd - traceStart, 1)

    // Build swimlanes: group states by agent_id, preserving order
    const laneMap = new Map<string, State[]>()
    uniqueAgents.forEach(agent => laneMap.set(agent, []))
    sorted.forEach(state => {
      laneMap.get(state.agent_id)?.push(state)
    })

    const lanes = uniqueAgents.map(agent => ({
      agentId: agent,
      states: laneMap.get(agent) || [],
      color: colorMap.get(agent) || '#64748b',
    }))

    // Time markers (5-6 ticks)
    const tickCount = 5
    const markers: number[] = []
    for (let i = 0; i <= tickCount; i++) {
      markers.push(traceStart + (totalDuration * i) / tickCount)
    }

    return {
      swimlanes: lanes,
      timeRange: { start: traceStart, end: traceEnd, duration: totalDuration },
      agentColorMap: colorMap,
      timeMarkers: markers,
    }
  }, [states])

  if (!states || states.length === 0) {
    return (
      <Card>
        <div className="text-center py-8 text-white/60 font-mono">
          <p className="text-sm">No state data for waterfall view</p>
        </div>
      </Card>
    )
  }

  const getBarPosition = (state: State) => {
    const stateStart = new Date(state.created_at).getTime()
    const left = ((stateStart - timeRange.start) / timeRange.duration) * 100
    const width = Math.max((state.latency_ms / timeRange.duration) * 100, 0.5) // min 0.5% width
    return { left: `${left}%`, width: `${width}%` }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Waterfall Timeline</CardTitle>
          <span className="text-xs text-slate-500 font-mono">
            Total: {formatDuration(timeRange.duration)}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {/* Time axis header */}
        <div className="flex mb-2">
          <div className="w-32 flex-shrink-0" />
          <div className="flex-1 relative h-6">
            {timeMarkers.map((time, i) => {
              const left = ((time - timeRange.start) / timeRange.duration) * 100
              return (
                <div
                  key={i}
                  className="absolute text-[10px] text-slate-500 font-mono"
                  style={{ left: `${left}%`, transform: 'translateX(-50%)' }}
                >
                  {formatDuration(time - timeRange.start)}
                </div>
              )
            })}
          </div>
        </div>

        {/* Swimlanes */}
        <div className="space-y-1">
          {swimlanes.map(lane => (
            <div key={lane.agentId} className="flex items-center group">
              {/* Agent label */}
              <div className="w-32 flex-shrink-0 pr-3 text-right">
                <span
                  className="text-xs font-mono truncate inline-block max-w-full"
                  style={{ color: lane.color }}
                  title={lane.agentId}
                >
                  {lane.agentId}
                </span>
              </div>

              {/* Bar area */}
              <div className="flex-1 relative h-8 bg-slate-800/50 rounded">
                {/* Grid lines */}
                {timeMarkers.map((time, i) => {
                  const left = ((time - timeRange.start) / timeRange.duration) * 100
                  return (
                    <div
                      key={i}
                      className="absolute top-0 bottom-0 w-px bg-slate-700/50"
                      style={{ left: `${left}%` }}
                    />
                  )
                })}

                {/* State bars */}
                {lane.states.map(state => {
                  const pos = getBarPosition(state)
                  const isHovered = hoveredStateId === state.id
                  const isSelected = selectedStateId === state.id
                  return (
                    <div
                      key={state.id}
                      className="absolute top-1 bottom-1 rounded cursor-pointer transition-all"
                      style={{
                        left: pos.left,
                        width: pos.width,
                        minWidth: '4px',
                        backgroundColor: lane.color,
                        opacity: isHovered || isSelected ? 1 : 0.7,
                        boxShadow: isSelected ? `0 0 8px ${lane.color}` : isHovered ? `0 0 4px ${lane.color}` : 'none',
                      }}
                      onMouseEnter={() => setHoveredStateId(state.id)}
                      onMouseLeave={() => setHoveredStateId(null)}
                      onClick={() => onStateClick?.(state)}
                      title={`#${state.sequence_num} ${state.agent_id} — ${state.latency_ms}ms, ${state.token_count} tokens`}
                    />
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Hover detail tooltip */}
        {hoveredStateId && (() => {
          const state = states.find(s => s.id === hoveredStateId)
          if (!state) return null
          return (
            <div className="mt-3 p-3 bg-slate-800 rounded-lg border border-slate-700">
              <div className="flex items-center gap-4 text-sm">
                <span className="font-mono text-white">
                  #{state.sequence_num} {state.agent_id}
                </span>
                <span className="text-slate-400 font-mono flex items-center gap-1">
                  <Clock size={12} />
                  {formatDuration(state.latency_ms)}
                </span>
                <span className="text-slate-400 font-mono flex items-center gap-1">
                  <Cpu size={12} />
                  {state.token_count.toLocaleString()} tokens
                </span>
                <span className="text-slate-500 font-mono text-xs">
                  {new Date(state.created_at).toLocaleTimeString()}
                </span>
              </div>
              {state.metadata?.ai_output && (
                <p className="text-xs text-slate-500 font-mono mt-1 truncate">
                  {state.metadata.ai_output.slice(0, 120)}...
                </p>
              )}
            </div>
          )
        })()}
      </CardContent>
    </Card>
  )
}
