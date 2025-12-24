'use client'

import { useMemo } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  LineChart,
  Line,
} from 'recharts'
import { clsx } from 'clsx'
import { AgentInfo } from './AgentCard'

interface AgentPerformanceChartProps {
  agent: AgentInfo
}

function generatePerformanceData(agent: AgentInfo) {
  const now = Date.now()
  return Array.from({ length: 20 }, (_, i) => ({
    time: new Date(now - (19 - i) * 60000).toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit' 
    }),
    tokens: Math.floor(Math.random() * 500) + 100,
    latency: Math.floor(Math.random() * 300) + 50,
    throughput: Math.floor(Math.random() * 10) + 1,
  }))
}

function generateToolData() {
  return [
    { name: 'search', calls: 45, color: '#6366f1' },
    { name: 'analyze', calls: 32, color: '#8b5cf6' },
    { name: 'generate', calls: 28, color: '#d946ef' },
    { name: 'validate', calls: 21, color: '#ec4899' },
    { name: 'fetch', calls: 15, color: '#f43f5e' },
  ]
}

export function AgentPerformanceChart({ agent }: AgentPerformanceChartProps) {
  const performanceData = useMemo(() => generatePerformanceData(agent), [agent])
  const toolData = useMemo(() => generateToolData(), [])

  return (
    <div className="space-y-6">
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-4">Token Usage Over Time</h3>
          <div className="h-64">
            <ResponsiveContainer>
              <AreaChart data={performanceData}>
                <defs>
                  <linearGradient id="tokenGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(71, 85, 105, 0.3)" vertical={false} />
                <XAxis 
                  dataKey="time" 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  interval="preserveStartEnd"
                />
                <YAxis 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  width={40}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                  }}
                  labelStyle={{ color: '#f1f5f9' }}
                />
                <Area
                  type="monotone"
                  dataKey="tokens"
                  stroke="#6366f1"
                  strokeWidth={2}
                  fill="url(#tokenGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-4">Latency Distribution</h3>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(71, 85, 105, 0.3)" vertical={false} />
                <XAxis 
                  dataKey="time" 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  interval="preserveStartEnd"
                />
                <YAxis 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  width={40}
                  unit="ms"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                  }}
                  labelStyle={{ color: '#f1f5f9' }}
                />
                <Line
                  type="monotone"
                  dataKey="latency"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: '#22c55e' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-4">Tool Calls Distribution</h3>
          <div className="h-48">
            <ResponsiveContainer>
              <BarChart data={toolData} layout="vertical">
                <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} />
                <YAxis 
                  type="category" 
                  dataKey="name" 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  width={60}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="calls" radius={[0, 4, 4, 0]}>
                  {toolData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="lg:col-span-2 p-6 rounded-xl bg-slate-800/50 border border-slate-700">
          <h3 className="text-sm font-semibold text-white mb-4">Throughput (requests/min)</h3>
          <div className="h-48">
            <ResponsiveContainer>
              <AreaChart data={performanceData}>
                <defs>
                  <linearGradient id="throughputGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(71, 85, 105, 0.3)" vertical={false} />
                <XAxis 
                  dataKey="time" 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#64748b', fontSize: 10 }}
                />
                <YAxis 
                  axisLine={false} 
                  tickLine={false} 
                  tick={{ fill: '#64748b', fontSize: 10 }}
                  width={30}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#1e293b',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="throughput"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  fill="url(#throughputGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
