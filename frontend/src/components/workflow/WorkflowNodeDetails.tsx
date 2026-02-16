'use client'

import { useMemo } from 'react'
import type { AgentQualityScore, QualityAssessment } from '@/lib/api'
import { QualityGradeBadge } from '@/components/quality/QualityGradeBadge'
import { X, AlertCircle, TrendingUp, Clock, Coins, Zap } from 'lucide-react'
import clsx from 'clsx'

interface WorkflowNodeDetailsProps {
  agentId: string
  workflow: QualityAssessment
  onClose: () => void
}

export function WorkflowNodeDetails({ agentId, workflow, onClose }: WorkflowNodeDetailsProps) {
  const agent = useMemo(() =>
    workflow.agent_scores?.find(a => a.agent_id === agentId),
    [agentId, workflow.agent_scores]
  )

  const agentImprovements = useMemo(() =>
    workflow.improvements?.filter(imp => imp.target_id === agentId) || [],
    [agentId, workflow.improvements]
  )

  if (!agent) {
    return (
      <div className="absolute top-0 right-0 w-80 h-full bg-slate-800 border-l border-slate-700 shadow-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Agent Not Found</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-700 rounded transition-colors"
            aria-label="Close"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>
        <p className="text-sm text-slate-400">Unable to load agent details.</p>
      </div>
    )
  }

  return (
    <div className="absolute top-0 right-0 w-96 h-full bg-slate-800 border-l border-slate-700 shadow-xl overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 bg-slate-800 border-b border-slate-700 p-4 z-10">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0 mr-2">
            <h3 className="text-lg font-semibold text-white mb-1 truncate">
              {agent.agent_name}
            </h3>
            {agent.agent_type && (
              <div className="text-xs text-slate-400 capitalize">{agent.agent_type}</div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-700 rounded transition-colors flex-shrink-0"
            aria-label="Close"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {/* Overall Score */}
        <section>
          <div className="flex items-center gap-3 mb-3">
            <QualityGradeBadge grade={agent.grade} size="lg" />
            <div>
              <div className={clsx(
                'text-2xl font-bold',
                agent.overall_score >= 0.9 ? 'text-green-400' :
                agent.overall_score >= 0.8 ? 'text-blue-400' :
                agent.overall_score >= 0.6 ? 'text-amber-400' :
                'text-red-400'
              )}>
                {(agent.overall_score * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-slate-400">Overall Quality</div>
            </div>
          </div>
        </section>

        {/* Critical Issues */}
        {agent.critical_issues && agent.critical_issues.length > 0 && (
          <section className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-red-400 mb-2">
              <AlertCircle size={16} />
              <span>Critical Issues ({agent.critical_issues.length})</span>
            </div>
            <div className="space-y-1.5">
              {agent.critical_issues.map((issue, idx) => (
                <div key={idx} className="text-xs text-slate-300">
                  • {issue}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Quality Dimensions */}
        {agent.dimensions && agent.dimensions.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp size={16} className="text-purple-400" />
              <h4 className="text-sm font-semibold text-white">Quality Dimensions</h4>
            </div>
            <div className="space-y-2.5">
              {agent.dimensions.map((dim) => (
                <div key={dim.dimension}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-slate-300 capitalize">{dim.dimension}</span>
                    <span className={clsx(
                      'font-semibold',
                      dim.score >= 0.8 ? 'text-green-400' :
                      dim.score >= 0.6 ? 'text-blue-400' :
                      dim.score >= 0.4 ? 'text-amber-400' :
                      'text-red-400'
                    )}>
                      {(dim.score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="bg-slate-700 rounded-full h-1.5 overflow-hidden">
                    <div
                      className={clsx(
                        'h-1.5 rounded-full transition-all',
                        dim.score >= 0.8 ? 'bg-green-500' :
                        dim.score >= 0.6 ? 'bg-blue-500' :
                        dim.score >= 0.4 ? 'bg-amber-500' :
                        'bg-red-500'
                      )}
                      style={{ width: `${dim.score * 100}%` }}
                    />
                  </div>
                  {dim.reasoning && (
                    <div className="text-xs text-slate-500 mt-1">{dim.reasoning}</div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Performance Metrics */}
        <section>
          <h4 className="text-sm font-semibold text-white mb-3">Performance</h4>
          <div className="grid grid-cols-2 gap-2">
            {/* Issues Count */}
            <MetricCard
              icon={<AlertCircle size={14} />}
              label="Issues"
              value={agent.issues_count}
              status={agent.issues_count === 0 ? 'good' : agent.issues_count <= 2 ? 'moderate' : 'poor'}
            />

            {/* Placeholder for token count - would come from traces */}
            <MetricCard
              icon={<Coins size={14} />}
              label="Avg Tokens"
              value="—"
              status="neutral"
            />

            {/* Placeholder for latency - would come from traces */}
            <MetricCard
              icon={<Clock size={14} />}
              label="Avg Latency"
              value="—"
              status="neutral"
            />

            {/* Placeholder for executions - would come from traces */}
            <MetricCard
              icon={<Zap size={14} />}
              label="Executions"
              value="—"
              status="neutral"
            />
          </div>
        </section>

        {/* Agent-Specific Improvements */}
        {agentImprovements.length > 0 && (
          <section>
            <h4 className="text-sm font-semibold text-white mb-3">
              Improvement Suggestions ({agentImprovements.length})
            </h4>
            <div className="space-y-2">
              {agentImprovements.map((improvement) => (
                <div
                  key={improvement.id}
                  className="bg-slate-700/50 rounded-lg p-3 border border-slate-600"
                >
                  <div className="flex items-start justify-between mb-1.5">
                    <span className={clsx(
                      'text-xs font-medium px-2 py-0.5 rounded',
                      improvement.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                      improvement.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                      improvement.severity === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                      'bg-blue-500/20 text-blue-400'
                    )}>
                      {improvement.severity}
                    </span>
                    <span className="text-xs text-slate-500">{improvement.effort}</span>
                  </div>
                  <div className="text-sm font-medium text-white mb-1">
                    {improvement.title}
                  </div>
                  <div className="text-xs text-slate-400">
                    {improvement.description}
                  </div>
                  {improvement.estimated_impact && (
                    <div className="text-xs text-emerald-400 mt-1.5">
                      💡 {improvement.estimated_impact}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Issues Breakdown */}
        {agent.issues_count > 0 && (
          <section>
            <h4 className="text-sm font-semibold text-white mb-3">
              Issues Detected ({agent.issues_count})
            </h4>
            <div className="text-xs text-slate-400 bg-slate-700/30 rounded-lg p-3 border border-slate-600">
              <p>Issue details would be displayed here based on trace analysis.</p>
              <p className="mt-2">This includes detection types, timestamps, and affected operations.</p>
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

interface MetricCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  status?: 'good' | 'moderate' | 'poor' | 'neutral'
}

function MetricCard({ icon, label, value, status = 'neutral' }: MetricCardProps) {
  return (
    <div className="bg-slate-700/50 rounded-lg p-2.5 border border-slate-600">
      <div className="flex items-center gap-1.5 mb-1">
        <span className={clsx(
          status === 'good' ? 'text-green-400' :
          status === 'moderate' ? 'text-amber-400' :
          status === 'poor' ? 'text-red-400' :
          'text-slate-400'
        )}>
          {icon}
        </span>
        <span className="text-xs text-slate-400">{label}</span>
      </div>
      <div className="text-lg font-bold text-white">{value}</div>
    </div>
  )
}
