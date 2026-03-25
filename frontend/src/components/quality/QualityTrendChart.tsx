'use client'

import { cn } from '@/lib/utils'
import { TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react'
import { Card, CardContent } from '../ui/Card'

interface TrendPoint {
  timestamp: string
  score: number
  detections: number
}

interface QualityTrendChartProps {
  data: TrendPoint[]
  title?: string
  height?: number
}

function getTrend(data: TrendPoint[]): { direction: 'up' | 'down' | 'flat'; change: number } {
  if (data.length < 2) return { direction: 'flat', change: 0 }
  const first = data.slice(0, Math.ceil(data.length / 3))
  const last = data.slice(-Math.ceil(data.length / 3))
  const firstAvg = first.reduce((s, p) => s + p.score, 0) / first.length
  const lastAvg = last.reduce((s, p) => s + p.score, 0) / last.length
  const change = lastAvg - firstAvg
  if (Math.abs(change) < 0.05) return { direction: 'flat', change }
  return { direction: change > 0 ? 'up' : 'down', change }
}

function MiniSparkline({ data, height = 40 }: { data: TrendPoint[]; height?: number }) {
  if (data.length < 2) return null

  const width = 200
  const padding = 4
  const scores = data.map(d => d.score)
  const min = Math.min(...scores) - 0.05
  const max = Math.max(...scores) + 0.05
  const range = max - min || 1

  const points = data.map((d, i) => {
    const x = padding + (i / (data.length - 1)) * (width - 2 * padding)
    const y = height - padding - ((d.score - min) / range) * (height - 2 * padding)
    return `${x},${y}`
  }).join(' ')

  const lastScore = scores[scores.length - 1]
  const color = lastScore >= 0.7 ? '#22c55e' : lastScore >= 0.5 ? '#f59e0b' : '#ef4444'

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Last point dot */}
      {data.length > 0 && (
        <circle
          cx={padding + ((data.length - 1) / (data.length - 1)) * (width - 2 * padding)}
          cy={height - padding - ((lastScore - min) / range) * (height - 2 * padding)}
          r="3"
          fill={color}
        />
      )}
    </svg>
  )
}

export function QualityTrendChart({ data, title = 'Quality Trend', height = 48 }: QualityTrendChartProps) {
  const trend = getTrend(data)
  const latest = data.length > 0 ? data[data.length - 1].score : 0
  const totalDetections = data.reduce((s, p) => s + p.detections, 0)

  const TrendIcon = trend.direction === 'up' ? TrendingUp
    : trend.direction === 'down' ? TrendingDown
    : Minus

  const trendColor = trend.direction === 'up' ? 'text-green-400'
    : trend.direction === 'down' ? 'text-red-400'
    : 'text-zinc-400'

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
          <div className={cn('flex items-center gap-1 text-xs', trendColor)}>
            <TrendIcon className="w-3.5 h-3.5" />
            <span>{trend.direction === 'flat' ? 'Stable' : `${trend.change > 0 ? '+' : ''}${(trend.change * 100).toFixed(0)}%`}</span>
          </div>
        </div>

        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-2xl font-bold text-zinc-100 font-mono">
              {(latest * 100).toFixed(0)}%
            </div>
            <div className="text-[10px] text-zinc-500 mt-0.5">
              {totalDetections} detections across {data.length} samples
            </div>
          </div>
          <MiniSparkline data={data} height={height} />
        </div>

        {latest < 0.5 && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-amber-400 bg-amber-500/10 rounded px-2 py-1">
            <AlertTriangle className="w-3 h-3" />
            <span>Quality below threshold — healing recommended</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// Simple timeline for use in quality detail pages
export function QualityTimeline({ data }: { data: TrendPoint[] }) {
  if (data.length === 0) {
    return (
      <div className="text-xs text-zinc-500 text-center py-4">
        No quality data yet. Run a detection to see trends.
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {data.slice(-10).map((point, i) => {
        const scoreColor = point.score >= 0.7 ? 'text-green-400' : point.score >= 0.5 ? 'text-amber-400' : 'text-red-400'
        return (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="text-zinc-500 w-16 shrink-0 font-mono">
              {new Date(point.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
            <div className="flex-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={cn('h-full rounded-full', point.score >= 0.7 ? 'bg-green-500' : point.score >= 0.5 ? 'bg-amber-500' : 'bg-red-500')}
                style={{ width: `${Math.round(point.score * 100)}%` }}
              />
            </div>
            <span className={cn('font-mono w-8 text-right', scoreColor)}>
              {(point.score * 100).toFixed(0)}%
            </span>
            <span className="text-zinc-600 w-6 text-right">{point.detections}d</span>
          </div>
        )
      })}
    </div>
  )
}
