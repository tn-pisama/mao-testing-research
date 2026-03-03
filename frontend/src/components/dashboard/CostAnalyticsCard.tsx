'use client'

import { DollarSign, Zap } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import { BarChart } from '../charts/BarChart'
import type { CostAnalytics } from '@/lib/api'

interface CostAnalyticsCardProps {
  data?: CostAnalytics
  isLoading?: boolean
}

export function CostAnalyticsCard({ data, isLoading }: CostAnalyticsCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-64 animate-pulse bg-zinc-700 rounded-lg" />
      </Card>
    )
  }

  if (!data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Cost Analytics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-40 flex items-center justify-center text-zinc-400">
            No data available
          </div>
        </CardContent>
      </Card>
    )
  }

  const chartData = Object.entries(data.cost_by_framework).map(([name, cost]) => ({
    name,
    cost: cost / 100, // Convert cents to dollars
  }))

  const totalCost = data.total_cost_cents / 100

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Cost Analytics</CardTitle>
          <div className="flex items-center gap-2 text-sm">
            <DollarSign size={16} className="text-green-400" />
            <span className="text-zinc-300">${totalCost.toFixed(2)} total</span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <BarChart
          data={chartData}
          xKey="name"
          yKey="cost"
          color="#10b981"
          height={180}
        />
        <div className="mt-4 flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-blue-400" />
            <span className="text-zinc-400">Total tokens:</span>
            <span className="font-medium text-blue-400">{data.total_tokens.toLocaleString()}</span>
          </div>
          <span className="text-xs text-zinc-500">Last 30 days</span>
        </div>
      </CardContent>
    </Card>
  )
}
