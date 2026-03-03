'use client'

import { RefreshCw, TrendingDown } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import { AreaChart } from '../charts/AreaChart'
import type { LoopAnalytics } from '@/lib/api'

interface LoopAnalyticsCardProps {
  data?: LoopAnalytics
  isLoading?: boolean
}

export function LoopAnalyticsCard({ data, isLoading }: LoopAnalyticsCardProps) {
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
          <CardTitle>Loop Detection Trends</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-40 flex items-center justify-center text-zinc-400">
            No data available
          </div>
        </CardContent>
      </Card>
    )
  }

  const chartData = data.time_series.map((d) => ({
    date: d.date,
    loops: d.count,
  }))

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Loop Detection Trends</CardTitle>
          <div className="flex items-center gap-2 text-sm">
            <RefreshCw size={16} className="text-yellow-400" />
            <span className="text-zinc-300">{data.total_loops_detected} loops detected</span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <AreaChart
          data={chartData}
          xKey="date"
          yKey="loops"
          color="#eab308"
          height={180}
        />
        <div className="mt-4 flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <TrendingDown size={14} className="text-green-400" />
            <span className="text-zinc-400">Avg loop length:</span>
            <span className="font-medium text-green-400">{data.avg_loop_length} steps</span>
          </div>
          <span className="text-xs text-zinc-500">Last 30 days</span>
        </div>
      </CardContent>
    </Card>
  )
}
