'use client'

import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Shield, AlertTriangle, Activity, CheckCircle } from 'lucide-react'

interface DetectorInfo {
  name: string
  readiness: 'production' | 'beta' | 'experimental' | 'failing' | 'untested'
  description: string
  enabled: boolean
  f1_score: number | null
  precision: number | null
  recall: number | null
  sample_count: number
  optimal_threshold: number | null
}

interface DetectorStatusData {
  detectors: DetectorInfo[]
  summary: Record<string, number>
  calibrated_at: string
  readiness_criteria: Record<string, any>
}

const readinessConfig: Record<string, { label: string; color: string; bg: string; icon: typeof Shield }> = {
  production: { label: 'Production', color: 'text-green-400', bg: 'bg-green-500/20', icon: CheckCircle },
  beta: { label: 'Beta', color: 'text-blue-400', bg: 'bg-blue-500/20', icon: Shield },
  experimental: { label: 'Experimental', color: 'text-amber-400', bg: 'bg-amber-500/20', icon: Activity },
  failing: { label: 'Failing', color: 'text-red-400', bg: 'bg-red-500/20', icon: AlertTriangle },
  untested: { label: 'Untested', color: 'text-zinc-400', bg: 'bg-zinc-500/20', icon: AlertTriangle },
}

function F1Bar({ value }: { value: number | null }) {
  if (value === null) return <span className="text-zinc-500 text-xs">N/A</span>
  const pct = Math.round(value * 100)
  const color = value >= 0.80 ? 'bg-green-500' : value >= 0.65 ? 'bg-blue-500' : value >= 0.40 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-zinc-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-zinc-300 w-10">{(value).toFixed(2)}</span>
    </div>
  )
}

function SampleProgress({ count, target = 30 }: { count: number; target?: number }) {
  const pct = Math.min(100, Math.round((count / target) * 100))
  const color = count >= target ? 'bg-green-500' : count >= target * 0.5 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-zinc-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-zinc-300">{count}/{target}</span>
    </div>
  )
}

export function DetectorStatusDashboard({ data }: { data: DetectorStatusData }) {
  const sortedDetectors = [...data.detectors].sort((a, b) => {
    const order = { production: 0, beta: 1, experimental: 2, failing: 3, untested: 4 }
    return (order[a.readiness] ?? 5) - (order[b.readiness] ?? 5)
  })

  const calibratedDate = new Date(data.calibrated_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center gap-3 flex-wrap">
        {Object.entries(data.summary).filter(([, count]) => count > 0).map(([tier, count]) => {
          const config = readinessConfig[tier]
          return config ? (
            <div key={tier} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full ${config.bg}`}>
              <config.icon className={`w-3.5 h-3.5 ${config.color}`} />
              <span className={`text-sm font-medium ${config.color}`}>{count} {config.label}</span>
            </div>
          ) : null
        })}
        <span className="text-xs text-zinc-500 ml-auto">Calibrated: {calibratedDate}</span>
      </div>

      {/* Detector table */}
      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700">
                <th className="text-left py-2 px-3 text-zinc-400 font-medium">Detector</th>
                <th className="text-left py-2 px-3 text-zinc-400 font-medium">Readiness</th>
                <th className="text-left py-2 px-3 text-zinc-400 font-medium">F1 Score</th>
                <th className="text-left py-2 px-3 text-zinc-400 font-medium">Precision</th>
                <th className="text-left py-2 px-3 text-zinc-400 font-medium">Recall</th>
                <th className="text-left py-2 px-3 text-zinc-400 font-medium">Samples</th>
                <th className="text-left py-2 px-3 text-zinc-400 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {sortedDetectors.map((det) => {
                const config = readinessConfig[det.readiness] || readinessConfig.untested
                return (
                  <tr key={det.name} className="border-b border-zinc-800 hover:bg-zinc-800/50">
                    <td className="py-2 px-3">
                      <div>
                        <span className="text-zinc-200 font-medium">{det.name}</span>
                        <p className="text-xs text-zinc-500 truncate max-w-xs">{det.description}</p>
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <Badge variant={det.readiness === 'production' ? 'success' : det.readiness === 'beta' ? 'info' : det.readiness === 'experimental' ? 'warning' : 'error'}>
                        {config.label}
                      </Badge>
                    </td>
                    <td className="py-2 px-3"><F1Bar value={det.f1_score} /></td>
                    <td className="py-2 px-3">
                      <span className="text-xs text-zinc-300">{det.precision !== null ? det.precision.toFixed(2) : 'N/A'}</span>
                    </td>
                    <td className="py-2 px-3">
                      <span className="text-xs text-zinc-300">{det.recall !== null ? det.recall.toFixed(2) : 'N/A'}</span>
                    </td>
                    <td className="py-2 px-3"><SampleProgress count={det.sample_count} /></td>
                    <td className="py-2 px-3">
                      <span className={`text-xs ${det.enabled ? 'text-green-400' : 'text-zinc-500'}`}>
                        {det.enabled ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
