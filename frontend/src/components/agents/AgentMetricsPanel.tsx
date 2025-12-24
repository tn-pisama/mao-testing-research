'use client'

import { clsx } from 'clsx'
import { TrendingUp, TrendingDown, Minus, Zap, Clock, DollarSign, AlertTriangle, Bot } from 'lucide-react'

interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  icon: typeof Zap
  iconColor: string
}

function MetricCard({ title, value, subtitle, trend, trendValue, icon: Icon, iconColor }: MetricCardProps) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus
  const trendColor = trend === 'up' ? 'text-emerald-400' : trend === 'down' ? 'text-red-400' : 'text-slate-400'

  return (
    <div className="bg-slate-800/50 rounded-xl border border-slate-700 p-4">
      <div className="flex items-start justify-between mb-3">
        <div className={clsx('p-2 rounded-lg', iconColor.replace('text-', 'bg-').replace('-400', '-500/20'))}>
          <Icon size={18} className={iconColor} />
        </div>
        {trend && (
          <div className={clsx('flex items-center gap-1 text-xs', trendColor)}>
            <TrendIcon size={14} />
            <span>{trendValue}</span>
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-white mb-1">{value}</div>
      <div className="text-sm text-slate-400">{title}</div>
      {subtitle && <div className="text-xs text-slate-500 mt-1">{subtitle}</div>}
    </div>
  )
}

interface AgentMetrics {
  totalAgents: number
  activeAgents: number
  totalTokens: number
  avgLatencyMs: number
  totalCostCents: number
  errorRate: number
  loopsDetected: number
  avgStepsPerTrace: number
}

interface AgentMetricsPanelProps {
  metrics: AgentMetrics
  previousMetrics?: AgentMetrics
}

function calculateTrend(current: number, previous?: number): { trend: 'up' | 'down' | 'neutral'; value: string } {
  if (!previous || previous === 0) return { trend: 'neutral', value: '—' }
  const change = ((current - previous) / previous) * 100
  if (Math.abs(change) < 1) return { trend: 'neutral', value: '0%' }
  return {
    trend: change > 0 ? 'up' : 'down',
    value: `${Math.abs(change).toFixed(1)}%`,
  }
}

export function AgentMetricsPanel({ metrics, previousMetrics }: AgentMetricsPanelProps) {
  const tokenTrend = calculateTrend(metrics.totalTokens, previousMetrics?.totalTokens)
  const latencyTrend = calculateTrend(metrics.avgLatencyMs, previousMetrics?.avgLatencyMs)
  const costTrend = calculateTrend(metrics.totalCostCents, previousMetrics?.totalCostCents)
  const errorTrend = calculateTrend(metrics.errorRate, previousMetrics?.errorRate)

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard
        title="Active Agents"
        value={`${metrics.activeAgents}/${metrics.totalAgents}`}
        subtitle="Currently processing"
        icon={Bot}
        iconColor="text-emerald-400"
      />
      <MetricCard
        title="Total Tokens"
        value={metrics.totalTokens.toLocaleString()}
        subtitle="This session"
        trend={tokenTrend.trend}
        trendValue={tokenTrend.value}
        icon={Zap}
        iconColor="text-blue-400"
      />
      <MetricCard
        title="Avg Latency"
        value={`${metrics.avgLatencyMs}ms`}
        subtitle="Per agent step"
        trend={latencyTrend.trend === 'up' ? 'down' : latencyTrend.trend === 'down' ? 'up' : 'neutral'}
        trendValue={latencyTrend.value}
        icon={Clock}
        iconColor="text-amber-400"
      />
      <MetricCard
        title="Estimated Cost"
        value={`$${(metrics.totalCostCents / 100).toFixed(2)}`}
        subtitle="This session"
        trend={costTrend.trend}
        trendValue={costTrend.value}
        icon={DollarSign}
        iconColor="text-purple-400"
      />
      <MetricCard
        title="Error Rate"
        value={`${metrics.errorRate.toFixed(1)}%`}
        subtitle="Of all requests"
        trend={errorTrend.trend === 'up' ? 'down' : errorTrend.trend === 'down' ? 'up' : 'neutral'}
        trendValue={errorTrend.value}
        icon={AlertTriangle}
        iconColor="text-red-400"
      />
      <MetricCard
        title="Loops Detected"
        value={metrics.loopsDetected}
        subtitle="Infinite loop patterns"
        icon={AlertTriangle}
        iconColor="text-orange-400"
      />
      <MetricCard
        title="Avg Steps/Trace"
        value={metrics.avgStepsPerTrace.toFixed(1)}
        subtitle="Agent steps per trace"
        icon={Zap}
        iconColor="text-cyan-400"
      />
      <MetricCard
        title="Active Agents"
        value={`${((metrics.activeAgents / metrics.totalAgents) * 100).toFixed(0)}%`}
        subtitle="Utilization rate"
        icon={Bot}
        iconColor="text-indigo-400"
      />
    </div>
  )
}
