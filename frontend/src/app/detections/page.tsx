'use client'

import { useState, useMemo } from 'react'
import { Layout } from '@/components/common/Layout'
import { formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Filter,
  Search,
  RefreshCw,
  TrendingUp,
  Activity,
  Shield,
  Zap,
  Eye,
  ThumbsUp,
  ThumbsDown,
  ChevronRight,
} from 'lucide-react'
import Link from 'next/link'
import { generateDemoDetections, generateDemoLoopAnalytics } from '@/lib/demo-data'

type DetectionType = 'all' | 'infinite_loop' | 'state_corruption' | 'persona_drift' | 'coordination_deadlock'
type Severity = 'all' | 'low' | 'medium' | 'high' | 'critical'

const detectionTypeConfig: Record<string, { label: string; color: string; icon: typeof AlertTriangle }> = {
  infinite_loop: { label: 'Infinite Loop', color: 'text-red-400', icon: RefreshCw },
  state_corruption: { label: 'State Corruption', color: 'text-orange-400', icon: AlertTriangle },
  persona_drift: { label: 'Persona Drift', color: 'text-purple-400', icon: Activity },
  coordination_deadlock: { label: 'Coordination Deadlock', color: 'text-amber-400', icon: Zap },
}

const severityConfig: Record<string, { label: string; color: string; bg: string }> = {
  low: { label: 'Low', color: 'text-slate-400', bg: 'bg-slate-500/20' },
  medium: { label: 'Medium', color: 'text-amber-400', bg: 'bg-amber-500/20' },
  high: { label: 'High', color: 'text-orange-400', bg: 'bg-orange-500/20' },
  critical: { label: 'Critical', color: 'text-red-400', bg: 'bg-red-500/20' },
}

