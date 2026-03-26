'use client'

import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Skeleton } from '@/components/ui/Skeleton'
import type { OrchestrationQualityResponse } from '@/lib/api/traces'

function ScoreBar({ label, value, threshold = 0.5 }: { label: string; value: number; threshold?: number }) {
  const pct = Math.round(value * 100)
  const color = value >= 0.7 ? 'bg-green-500' : value >= threshold ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-3">
      <span className="w-44 text-sm text-zinc-400 truncate">{label}</span>
      <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-12 text-right text-sm font-mono text-zinc-300">{pct}%</span>
    </div>
  )
}

function OverallBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const bg = score >= 0.7 ? 'bg-green-500/10 border-green-500/30 text-green-400'
    : score >= 0.5 ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
    : 'bg-red-500/10 border-red-500/30 text-red-400'
  const label = score >= 0.7 ? 'Good' : score >= 0.5 ? 'Fair' : 'Poor'
  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl border ${bg}`}>
      <span className="text-3xl font-bold font-mono">{pct}</span>
      <div className="text-xs leading-tight">
        <div className="font-semibold">{label}</div>
        <div className="opacity-70">overall</div>
      </div>
    </div>
  )
}

export function OrchestrationQualityPanel({ traceId }: { traceId: string }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['trace', traceId, 'orchestration-quality'],
    queryFn: () => api.getOrchestrationQuality(traceId),
    enabled: !!traceId,
    retry: false,
  })

  if (isLoading) return <Skeleton className="h-64 rounded-xl" />
  if (error || !data) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 text-center text-zinc-500">
        Orchestration quality not available for this trace
      </div>
    )
  }

  const q = data as OrchestrationQualityResponse

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-white">Orchestration Quality</h3>
          <p className="text-sm text-zinc-400 mt-1">
            Topology: <span className="text-zinc-300 font-medium">{q.topology}</span>
            {' / '}
            Mode: <span className="text-zinc-300 font-medium">{q.mode}</span>
          </p>
        </div>
        <OverallBadge score={q.overall} />
      </div>

      {/* Dimension Scores */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5 space-y-3">
        <h4 className="text-sm font-semibold text-zinc-300 mb-4">Dimension Scores</h4>
        {Object.entries(q.dimensions).map(([dim, val]) => (
          <ScoreBar key={dim} label={dim.replace(/_/g, ' ')} value={val} />
        ))}
      </div>

      {/* Issues */}
      {q.issues.length > 0 && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5">
          <h4 className="text-sm font-semibold text-amber-400 mb-3">Issues Detected</h4>
          <ul className="space-y-2">
            {q.issues.map((issue, i) => (
              <li key={i} className="text-sm text-zinc-300 flex gap-2">
                <span className="text-amber-500 mt-0.5">&#x25cf;</span>
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Agent Stats */}
      {Object.keys(q.agent_stats).length > 0 && (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <h4 className="text-sm font-semibold text-zinc-300 mb-3">Agent Stats</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-zinc-500 text-left">
                  <th className="pb-2 pr-4">Agent</th>
                  <th className="pb-2 pr-4">Role</th>
                  <th className="pb-2 pr-4 text-right">States</th>
                  <th className="pb-2 pr-4 text-right">Latency</th>
                  <th className="pb-2 text-right">Errors</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(q.agent_stats).map(([agentId, stats]) => (
                  <tr key={agentId} className="border-t border-zinc-800">
                    <td className="py-2 pr-4 font-mono text-zinc-300 truncate max-w-[180px]">{agentId}</td>
                    <td className="py-2 pr-4 text-zinc-400">{stats.role}</td>
                    <td className="py-2 pr-4 text-right text-zinc-300">{stats.state_count}</td>
                    <td className="py-2 pr-4 text-right text-zinc-300">{stats.total_latency_ms}ms</td>
                    <td className="py-2 text-right">
                      {stats.errors > 0
                        ? <span className="text-red-400">{stats.errors}</span>
                        : <span className="text-zinc-500">0</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
