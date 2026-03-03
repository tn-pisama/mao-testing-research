'use client'

import { useState } from 'react'
import { Card } from '../ui/Card'
import { GitCompare } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentInfo } from './index'

interface AgentComparisonViewProps {
  agents?: AgentInfo[]
}

const statusColors: Record<string, string> = {
  running: 'text-green-400',
  idle: 'text-zinc-400',
  completed: 'text-blue-400',
  failed: 'text-red-400',
  waiting: 'text-amber-400',
}

interface MetricRow {
  label: string
  getValue: (agent: AgentInfo) => number | string
  getNumeric?: (agent: AgentInfo) => number
  format?: (value: number) => string
}

const metrics: MetricRow[] = [
  {
    label: 'Steps',
    getValue: (a) => a.stepCount,
    getNumeric: (a) => a.stepCount,
  },
  {
    label: 'Tokens',
    getValue: (a) => a.tokensUsed >= 1000 ? `${(a.tokensUsed / 1000).toFixed(1)}k` : a.tokensUsed,
    getNumeric: (a) => a.tokensUsed,
  },
  {
    label: 'Latency',
    getValue: (a) => `${a.latencyMs}ms`,
    getNumeric: (a) => a.latencyMs,
  },
  {
    label: 'Errors',
    getValue: (a) => a.errorCount,
    getNumeric: (a) => a.errorCount,
  },
  {
    label: 'Status',
    getValue: (a) => a.status,
  },
]

export function AgentComparisonView({ agents }: AgentComparisonViewProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set())

  if (!agents || agents.length === 0) {
    return (
      <Card>
        <div className="text-center py-12 text-zinc-400">
          <GitCompare size={32} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">Select agents to compare</p>
          <p className="text-xs mt-1">Side-by-side agent metrics comparison</p>
        </div>
      </Card>
    )
  }

  const toggleAgent = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else if (next.size < 4) {
        next.add(id)
      }
      return next
    })
  }

  const selectedAgents = agents.filter((a) => selected.has(a.id))

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center gap-2 mb-3">
          <GitCompare size={16} className="text-zinc-400" />
          <span className="text-sm font-medium text-white">Select Agents</span>
          <span className="text-xs text-zinc-500">(max 4)</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {agents.map((agent) => (
            <button
              key={agent.id}
              onClick={() => toggleAgent(agent.id)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm border transition-all',
                selected.has(agent.id)
                  ? 'bg-blue-500/20 text-blue-400 border-blue-500/50'
                  : 'bg-zinc-800/50 text-zinc-400 border-zinc-700/50 hover:border-zinc-600'
              )}
            >
              {agent.name}
            </button>
          ))}
        </div>
      </Card>

      {selectedAgents.length === 0 ? (
        <Card>
          <div className="text-center py-8 text-zinc-400">
            <p className="text-sm">Click agents above to compare</p>
          </div>
        </Card>
      ) : (
        <Card padding="none">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-700/50">
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase w-24">
                    Metric
                  </th>
                  {selectedAgents.map((agent) => (
                    <th key={agent.id} className="px-4 py-3 text-left text-xs font-medium text-zinc-400">
                      {agent.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {metrics.map((metric) => {
                  const numericValues = metric.getNumeric
                    ? selectedAgents.map((a) => metric.getNumeric!(a))
                    : null
                  const maxValue = numericValues ? Math.max(...numericValues, 1) : 0

                  return (
                    <tr key={metric.label}>
                      <td className="px-4 py-3 text-xs text-zinc-500">{metric.label}</td>
                      {selectedAgents.map((agent) => {
                        const value = metric.getValue(agent)
                        const numericVal = metric.getNumeric?.(agent)
                        const isStatus = metric.label === 'Status'

                        return (
                          <td key={agent.id} className="px-4 py-3">
                            <div className="space-y-1">
                              <span className={cn(
                                'text-sm font-medium',
                                isStatus
                                  ? statusColors[String(value)] ?? 'text-zinc-400'
                                  : 'text-white'
                              )}>
                                {String(value)}
                              </span>
                              {numericVal !== undefined && maxValue > 0 && (
                                <div className="w-full bg-zinc-800 rounded-full h-1">
                                  <div
                                    className="bg-blue-500 h-1 rounded-full transition-all"
                                    style={{ width: `${(numericVal / maxValue) * 100}%` }}
                                  />
                                </div>
                              )}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
