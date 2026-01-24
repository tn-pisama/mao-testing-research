'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useMemo } from 'react'
import { Layout } from '@/components/common/Layout'
import { formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'
import {
  AlertTriangle,
  AlertCircle,
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
  Wrench,
} from 'lucide-react'
import Link from 'next/link'
import { generateDemoLoopAnalytics } from '@/lib/demo-data'
import type { Detection } from '@/lib/api'
import { useUserPreferences } from '@/lib/user-preferences'
import { useDetections } from '@/hooks/useApiWithFallback'

type DetectionType = 'all' | 'infinite_loop' | 'state_corruption' | 'persona_drift' | 'coordination_deadlock' | 'task_derailment' | 'context_neglect' | 'communication_breakdown' | 'specification_mismatch' | 'poor_decomposition' | 'flawed_workflow'
type Severity = 'all' | 'low' | 'medium' | 'high' | 'critical'

const detectionTypeConfig: Record<string, { label: string; color: string; icon: typeof AlertTriangle; category: string }> = {
  infinite_loop: { label: 'Infinite Loop', color: 'text-red-400', icon: RefreshCw, category: 'Inter-Agent' },
  state_corruption: { label: 'State Corruption', color: 'text-orange-400', icon: AlertTriangle, category: 'System' },
  persona_drift: { label: 'Persona Drift', color: 'text-purple-400', icon: Activity, category: 'Inter-Agent' },
  coordination_deadlock: { label: 'Coordination Deadlock', color: 'text-amber-400', icon: Zap, category: 'Inter-Agent' },
  task_derailment: { label: 'Task Derailment', color: 'text-pink-400', icon: TrendingUp, category: 'Inter-Agent' },
  context_neglect: { label: 'Context Neglect', color: 'text-cyan-400', icon: Eye, category: 'Inter-Agent' },
  communication_breakdown: { label: 'Communication Breakdown', color: 'text-rose-400', icon: AlertTriangle, category: 'Inter-Agent' },
  specification_mismatch: { label: 'Spec Mismatch', color: 'text-blue-400', icon: Shield, category: 'System' },
  poor_decomposition: { label: 'Poor Decomposition', color: 'text-indigo-400', icon: Activity, category: 'System' },
  flawed_workflow: { label: 'Flawed Workflow', color: 'text-violet-400', icon: Zap, category: 'System' },
}

const severityConfig: Record<string, { label: string; color: string; bg: string }> = {
  low: { label: 'Low', color: 'text-slate-400', bg: 'bg-slate-500/20' },
  medium: { label: 'Medium', color: 'text-amber-400', bg: 'bg-amber-500/20' },
  high: { label: 'High', color: 'text-orange-400', bg: 'bg-orange-500/20' },
  critical: { label: 'Critical', color: 'text-red-400', bg: 'bg-red-500/20' },
}

// Plain-English labels for n8n users
const plainEnglishLabels: Record<string, string> = {
  infinite_loop: 'Stuck in a loop',
  state_corruption: 'Data got corrupted',
  persona_drift: 'Unexpected behavior',
  coordination_deadlock: 'System stuck',
  task_derailment: 'Got off track',
  context_neglect: 'Lost context',
  communication_breakdown: 'Communication issue',
  specification_mismatch: 'Wrong output format',
  poor_decomposition: 'Bad task split',
  flawed_workflow: 'Workflow problem',
}

export default function DetectionsPage() {
  const [typeFilter, setTypeFilter] = useState<DetectionType>('all')
  const [severityFilter, setSeverityFilter] = useState<Severity>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showValidated, setShowValidated] = useState(true)
  const { isN8nUser, showAdvancedFeatures } = useUserPreferences()

  // Fetch real detections from API
  const { detections, isLoading, isDemoMode } = useDetections({ perPage: 50 })

  // n8n users see simplified view with friendly terminology
  const showSimplifiedView = isN8nUser && !showAdvancedFeatures
  const isLoaded = !isLoading

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
      task_derailment: detections.filter(d => d.detection_type === 'task_derailment').length,
      context_neglect: detections.filter(d => d.detection_type === 'context_neglect').length,
      communication_breakdown: detections.filter(d => d.detection_type === 'communication_breakdown').length,
      specification_mismatch: detections.filter(d => d.detection_type === 'specification_mismatch').length,
      poor_decomposition: detections.filter(d => d.detection_type === 'poor_decomposition').length,
      flawed_workflow: detections.filter(d => d.detection_type === 'flawed_workflow').length,
    }
  }), [detections])

  if (!isLoaded) {
    return (
      <Layout>
        <div className="p-6">
          <div className="animate-pulse space-y-6">
            <div className="h-8 w-48 bg-slate-700 rounded" />
            <div className="grid grid-cols-4 gap-4">
              {[1,2,3,4].map(i => <div key={i} className="h-20 bg-slate-700 rounded-xl" />)}
            </div>
            <div className="h-96 bg-slate-700 rounded-xl" />
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            {showSimplifiedView && (
              <div className="p-2 bg-amber-500/20 rounded-lg">
                <AlertCircle size={24} className="text-amber-400" />
              </div>
            )}
            <div>
              <h1 className="text-2xl font-bold text-white mb-1">
                {showSimplifiedView ? 'Problems Found' : 'Detections'}
              </h1>
              <p className="text-sm text-slate-400">
                {showSimplifiedView
                  ? 'Issues we found in your workflows that need attention'
                  : 'Monitor and validate failure detections across your agent systems'}
              </p>
            </div>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-white font-medium transition-colors">
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>

        {isDemoMode && (
          <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
            <AlertCircle size={20} className="text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-semibold text-amber-400 mb-1">Demo Mode</h3>
              <p className="text-sm text-amber-300/80">
                Unable to connect to API. Showing demo data for illustration purposes.
                {' '}Please check your connection or contact support if this persists.
              </p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            icon={AlertTriangle}
            label={showSimplifiedView ? 'Total Problems' : 'Total Detections'}
            value={stats.total}
            color="text-red-400"
            bgColor="bg-red-500/20"
          />
          <StatCard
            icon={Eye}
            label={showSimplifiedView ? 'Need Attention' : 'Needs Review'}
            value={stats.unvalidated}
            color="text-amber-400"
            bgColor="bg-amber-500/20"
          />
          {showSimplifiedView ? (
            <StatCard
              icon={Wrench}
              label="Fixes Available"
              value={Math.floor(stats.total * 0.7)}
              color="text-purple-400"
              bgColor="bg-purple-500/20"
            />
          ) : (
            <StatCard
              icon={ThumbsDown}
              label="False Positives"
              value={stats.falsePositives}
              color="text-slate-400"
              bgColor="bg-slate-500/20"
            />
          )}
          <StatCard
            icon={Shield}
            label={showSimplifiedView ? 'Detection Accuracy' : 'Avg Confidence'}
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
                    <optgroup label="System Design">
                      <option value="specification_mismatch">Spec Mismatch (F1)</option>
                      <option value="poor_decomposition">Poor Decomposition (F2)</option>
                      <option value="state_corruption">State Corruption (F3/F4)</option>
                      <option value="flawed_workflow">Flawed Workflow (F5)</option>
                    </optgroup>
                    <optgroup label="Inter-Agent">
                      <option value="task_derailment">Task Derailment (F6)</option>
                      <option value="context_neglect">Context Neglect (F7)</option>
                      <option value="infinite_loop">Infinite Loop (F8/F9)</option>
                      <option value="communication_breakdown">Communication Breakdown (F10)</option>
                      <option value="persona_drift">Persona Drift (F11)</option>
                    </optgroup>
                    <optgroup label="Coordination">
                      <option value="coordination_deadlock">Deadlock (F12-F14)</option>
                    </optgroup>
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
                  const displayLabel = showSimplifiedView
                    ? (plainEnglishLabels[detection.detection_type] || typeConfig.label)
                    : typeConfig.label

                  return (
                    <Link
                      key={detection.id}
                      href={showSimplifiedView ? `/healing?detection=${detection.id}` : `/traces/${detection.trace_id}`}
                      className="flex items-center gap-4 p-4 hover:bg-slate-700/30 transition-colors"
                    >
                      <div className={clsx('p-2 rounded-lg', severity.bg)}>
                        <TypeIcon size={16} className={typeConfig.color} />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-white">{displayLabel}</span>
                          <span className={clsx('text-xs px-2 py-0.5 rounded-full', severity.bg, severity.color)}>
                            {severity.label}
                          </span>
                          {detection.validated && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
                              {showSimplifiedView ? 'Confirmed' : 'Validated'}
                            </span>
                          )}
                          {detection.false_positive && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-500/20 text-slate-400">
                              {showSimplifiedView ? 'Not an Issue' : 'False Positive'}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-xs text-slate-400">
                          {showSimplifiedView ? (
                            <>
                              <span>{formatDistanceToNow(new Date(detection.created_at), { addSuffix: true })}</span>
                              {severity.label !== 'Low' && (
                                <span className="text-amber-400">Recommended to fix</span>
                              )}
                            </>
                          ) : (
                            <>
                              <span>{Math.round(detection.confidence * 100)}% confidence</span>
                              <span>via {detection.method.replace('_', ' ')}</span>
                              <span>{detection.details?.affected_agents} agents affected</span>
                            </>
                          )}
                        </div>
                      </div>

                      <div className="text-right">
                        {showSimplifiedView ? (
                          <div className="flex items-center gap-2">
                            <Link
                              href={`/healing?detection=${detection.id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
                            >
                              <Wrench size={14} />
                              Fix
                            </Link>
                          </div>
                        ) : (
                          <>
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
                          </>
                        )}
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
