'use client'

import { DollarSign } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import type { CostAnalytics } from '@/lib/api'

interface CostAnalyticsCardProps {
  data?: CostAnalytics
  isLoading: boolean
}

export function CostAnalyticsCard({ data, isLoading }: CostAnalyticsCardProps) {
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

  const totalDollars = (data?.total_cost_cents || 0) / 100

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
      <div className="flex items-center gap-2 mb-4">
        <DollarSign className="text-success-500" size={20} />
        <h3 className="text-lg font-semibold text-white">Cost Analytics</h3>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div>
          <div className="text-2xl font-bold text-white">${totalDollars.toFixed(2)}</div>
          <div className="text-sm text-slate-400">Total Cost</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-white">
            {(data?.total_tokens || 0).toLocaleString()}
          </div>
          <div className="text-sm text-slate-400">Total Tokens</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-white">
            ${((data?.top_expensive_traces?.[0]?.cost_cents || 0) / 100).toFixed(2)}
          </div>
          <div className="text-sm text-slate-400">Most Expensive</div>
        </div>
      </div>

      {data?.cost_by_day && data.cost_by_day.length > 0 && (
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.cost_by_day}>
              <XAxis dataKey="date" hide />
              <YAxis hide />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(value: number) => [`$${(value / 100).toFixed(2)}`, 'Cost']}
              />
              <Bar dataKey="cost_cents" fill="#22c55e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
