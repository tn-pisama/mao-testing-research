'use client'

import { useState } from 'react'
import type { QualityAssessment } from '@/lib/api'
import { QualityGradeBadge } from '@/components/quality/QualityGradeBadge'
import { AgentStatusGrid } from '@/components/dashboard/AgentStatusGrid'
import { WorkflowGraphView } from '@/components/workflow/WorkflowGraphView'
import { WorkflowNodeDetails } from '@/components/workflow/WorkflowNodeDetails'
import { WorkflowEdgeDetails } from '@/components/workflow/WorkflowEdgeDetails'
import { useHandoffAnalysis } from '@/hooks/useHandoffAnalysis'
import { X, ChevronDown, ChevronUp, AlertCircle, Info, TrendingUp, GitBranch, Activity } from 'lucide-react'
import clsx from 'clsx'

interface WorkflowDetailPanelProps {
  workflow: QualityAssessment
  onClose: () => void
}

export function WorkflowDetailPanel({ workflow, onClose }: WorkflowDetailPanelProps) {
  const [showAgentDetails, setShowAgentDetails] = useState(false)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)

  const orchestrationScore = workflow.orchestration_score
  const orchestrationImprovements = workflow.improvements?.filter(
    (imp) => imp.target_type === 'orchestration'
  ) || []

  // Load handoff analysis with API fallback to demo data
  const { handoffAnalysis, handoffMetrics, isLoading: handoffLoading, isDemoMode } = useHandoffAnalysis(workflow)

  const handleNodeClick = (nodeId: string) => {
    // Don't open details for start/end nodes
    if (nodeId === 'start' || nodeId === 'end') return
    setSelectedNodeId(nodeId)
    setSelectedEdgeId(null) // Close edge details if open
  }

  const handleEdgeClick = (edgeId: string) => {
    setSelectedEdgeId(edgeId)
    setSelectedNodeId(null) // Close node details if open
  }

  return (
    <div className="fixed inset-y-0 right-0 w-full md:w-2/3 lg:w-1/2 bg-slate-900 border-l border-slate-700 shadow-2xl overflow-y-auto z-50">
      {/* Header */}
      <div className="sticky top-0 bg-slate-900 border-b border-slate-700 p-6 z-10">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0 mr-4">
            <h2 className="text-2xl font-bold text-white mb-2 truncate">
              {workflow.workflow_name}
            </h2>
            <div className="text-sm text-slate-400">
              ID: {workflow.workflow_id}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-800 rounded-lg transition-colors flex-shrink-0"
            aria-label="Close panel"
          >
            <X size={24} className="text-slate-400" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-6 space-y-6">
        {/* Orchestration Quality - PRIMARY */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-lg font-semibold text-white">Orchestration Quality</h3>
            <TrendingUp size={20} className="text-purple-400" />
          </div>

          <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
            {/* Overall Score */}
            <div className="flex items-center gap-4 mb-4">
              <QualityGradeBadge grade={workflow.overall_grade} size="lg" />
              <div>
                <div className={clsx(
                  'text-3xl font-bold',
                  workflow.overall_score >= 0.8 ? 'text-green-400' :
                  workflow.overall_score >= 0.6 ? 'text-blue-400' :
                  workflow.overall_score >= 0.4 ? 'text-amber-400' :
                  'text-red-400'
                )}>
                  {(workflow.overall_score * 100).toFixed(0)}%
                </div>
                <div className="text-sm text-slate-400">Overall Quality</div>
              </div>
              {orchestrationScore?.detected_pattern && (
                <div className="ml-auto">
                  <div className="text-xs text-slate-400">Pattern</div>
                  <div className="text-sm text-white font-medium capitalize">
                    {orchestrationScore.detected_pattern}
                  </div>
                </div>
              )}
            </div>

            {/* Orchestration Dimensions */}
            {orchestrationScore?.dimensions && orchestrationScore.dimensions.length > 0 && (
              <div className="space-y-3">
                <div className="text-sm font-medium text-slate-300">Dimensions</div>
                {orchestrationScore.dimensions.map((dim) => (
                  <div key={dim.dimension} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
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
                  </div>
                ))}
              </div>
            )}

            {/* Critical Orchestration Issues */}
            {orchestrationScore?.critical_issues && orchestrationScore.critical_issues.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-700">
                <div className="flex items-center gap-2 text-sm font-medium text-red-400 mb-2">
                  <AlertCircle size={16} />
                  <span>Critical Issues</span>
                </div>
                <div className="space-y-2">
                  {orchestrationScore.critical_issues.map((issue, idx) => (
                    <div
                      key={idx}
                      className="text-sm text-slate-300 bg-red-500/10 border border-red-500/20 rounded-lg p-2"
                    >
                      {issue}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Workflow Diagram */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-lg font-semibold text-white">Workflow Diagram</h3>
            <GitBranch size={20} className="text-blue-400" />
            {isDemoMode && (
              <span className="text-xs px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded">
                Demo Data
              </span>
            )}
            {(selectedNodeId || selectedEdgeId) && (
              <div className="ml-auto text-xs text-slate-400">
                Click {selectedNodeId ? 'node' : 'edge'} for details • Click outside to close
              </div>
            )}
          </div>
          <div className="relative">
            {handoffLoading ? (
              <div className="h-[600px] flex items-center justify-center bg-slate-800 rounded-lg border border-slate-700">
                <div className="text-center">
                  <Activity className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
                  <p className="text-slate-400 text-sm">Loading workflow diagram...</p>
                </div>
              </div>
            ) : handoffAnalysis ? (
              <WorkflowGraphView
                workflow={workflow}
                handoffGraph={handoffAnalysis.handoff_graph}
                handoffMetrics={handoffMetrics}
                height={600}
                onNodeClick={handleNodeClick}
                onEdgeClick={handleEdgeClick}
              />
            ) : null}
            {selectedNodeId && (
              <WorkflowNodeDetails
                agentId={selectedNodeId}
                workflow={workflow}
                onClose={() => setSelectedNodeId(null)}
              />
            )}
            {selectedEdgeId && (
              <WorkflowEdgeDetails
                edgeId={selectedEdgeId}
                handoffMetrics={handoffMetrics}
                workflow={workflow}
                onClose={() => setSelectedEdgeId(null)}
              />
            )}
          </div>
        </section>

        {/* Complexity Metrics */}
        {orchestrationScore?.complexity_metrics && (
          <section>
            <h3 className="text-lg font-semibold text-white mb-4">Complexity Metrics</h3>
            <div className="grid grid-cols-2 gap-3">
              <MetricCard label="Agents" value={orchestrationScore.complexity_metrics.agent_count} />
              <MetricCard label="Nodes" value={orchestrationScore.complexity_metrics.node_count} />
              <MetricCard label="Connections" value={orchestrationScore.complexity_metrics.connection_count} />
              <MetricCard label="Max Depth" value={orchestrationScore.complexity_metrics.max_depth} />
              <MetricCard
                label="Cyclomatic"
                value={orchestrationScore.complexity_metrics.cyclomatic_complexity}
                status={
                  orchestrationScore.complexity_metrics.cyclomatic_complexity <= 10 ? 'good' :
                  orchestrationScore.complexity_metrics.cyclomatic_complexity <= 20 ? 'moderate' :
                  'high'
                }
              />
              <MetricCard
                label="Coupling"
                value={orchestrationScore.complexity_metrics.coupling_ratio.toFixed(2)}
                status={
                  orchestrationScore.complexity_metrics.coupling_ratio < 0.3 ? 'good' :
                  orchestrationScore.complexity_metrics.coupling_ratio < 0.6 ? 'moderate' :
                  'high'
                }
              />
            </div>
          </section>
        )}

        {/* Key Findings */}
        {workflow.key_findings && workflow.key_findings.length > 0 && (
          <section>
            <h3 className="text-lg font-semibold text-white mb-4">Key Findings</h3>
            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700 space-y-2">
              {workflow.key_findings.map((finding, idx) => (
                <div key={idx} className="flex items-start gap-2 text-sm text-slate-300">
                  <span className="text-blue-400 flex-shrink-0">•</span>
                  <span>{finding}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Summary */}
        {workflow.summary && (
          <section>
            <h3 className="text-lg font-semibold text-white mb-4">Summary</h3>
            <div className="bg-slate-800 rounded-lg p-4 border border-slate-700 text-sm text-slate-300">
              {workflow.summary}
            </div>
          </section>
        )}

        {/* Orchestration Improvements */}
        {orchestrationImprovements.length > 0 && (
          <section>
            <h3 className="text-lg font-semibold text-white mb-4">Orchestration Improvements</h3>
            <div className="space-y-3">
              {orchestrationImprovements.map((improvement) => (
                <div
                  key={improvement.id}
                  className="bg-slate-800 rounded-lg p-4 border border-slate-700"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className={clsx(
                        'text-xs font-medium px-2 py-0.5 rounded',
                        improvement.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                        improvement.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                        improvement.severity === 'medium' ? 'bg-amber-500/20 text-amber-400' :
                        'bg-blue-500/20 text-blue-400'
                      )}>
                        {improvement.severity}
                      </span>
                      <span className="text-xs text-slate-500">
                        {improvement.effort} effort
                      </span>
                    </div>
                  </div>
                  <div className="text-sm font-medium text-white mb-1">
                    {improvement.title}
                  </div>
                  <div className="text-sm text-slate-400">
                    {improvement.description}
                  </div>
                  {improvement.estimated_impact && (
                    <div className="text-xs text-slate-500 mt-2">
                      Impact: {improvement.estimated_impact}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Agent Details - SECONDARY (Collapsed by Default) */}
        {workflow.agent_scores && workflow.agent_scores.length > 0 && (
          <section>
            <button
              onClick={() => setShowAgentDetails(!showAgentDetails)}
              className="flex items-center justify-between w-full text-lg font-semibold text-white mb-4 hover:text-blue-400 transition-colors"
            >
              <span>Agent Details ({workflow.agent_scores.length})</span>
              {showAgentDetails ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </button>

            {showAgentDetails && (
              <AgentStatusGrid agents={workflow.agent_scores} isLoading={false} />
            )}
          </section>
        )}
      </div>
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: number | string
  status?: 'good' | 'moderate' | 'high'
}

function MetricCard({ label, value, status }: MetricCardProps) {
  return (
    <div className="bg-slate-800 rounded-lg p-3 border border-slate-700">
      <div className="text-xs text-slate-400 mb-1">{label}</div>
      <div className="flex items-baseline gap-2">
        <div className="text-xl font-bold text-white">{value}</div>
        {status && (
          <div className={clsx(
            'text-xs font-medium',
            status === 'good' ? 'text-green-400' :
            status === 'moderate' ? 'text-amber-400' :
            'text-red-400'
          )}>
            {status === 'good' ? '✓' : status === 'moderate' ? '⚠' : '✗'}
          </div>
        )}
      </div>
    </div>
  )
}
