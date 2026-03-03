'use client'

import { Card } from '../ui/Card'
import { HeartPulse, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AgentInfo } from './index'

interface AgentHealthDashboardProps {
  agents?: AgentInfo[]
}

type HealthLevel = 'good' | 'warning' | 'critical'

const healthColors: Record<HealthLevel, string> = {
  good: 'bg-green-400',
  warning: 'bg-amber-400',
  critical: 'bg-red-400',
}

const healthTextColors: Record<HealthLevel, string> = {
  good: 'text-green-400',
  warning: 'text-amber-400',
  critical: 'text-red-400',
}

function getStatusHealth(status: AgentInfo['status']): HealthLevel {
  if (status === 'running' || status === 'completed') return 'good'
  if (status === 'idle' || status === 'waiting') return 'warning'
  return 'critical'
}

function getErrorHealth(errorCount: number, stepCount: number): HealthLevel {
  const rate = stepCount > 0 ? errorCount / stepCount : 0
  if (rate < 0.05) return 'good'
  if (rate < 0.15) return 'warning'
  return 'critical'
}

function getLatencyHealth(latencyMs: number): HealthLevel {
  if (latencyMs < 200) return 'good'
  if (latencyMs < 500) return 'warning'
  return 'critical'
}

function HealthBar({ level, label, value }: { level: HealthLevel; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', healthColors[level])} />
      <span className="text-xs text-zinc-500 w-14">{label}</span>
      <span className={cn('text-xs font-medium', healthTextColors[level])}>{value}</span>
    </div>
  )
}

export function AgentHealthDashboard({ agents }: AgentHealthDashboardProps) {
  if (!agents || agents.length === 0) {
    return (
      <Card>
        <div className="text-center py-12 text-zinc-400">
          <HeartPulse size={32} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No health data available</p>
          <p className="text-xs mt-1">Agent health metrics will appear here</p>
        </div>
      </Card>
    )
  }

  const healthyCount = agents.filter((a) => {
    const statusOk = getStatusHealth(a.status) === 'good'
    const errorsOk = getErrorHealth(a.errorCount, a.stepCount) !== 'critical'
    const latencyOk = getLatencyHealth(a.latencyMs) !== 'critical'
    return statusOk && errorsOk && latencyOk
  }).length

  const healthScore = Math.round((healthyCount / agents.length) * 100)

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <HeartPulse size={20} className={cn(
              healthScore >= 80 ? 'text-green-400' : healthScore >= 50 ? 'text-amber-400' : 'text-red-400'
            )} />
            <div>
              <div className="text-sm font-medium text-white">System Health</div>
              <div className="text-xs text-zinc-500">{healthyCount} of {agents.length} agents healthy</div>
            </div>
          </div>
          <div className={cn(
            'text-2xl font-bold',
            healthScore >= 80 ? 'text-green-400' : healthScore >= 50 ? 'text-amber-400' : 'text-red-400'
          )}>
            {healthScore}%
          </div>
        </div>
      </Card>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {agents.map((agent) => {
          const statusLevel = getStatusHealth(agent.status)
          const errorLevel = getErrorHealth(agent.errorCount, agent.stepCount)
          const latencyLevel = getLatencyHealth(agent.latencyMs)
          const errorRate = agent.stepCount > 0
            ? ((agent.errorCount / agent.stepCount) * 100).toFixed(1)
            : '0.0'

          const Icon = statusLevel === 'good' ? CheckCircle
            : statusLevel === 'warning' ? AlertTriangle
            : XCircle

          return (
            <Card key={agent.id}>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium text-white">{agent.name}</div>
                    <div className="text-xs text-zinc-500 capitalize">{agent.type}</div>
                  </div>
                  <Icon size={16} className={healthTextColors[statusLevel]} />
                </div>
                <div className="space-y-1.5">
                  <HealthBar level={statusLevel} label="Status" value={agent.status} />
                  <HealthBar level={errorLevel} label="Errors" value={`${errorRate}%`} />
                  <HealthBar level={latencyLevel} label="Latency" value={`${agent.latencyMs}ms`} />
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
