'use client'

export const dynamic = 'force-dynamic'

import { Layout } from '@/components/common/Layout'
import { useCalibrationMonitor, useICPDetectors } from '@/hooks/useApiWithFallback'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Clock,
  Eye,
  Shield,
  TrendingUp,
} from 'lucide-react'

function StatCard({ icon: Icon, label, value, sub }: {
  icon: React.ElementType
  label: string
  value: string | number
  sub?: string
}) {
  return (
    <Card padding="md">
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-primary-500/10 border border-primary-500/20">
          <Icon className="w-5 h-5 text-primary-400" />
        </div>
        <div>
          <p className="text-sm text-slate-400">{label}</p>
          <p className="text-2xl font-bold font-mono text-white">{value}</p>
          {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
        </div>
      </div>
    </Card>
  )
}

function ConfidenceBar({ distribution }: {
  distribution: { high: number; likely: number; possible: number; low: number }
}) {
  const total = distribution.high + distribution.likely + distribution.possible + distribution.low
  if (total === 0) return <p className="text-xs text-slate-500">No detections</p>

  const segments = [
    { key: 'high', count: distribution.high, color: 'bg-green-500' },
    { key: 'likely', count: distribution.likely, color: 'bg-primary-500' },
    { key: 'possible', count: distribution.possible, color: 'bg-amber-500' },
    { key: 'low', count: distribution.low, color: 'bg-red-500' },
  ]

  return (
    <div className="space-y-1">
      <div className="flex h-2 rounded-full overflow-hidden bg-slate-800">
        {segments.map((seg) => (
          seg.count > 0 && (
            <div
              key={seg.key}
              className={`${seg.color} transition-all`}
              style={{ width: `${(seg.count / total) * 100}%` }}
              title={`${seg.key}: ${seg.count}`}
            />
          )
        ))}
      </div>
      <div className="flex gap-3 text-xs text-slate-500">
        {segments.map((seg) => (
          <span key={seg.key} className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${seg.color}`} />
            {seg.key}: {seg.count}
          </span>
        ))}
      </div>
    </div>
  )
}

function DetectorCard({ name, stats }: {
  name: string
  stats: {
    total_observations: number
    detected_count: number
    detection_rate: number
    avg_confidence: number
    confidence_distribution: { high: number; likely: number; possible: number; low: number }
    severity_distribution: Record<string, number>
    avg_detection_time_ms: number
    alerts: Array<{ type: string; message: string; severity: string }>
  }
}) {
  const hasAlerts = stats.alerts.length > 0
  const ratePercent = (stats.detection_rate * 100).toFixed(1)
  const confPercent = (stats.avg_confidence * 100).toFixed(0)

  return (
    <Card padding="md" className={hasAlerts ? 'border-amber-500/40' : ''}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-mono font-semibold text-white">{name}</span>
          {hasAlerts && (
            <Badge variant="warning" size="sm">
              {stats.alerts.length} alert{stats.alerts.length > 1 ? 's' : ''}
            </Badge>
          )}
        </div>
        <span className="text-xs text-slate-500 font-mono">{stats.total_observations} obs</span>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-3">
        <div>
          <p className="text-xs text-slate-500">Detection Rate</p>
          <p className={`text-lg font-mono font-bold ${
            stats.detection_rate > 0.5 ? 'text-amber-400' : 'text-white'
          }`}>
            {ratePercent}%
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Avg Confidence</p>
          <p className={`text-lg font-mono font-bold ${
            stats.avg_confidence > 0 && stats.avg_confidence < 0.4 ? 'text-red-400' : 'text-white'
          }`}>
            {stats.avg_confidence > 0 ? `${confPercent}%` : '—'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Avg Time</p>
          <p className="text-lg font-mono font-bold text-white">
            {stats.avg_detection_time_ms > 0 ? `${stats.avg_detection_time_ms.toFixed(0)}ms` : '—'}
          </p>
        </div>
      </div>

      <ConfidenceBar distribution={stats.confidence_distribution} />

      {/* Severity breakdown */}
      {Object.keys(stats.severity_distribution).length > 0 && (
        <div className="mt-3 flex gap-2 flex-wrap">
          {Object.entries(stats.severity_distribution).map(([sev, count]) => (
            <Badge
              key={sev}
              variant={sev === 'severe' ? 'error' : sev === 'moderate' ? 'warning' : 'default'}
              size="sm"
            >
              {sev}: {count}
            </Badge>
          ))}
        </div>
      )}

      {/* Alerts */}
      {hasAlerts && (
        <div className="mt-3 space-y-1">
          {stats.alerts.map((alert, i) => (
            <div key={i} className="flex items-start gap-2 p-2 bg-amber-500/5 border border-amber-500/20 rounded text-xs">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
              <span className="text-amber-300">{alert.message}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function ICPDetectorTable({ detectors }: {
  detectors: Array<{
    name: string
    module: string
    failure_mode: string | null
    failure_mode_title: string | null
    tier: string
  }>
}) {
  // Group by failure mode
  const grouped = detectors.reduce((acc, det) => {
    const fm = det.failure_mode || 'Other'
    if (!acc[fm]) acc[fm] = []
    acc[fm].push(det)
    return acc
  }, {} as Record<string, typeof detectors>)

  const sortedModes = Object.keys(grouped).sort((a, b) => {
    if (a === 'Other') return 1
    if (b === 'Other') return -1
    const numA = parseInt(a.replace('F', ''), 10)
    const numB = parseInt(b.replace('F', ''), 10)
    return numA - numB
  })

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-2 px-3 text-xs text-slate-500 font-mono">Mode</th>
            <th className="text-left py-2 px-3 text-xs text-slate-500 font-mono">Title</th>
            <th className="text-left py-2 px-3 text-xs text-slate-500 font-mono">Detector</th>
            <th className="text-left py-2 px-3 text-xs text-slate-500 font-mono">Tier</th>
          </tr>
        </thead>
        <tbody>
          {sortedModes.map((fm) =>
            grouped[fm].map((det, i) => (
              <tr key={det.name} className="border-b border-slate-800 hover:bg-slate-800/50">
                {i === 0 && (
                  <>
                    <td className="py-2 px-3 font-mono text-primary-400" rowSpan={grouped[fm].length}>
                      {fm}
                    </td>
                    <td className="py-2 px-3 text-slate-300" rowSpan={grouped[fm].length}>
                      {det.failure_mode_title || '—'}
                    </td>
                  </>
                )}
                <td className="py-2 px-3 font-mono text-white">{det.name}</td>
                <td className="py-2 px-3">
                  <Badge variant="info" size="sm">ICP</Badge>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

export default function DiagnosticsPage() {
  const { data: monitorData, isLoading: monitorLoading } = useCalibrationMonitor()
  const { data: detectorData, isLoading: detectorLoading } = useICPDetectors()

  const isLoading = monitorLoading || detectorLoading

  return (
    <Layout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-primary-600/20 rounded-lg">
              <Activity className="w-6 h-6 text-primary-400" />
            </div>
            <h1 className="text-2xl font-bold text-white">Detector Diagnostics</h1>
            <Badge variant="info" size="sm">ICP</Badge>
          </div>
          <p className="text-slate-400">
            Live calibration monitoring across all detection runs. Track confidence distributions, detection rates, and drift alerts.
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
          </div>
        ) : (
          <>
            {/* Summary Stats */}
            {monitorData?.summary && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard
                  icon={Eye}
                  label="Detectors Observed"
                  value={monitorData.summary.total_detectors_observed}
                />
                <StatCard
                  icon={BarChart3}
                  label="Total Observations"
                  value={monitorData.summary.total_observations}
                />
                <StatCard
                  icon={TrendingUp}
                  label="Diagnose Runs"
                  value={monitorData.summary.total_diagnose_runs}
                />
                <StatCard
                  icon={AlertTriangle}
                  label="Active Alerts"
                  value={monitorData.summary.alert_count}
                  sub={monitorData.summary.detectors_with_alerts > 0
                    ? `${monitorData.summary.detectors_with_alerts} detector${monitorData.summary.detectors_with_alerts > 1 ? 's' : ''}`
                    : undefined}
                />
              </div>
            )}

            {/* Global Alerts */}
            {monitorData?.alerts && monitorData.alerts.length > 0 && (
              <Card padding="lg" className="border-amber-500/30">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-amber-400" />
                    <span className="text-amber-400">Active Drift Alerts</span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    {monitorData.alerts.map((alert, i) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg">
                        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                        <div>
                          <span className="text-sm text-amber-300">{alert.message}</span>
                          {alert.detector && (
                            <span className="ml-2 text-xs font-mono text-slate-500">({alert.detector})</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Per-Detector Cards */}
            {monitorData?.detectors && Object.keys(monitorData.detectors).length > 0 ? (
              <div>
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-primary-400" />
                  Per-Detector Monitoring
                </h2>
                <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {Object.entries(monitorData.detectors)
                    .sort(([, a], [, b]) => b.alerts.length - a.alerts.length || b.total_observations - a.total_observations)
                    .map(([name, stats]) => (
                      <DetectorCard key={name} name={name} stats={stats} />
                    ))}
                </div>
              </div>
            ) : (
              <Card padding="lg">
                <div className="text-center py-8 text-slate-500">
                  <Eye className="w-12 h-12 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">No monitoring data yet</p>
                  <p className="text-sm">Run a diagnosis from the Agent Forensics page to start collecting calibration data.</p>
                </div>
              </Card>
            )}

            {/* ICP Detector Inventory */}
            {detectorData && detectorData.detectors.length > 0 && (
              <Card padding="lg">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <Shield className="w-5 h-5 text-primary-400" />
                      <span>ICP Detector Inventory</span>
                    </CardTitle>
                    <div className="flex gap-2">
                      <Badge variant="info" size="sm">{detectorData.total_detectors} detectors</Badge>
                      <Badge variant="success" size="sm">{detectorData.failure_modes_covered} failure modes</Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <ICPDetectorTable detectors={detectorData.detectors} />
                </CardContent>
              </Card>
            )}

            {/* Monitoring Since */}
            {monitorData?.summary?.monitoring_since && (
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <Clock className="w-3.5 h-3.5" />
                <span>Monitoring since {new Date(monitorData.summary.monitoring_since).toLocaleString()}</span>
              </div>
            )}
          </>
        )}
      </div>
    </Layout>
  )
}
