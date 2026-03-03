'use client'

import { useMemo } from 'react'
import type { QualityAssessment } from '@/lib/api'
import type { HandoffMetrics } from '@/lib/workflow-layout'
import { X, ArrowRight, CheckCircle2, AlertCircle, Clock, Activity } from 'lucide-react'
import { cn } from '@/lib/utils'

interface WorkflowEdgeDetailsProps {
  edgeId: string
  handoffMetrics?: Record<string, HandoffMetrics>
  workflow: QualityAssessment
  onClose: () => void
}

export function WorkflowEdgeDetails({
  edgeId,
  handoffMetrics,
  workflow,
  onClose
}: WorkflowEdgeDetailsProps) {
  // Parse edge ID: "agent1-agent2"
  const [sourceId, targetId] = useMemo(() => edgeId.split('-'), [edgeId])

  // Get metrics for this edge
  const metrics = handoffMetrics?.[edgeId]

  // Get agent names
  const sourceAgent = useMemo(() =>
    workflow.agent_scores?.find(a => a.agent_id === sourceId),
    [workflow.agent_scores, sourceId]
  )
  const targetAgent = useMemo(() =>
    workflow.agent_scores?.find(a => a.agent_id === targetId),
    [workflow.agent_scores, targetId]
  )

  return (
    <div className="absolute top-0 right-0 w-96 h-full bg-zinc-800 border-l border-zinc-700 shadow-xl overflow-y-auto z-50">
      {/* Header with agent names */}
      <div className="sticky top-0 bg-zinc-800 border-b border-zinc-700 p-4 z-10">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0 mr-2">
            <h3 className="text-lg font-semibold text-white mb-2">
              Handoff Details
            </h3>
            <div className="flex items-center gap-2 text-sm text-zinc-300">
              <span className="truncate">{sourceAgent?.agent_name || sourceId}</span>
              <ArrowRight size={16} className="text-blue-400" />
              <span className="truncate">{targetAgent?.agent_name || targetId}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-zinc-700 rounded transition-colors flex-shrink-0"
            aria-label="Close"
          >
            <X size={20} className="text-zinc-400" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {metrics ? (
          <>
            {/* Status Badge */}
            <section>
              <div className={cn(
                'inline-flex items-center gap-2 px-3 py-2 rounded-lg font-semibold',
                metrics.status === 'healthy' ? 'bg-green-500/20 text-green-400' :
                metrics.status === 'degraded' ? 'bg-amber-500/20 text-amber-400' :
                'bg-red-500/20 text-red-400'
              )}>
                {metrics.status === 'healthy' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                <span className="capitalize">{metrics.status}</span>
              </div>
            </section>

            {/* Key Metrics Grid */}
            <section>
              <h4 className="text-sm font-semibold text-white mb-3">Performance</h4>
              <div className="grid grid-cols-2 gap-2">
                <MetricCard
                  label="Success Rate"
                  value={`${(metrics.successRate * 100).toFixed(1)}%`}
                  icon={<CheckCircle2 size={14} />}
                  status={metrics.successRate >= 0.95 ? 'good' : metrics.successRate >= 0.85 ? 'moderate' : 'poor'}
                />
                <MetricCard
                  label="Avg Latency"
                  value={`${metrics.avgLatencyMs}ms`}
                  icon={<Clock size={14} />}
                  status={metrics.avgLatencyMs < 100 ? 'good' : metrics.avgLatencyMs < 200 ? 'moderate' : 'poor'}
                />
                <MetricCard
                  label="Total Handoffs"
                  value={metrics.totalHandoffs}
                  icon={<Activity size={14} />}
                />
                <MetricCard
                  label="Failed"
                  value={metrics.failedHandoffs}
                  icon={<AlertCircle size={14} />}
                  status={metrics.failedHandoffs === 0 ? 'good' : metrics.failedHandoffs <= 2 ? 'moderate' : 'poor'}
                />
              </div>
            </section>

            {/* Success Rate Visual */}
            <section>
              <h4 className="text-sm font-semibold text-white mb-3">Success Breakdown</h4>
              <div className="bg-zinc-700/50 rounded-lg p-3">
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="text-green-400">Successful</span>
                  <span className="text-white font-semibold">
                    {metrics.totalHandoffs - metrics.failedHandoffs}
                  </span>
                </div>
                <div className="bg-zinc-700 rounded-full h-2 overflow-hidden mb-3">
                  <div
                    className="bg-green-500 h-2 rounded-full transition-all"
                    style={{ width: `${metrics.successRate * 100}%` }}
                  />
                </div>
                {metrics.failedHandoffs > 0 && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-red-400">Failed</span>
                    <span className="text-white font-semibold">{metrics.failedHandoffs}</span>
                  </div>
                )}
              </div>
            </section>

            {/* Recommendations */}
            {metrics.status !== 'healthy' && (
              <section>
                <h4 className="text-sm font-semibold text-white mb-3">Recommendations</h4>
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-sm text-zinc-300">
                  {metrics.status === 'degraded' && (
                    <p>This handoff is showing signs of degradation. Monitor for patterns and consider investigating agent health.</p>
                  )}
                  {metrics.status === 'failing' && (
                    <p>This handoff is failing frequently. Check agent health, retry logic, and error handling between these agents.</p>
                  )}
                </div>
              </section>
            )}
          </>
        ) : (
          <div className="text-center py-8">
            <AlertCircle className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
            <p className="text-zinc-400">No metrics available for this handoff</p>
            <p className="text-zinc-500 text-sm mt-2">
              Handoff metrics will appear once workflow execution data is collected.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: string | number
  icon: React.ReactNode
  status?: 'good' | 'moderate' | 'poor'
}

function MetricCard({ label, value, icon, status }: MetricCardProps) {
  return (
    <div className="bg-zinc-700/50 rounded-lg p-2.5 border border-zinc-600">
      <div className="flex items-center gap-1.5 mb-1">
        <span className={cn(
          status === 'good' ? 'text-green-400' :
          status === 'moderate' ? 'text-amber-400' :
          status === 'poor' ? 'text-red-400' :
          'text-zinc-400'
        )}>
          {icon}
        </span>
        <span className="text-xs text-zinc-400">{label}</span>
      </div>
      <div className="text-lg font-bold text-white">{value}</div>
    </div>
  )
}
