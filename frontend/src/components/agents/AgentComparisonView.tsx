'use client'

import { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts'
import { Bot, Check, X, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { AgentInfo } from './AgentCard'

interface AgentComparisonViewProps {
  agents: AgentInfo[]
}

const metrics = ['Speed', 'Accuracy', 'Efficiency', 'Reliability', 'Throughput', 'Cost']

function generateAgentMetrics(agent: AgentInfo) {
  const seed = agent.id.charCodeAt(0)
  return metrics.map((metric) => ({
    metric,
    value: Math.floor(((seed * metric.charCodeAt(0)) % 40) + 60),
  }))
}

const agentColors = [
  '#6366f1',
  '#8b5cf6',
  '#d946ef',
  '#ec4899',
  '#f43f5e',
  '#f97316',
]

export function AgentComparisonView({ agents }: AgentComparisonViewProps) {
  const [selectedAgents, setSelectedAgents] = useState<string[]>(
    agents.slice(0, 2).map((a) => a.id)
  )

  const toggleAgent = (agentId: string) => {
    setSelectedAgents((prev) =>
      prev.includes(agentId)
        ? prev.filter((id) => id !== agentId)
        : [...prev, agentId].slice(-4)
    )
  }

  const radarData = useMemo(() => {
    const metricsData = metrics.map((metric) => ({ metric }))
    selectedAgents.forEach((agentId) => {
      const agent = agents.find((a) => a.id === agentId)
      if (agent) {
        const agentMetrics = generateAgentMetrics(agent)
        agentMetrics.forEach((am, i) => {
          ;(metricsData[i] as any)[agent.name] = am.value
        })
      }
    })
    return metricsData
  }, [selectedAgents, agents])

  const selectedAgentData = useMemo(() => {
    return selectedAgents.map((id) => agents.find((a) => a.id === id)).filter(Boolean) as AgentInfo[]
  }, [selectedAgents, agents])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        {agents.map((agent, index) => {
          const isSelected = selectedAgents.includes(agent.id)
          return (
            <button
              key={agent.id}
              onClick={() => toggleAgent(agent.id)}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg border transition-all',
                isSelected
                  ? 'bg-slate-700 border-primary-500'
                  : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
              )}
            >
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: agentColors[index % agentColors.length] }}
              />
              <span className="text-sm text-white">{agent.name}</span>
              {isSelected && <Check size={14} className="text-primary-400" />}
            </button>
          )
        })}
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-4">Performance Radar</h3>
          <div className="h-80">
            <ResponsiveContainer>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(71, 85, 105, 0.5)" />
                <PolarAngleAxis
                  dataKey="metric"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                />
                <PolarRadiusAxis
                  angle={30}
                  domain={[0, 100]}
                  tick={{ fill: '#64748b', fontSize: 10 }}
                />
                {selectedAgentData.map((agent, index) => (
                  <Radar
                    key={agent.id}
                    name={agent.name}
                    dataKey={agent.name}
                    stroke={agentColors[agents.findIndex((a) => a.id === agent.id) % agentColors.length]}
                    fill={agentColors[agents.findIndex((a) => a.id === agent.id) % agentColors.length]}
                    fillOpacity={0.2}
                    strokeWidth={2}
                  />
                ))}
                <Legend />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-4">Side-by-Side Comparison</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="pb-3 text-left text-xs font-medium text-slate-400">Metric</th>
                  {selectedAgentData.map((agent, index) => (
                    <th key={agent.id} className="pb-3 text-right text-xs font-medium">
                      <span style={{ color: agentColors[agents.findIndex((a) => a.id === agent.id) % agentColors.length] }}>
                        {agent.name}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/50">
                <ComparisonRow
                  label="Tokens Used"
                  values={selectedAgentData.map((a) => a.tokensUsed.toLocaleString())}
                  agents={selectedAgentData}
                  allAgents={agents}
                />
                <ComparisonRow
                  label="Latency (ms)"
                  values={selectedAgentData.map((a) => a.latencyMs.toString())}
                  agents={selectedAgentData}
                  allAgents={agents}
                  lowerIsBetter
                />
                <ComparisonRow
                  label="Steps"
                  values={selectedAgentData.map((a) => a.stepCount.toString())}
                  agents={selectedAgentData}
                  allAgents={agents}
                />
                <ComparisonRow
                  label="Errors"
                  values={selectedAgentData.map((a) => a.errorCount.toString())}
                  agents={selectedAgentData}
                  allAgents={agents}
                  lowerIsBetter
                />
                <ComparisonRow
                  label="Status"
                  values={selectedAgentData.map((a) => a.status)}
                  agents={selectedAgentData}
                  allAgents={agents}
                  isStatus
                />
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

interface ComparisonRowProps {
  label: string
  values: string[]
  agents: AgentInfo[]
  allAgents: AgentInfo[]
  lowerIsBetter?: boolean
  isStatus?: boolean
}

function ComparisonRow({ label, values, agents, allAgents, lowerIsBetter, isStatus }: ComparisonRowProps) {
  const numericValues = values.map((v) => parseFloat(v.replace(/,/g, '')))
  const bestValue = lowerIsBetter
    ? Math.min(...numericValues.filter((n) => !isNaN(n)))
    : Math.max(...numericValues.filter((n) => !isNaN(n)))

  return (
    <tr>
      <td className="py-3 text-sm text-slate-400">{label}</td>
      {values.map((value, index) => {
        const numValue = parseFloat(value.replace(/,/g, ''))
        const isBest = !isNaN(numValue) && numValue === bestValue && !isStatus
        const statusColor = isStatus
          ? value === 'running'
            ? 'text-emerald-400'
            : value === 'failed'
            ? 'text-red-400'
            : 'text-slate-400'
          : 'text-white'

        return (
          <td
            key={index}
            className={clsx('py-3 text-right text-sm font-medium', statusColor, isBest && 'text-emerald-400')}
          >
            <div className="flex items-center justify-end gap-1">
              {value}
              {isBest && <TrendingUp size={12} className="text-emerald-400" />}
            </div>
          </td>
        )
      })}
    </tr>
  )
}