export default function DetectionsPage() {
  const [typeFilter, setTypeFilter] = useState<DetectionType>('all')
  const [severityFilter, setSeverityFilter] = useState<Severity>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showValidated, setShowValidated] = useState(true)

  const detections = useMemo(() => generateDemoDetections(25), [])
  const analytics = useMemo(() => generateDemoLoopAnalytics(), [])

  const filteredDetections = useMemo(() => {
    return detections.filter((d) => {
      if (typeFilter !== 'all' && d.detection_type !== typeFilter) return false
      if (severityFilter !== 'all' && d.details?.severity !== severityFilter) return false
      if (!showValidated && d.validated) return false
      return true
    })
  }, [detections, typeFilter, severityFilter, showValidated])

  const stats = useMemo(() => ({
    total: detections.length,
    unvalidated: detections.filter(d => !d.validated).length,
    falsePositives: detections.filter(d => d.false_positive).length,
    byType: {
      infinite_loop: detections.filter(d => d.detection_type === 'infinite_loop').length,
      state_corruption: detections.filter(d => d.detection_type === 'state_corruption').length,
      persona_drift: detections.filter(d => d.detection_type === 'persona_drift').length,
      coordination_deadlock: detections.filter(d => d.detection_type === 'coordination_deadlock').length,
    }
  }), [detections])

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">Detections</h1>
            <p className="text-sm text-slate-400">
              Monitor and validate failure detections across your agent systems
            </p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-white font-medium transition-colors">
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            icon={AlertTriangle}
            label="Total Detections"
            value={stats.total}
            color="text-red-400"
            bgColor="bg-red-500/20"
          />
          <StatCard
            icon={Eye}
            label="Needs Review"
            value={stats.unvalidated}
            color="text-amber-400"
            bgColor="bg-amber-500/20"
          />
          <StatCard
            icon={ThumbsDown}
            label="False Positives"
            value={stats.falsePositives}
            color="text-slate-400"
            bgColor="bg-slate-500/20"
          />
          <StatCard
            icon={Shield}
            label="Avg Confidence"
            value={`${Math.round(detections.reduce((s, d) => s + d.confidence * 100, 0) / detections.length)}%`}
            color="text-emerald-400"
            bgColor="bg-emerald-500/20"
          />
        </div>

        <div className="grid lg:grid-cols-4 gap-6">
          <div className="lg:col-span-1 space-y-4">
            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <Filter size={14} />
                Filters
              </h3>

              <div className="space-y-4">
                <div>
                  <label className="text-xs text-slate-400 mb-2 block">Detection Type</label>
                  <select
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value as DetectionType)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-sm focus:outline-none focus:border-primary-500"
                  >
                    <option value="all">All Types</option>
                    <option value="infinite_loop">Infinite Loop</option>
                    <option value="state_corruption">State Corruption</option>
                    <option value="persona_drift">Persona Drift</option>
                    <option value="coordination_deadlock">Coordination Deadlock</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs text-slate-400 mb-2 block">Severity</label>
                  <select
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value as Severity)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white text-sm focus:outline-none focus:border-primary-500"
                  >
                    <option value="all">All Severities</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>

                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showValidated}
                    onChange={(e) => setShowValidated(e.target.checked)}
                    className="rounded border-slate-600 bg-slate-900 text-primary-500 focus:ring-primary-500"
                  />
                  <span className="text-sm text-slate-300">Show Validated</span>
                </label>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
              <h3 className="text-sm font-semibold text-white mb-3">By Type</h3>
              <div className="space-y-2">
                {Object.entries(stats.byType).map(([type, count]) => {
                  const config = detectionTypeConfig[type]
                  const Icon = config.icon
                  return (
                    <button
                      key={type}
                      onClick={() => setTypeFilter(type as DetectionType)}
                      className={clsx(
                        'w-full flex items-center justify-between p-2 rounded-lg transition-colors',
                        typeFilter === type ? 'bg-slate-700' : 'hover:bg-slate-700/50'
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <Icon size={14} className={config.color} />
                        <span className="text-sm text-slate-300">{config.label}</span>
                      </div>
                      <span className="text-sm font-medium text-white">{count}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          </div>

          <div className="lg:col-span-3">
            <div className="rounded-xl bg-slate-800/50 border border-slate-700 overflow-hidden">
              <div className="p-4 border-b border-slate-700 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-slate-400">
                    {filteredDetections.length} detections
                  </span>
                </div>
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 pr-4 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-primary-500 w-64"
                  />
                </div>
              </div>

              <div className="divide-y divide-slate-700/50">
                {filteredDetections.map((detection) => {
                  const typeConfig = detectionTypeConfig[detection.detection_type] || detectionTypeConfig.infinite_loop
                  const severity = severityConfig[detection.details?.severity || 'medium']
                  const TypeIcon = typeConfig.icon

                  return (
                    <Link
                      key={detection.id}
                      href={`/traces/${detection.trace_id}`}
                      className="flex items-center gap-4 p-4 hover:bg-slate-700/30 transition-colors"
                    >
                      <div className={clsx('p-2 rounded-lg', severity.bg)}>
                        <TypeIcon size={16} className={typeConfig.color} />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-white">{typeConfig.label}</span>
                          <span className={clsx('text-xs px-2 py-0.5 rounded-full', severity.bg, severity.color)}>
                            {severity.label}
                          </span>
                          {detection.validated && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
                              Validated
                            </span>
                          )}
                          {detection.false_positive && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-500/20 text-slate-400">
                              False Positive
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-xs text-slate-400">
                          <span>{Math.round(detection.confidence * 100)}% confidence</span>
                          <span>via {detection.method.replace('_', ' ')}</span>
                          <span>{detection.details?.affected_agents} agents affected</span>
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-xs text-slate-400 mb-1">
                          {formatDistanceToNow(new Date(detection.created_at), { addSuffix: true })}
                        </div>
                        <div className="flex items-center gap-1">
                          {!detection.validated && (
                            <>
                              <button
                                onClick={(e) => { e.preventDefault() }}
                                className="p-1.5 rounded hover:bg-emerald-500/20 text-slate-400 hover:text-emerald-400 transition-colors"
                                title="Mark as valid"
                              >
                                <ThumbsUp size={14} />
                              </button>
                              <button
                                onClick={(e) => { e.preventDefault() }}
                                className="p-1.5 rounded hover:bg-red-500/20 text-slate-400 hover:text-red-400 transition-colors"
                                title="Mark as false positive"
                              >
                                <ThumbsDown size={14} />
                              </button>
                            </>
                          )}
                          <ChevronRight size={14} className="text-slate-500" />
                        </div>
                      </div>
                    </Link>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}

interface StatCardProps {
  icon: typeof AlertTriangle
  label: string
  value: string | number
  color: string
  bgColor: string
}

function StatCard({ icon: Icon, label, value, color, bgColor }: StatCardProps) {
  return (
    <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700">
      <div className="flex items-center gap-3">
        <div className={clsx('p-2 rounded-lg', bgColor)}>
          <Icon size={18} className={color} />
        </div>
        <div>
          <div className="text-2xl font-bold text-white">{value}</div>
          <div className="text-xs text-slate-400">{label}</div>
        </div>
      </div>
    </div>
  )
}
