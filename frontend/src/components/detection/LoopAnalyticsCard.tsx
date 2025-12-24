'use client'

import { RefreshCcw } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import type { LoopAnalytics } from '@/lib/api'

interface LoopAnalyticsCardProps {
  data?: LoopAnalytics
  isLoading: boolean
}

export function LoopAnalyticsCard({ data, isLoading }: LoopAnalyticsCardProps) {
  if (isLoading) {
    return (
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-slate-700 rounded w-1/3"></div>
          <div className="h-32 bg-slate-700 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
      <div className="flex items-center gap-2 mb-4">
        <RefreshCcw className="text-primary-400" size={20} />
        <h3 className="text-lg font-semibold text-white">Loop Detection</h3>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div>
          <div className="text-2xl font-bold text-white">{data?.total_loops_detected || 0}</div>
          <div className="text-sm text-slate-400">Total Loops</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-white">{data?.avg_loop_length?.toFixed(1) || 0}</div>
          <div className="text-sm text-slate-400">Avg Length</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-white">
            {data?.top_agents_in_loops?.[0]?.agent_id?.slice(0, 8) || '-'}
          </div>
          <div className="text-sm text-slate-400">Top Agent</div>
        </div>
      </div>

      {data?.time_series && data.time_series.length > 0 && (
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.time_series}>
              <defs>
                <linearGradient id="loopGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" hide />
              <YAxis hide />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#94a3b8' }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#0ea5e9"
                fill="url(#loopGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
