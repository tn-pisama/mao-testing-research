'use client'

import { useParams } from 'next/navigation'
import { useState, useRef } from 'react'
import dynamic from 'next/dynamic'
import Link from 'next/link'
import { useQualityAssessmentsQuery } from '@/hooks/useQueries'
import { Skeleton } from '@/components/ui/Skeleton'
import { WorkflowNodeDetails } from '@/components/workflow/WorkflowNodeDetails'

const WorkflowGraphView = dynamic(
  () => import('@/components/workflow/WorkflowGraphView').then(mod => ({ default: mod.WorkflowGraphView })),
  { ssr: false, loading: () => <Skeleton className="h-[600px] rounded-xl" /> }
)
import { WorkflowEdgeDetails } from '@/components/workflow/WorkflowEdgeDetails'
import { QualityGradeBadge } from '@/components/quality/QualityGradeBadge'
import { exportReactFlowAsImage } from '@/lib/export-utils'
import { useHandoffAnalysis } from '@/hooks/useHandoffAnalysis'
import {
  ArrowLeft,
  Download,
  Share2,
  Maximize2,
  TrendingUp,
  AlertCircle,
  GitBranch,
  Activity,
} from 'lucide-react'
import { cn } from '@/lib/utils'

export default function WorkflowPage() {
  const params = useParams()
  const _workflowId = params.id as string

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const reactFlowRef = useRef<HTMLDivElement>(null)

  // Fetch workflow data
  const { assessments: workflows, isLoading } = useQualityAssessmentsQuery()

  const workflow = workflows[0]

  // Load handoff analysis with API fallback to demo data
  const { handoffAnalysis, handoffMetrics, isLoading: handoffLoading, isDemoMode } = useHandoffAnalysis(workflow)

  const handleNodeClick = (nodeId: string) => {
    if (nodeId === 'start' || nodeId === 'end') return
    setSelectedNodeId(nodeId)
    setSelectedEdgeId(null) // Close edge details if open
  }

  const handleEdgeClick = (edgeId: string) => {
    setSelectedEdgeId(edgeId)
    setSelectedNodeId(null) // Close node details if open
  }

  const handleShare = () => {
    const url = window.location.href
    navigator.clipboard.writeText(url)
    // Could add a toast notification here
    alert('Workflow URL copied to clipboard!')
  }

  const handleExport = async () => {
    if (!reactFlowRef.current || !workflow) {
      alert('Unable to export: diagram not ready')
      return
    }

    setIsExporting(true)
    try {
      const filename = `${workflow.workflow_name.replace(/\s+/g, '-')}-${workflow.workflow_id.substring(0, 8)}`
      await exportReactFlowAsImage(reactFlowRef.current, {
        filename,
        format: 'png',
        scale: 3, // High resolution
      })
    } catch (err) {
      console.error('Export failed:', err)
      alert('Export failed. Please try again.')
    } finally {
      setIsExporting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
          <p className="text-zinc-400">Loading workflow...</p>
        </div>
      </div>
    )
  }

  if (!workflow) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h1 className="text-xl font-bold text-white mb-2">Workflow Not Found</h1>
          <p className="text-zinc-400 mb-4">The workflow you&apos;re looking for doesn&apos;t exist.</p>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300"
          >
            <ArrowLeft size={16} />
            Back to Dashboard
          </Link>
        </div>
      </div>
    )
  }

  const orchestrationScore = workflow.orchestration_score

  return (
    <div className={cn(
      'min-h-screen bg-zinc-950',
      isFullscreen ? 'fixed inset-0 z-50' : ''
    )}>
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="px-6 py-4">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm mb-3">
            <Link href="/dashboard" className="text-zinc-400 hover:text-white transition-colors">
              Dashboard
            </Link>
            <span className="text-zinc-600">/</span>
            <Link href="/quality" className="text-zinc-400 hover:text-white transition-colors">
              Quality
            </Link>
            <span className="text-zinc-600">/</span>
            <span className="text-white font-medium">Workflow</span>
          </div>

          {/* Title and Actions */}
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-bold text-white mb-2 truncate">
                {workflow.workflow_name}
              </h1>
              <div className="flex items-center gap-4 text-sm text-zinc-400">
                <span>ID: {workflow.workflow_id}</span>
                {orchestrationScore?.detected_pattern && (
                  <div className="flex items-center gap-1.5">
                    <GitBranch size={14} />
                    <span className="capitalize">{orchestrationScore.detected_pattern}</span>
                  </div>
                )}
                <div className="flex items-center gap-1.5">
                  <Activity size={14} />
                  <span>{workflow.agent_scores?.length || 0} agents</span>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleShare}
                className="flex items-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors"
              >
                <Share2 size={16} />
                Share
              </button>
              <button
                onClick={handleExport}
                disabled={isExporting}
                className="flex items-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Download size={16} className={isExporting ? 'animate-pulse' : ''} />
                {isExporting ? 'Exporting...' : 'Export'}
              </button>
              <button
                onClick={() => setIsFullscreen(!isFullscreen)}
                className="flex items-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors"
              >
                <Maximize2 size={16} />
                {isFullscreen ? 'Exit' : 'Fullscreen'}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex h-[calc(100vh-140px)]">
        {/* Left Sidebar - Metrics */}
        <aside className="w-80 border-r border-zinc-800 bg-zinc-900/50 overflow-y-auto">
          <div className="p-6 space-y-6">
            {/* Overall Quality */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp size={18} className="text-purple-400" />
                <h2 className="text-lg font-semibold text-white">Overall Quality</h2>
                {isDemoMode && (
                  <span className="text-xs px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded">
                    Demo Data
                  </span>
                )}
              </div>
              <div className="bg-zinc-800 rounded-lg p-4 border border-zinc-700">
                <div className="flex items-center gap-4 mb-3">
                  <QualityGradeBadge grade={workflow.overall_grade} size="lg" />
                  <div>
                    <div className={cn(
                      'text-3xl font-bold',
                      workflow.overall_score >= 0.8 ? 'text-green-400' :
                      workflow.overall_score >= 0.6 ? 'text-blue-400' :
                      workflow.overall_score >= 0.4 ? 'text-amber-400' :
                      'text-red-400'
                    )}>
                      {(workflow.overall_score * 100).toFixed(0)}%
                    </div>
                    <div className="text-xs text-zinc-400">Health Score</div>
                  </div>
                </div>
              </div>
            </section>

            {/* Orchestration Metrics */}
            {orchestrationScore && (
              <section>
                <h3 className="text-sm font-semibold text-white mb-3">Orchestration</h3>
                <div className="space-y-2">
                  {orchestrationScore.dimensions?.map((dim) => (
                    <div key={dim.dimension} className="bg-zinc-800/50 rounded-lg p-3">
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="text-zinc-300 capitalize">{dim.dimension}</span>
                        <span className={cn(
                          'font-semibold',
                          dim.score >= 0.8 ? 'text-green-400' :
                          dim.score >= 0.6 ? 'text-blue-400' :
                          'text-amber-400'
                        )}>
                          {(dim.score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="bg-zinc-700 rounded-full h-1 overflow-hidden">
                        <div
                          className={cn(
                            'h-1 rounded-full',
                            dim.score >= 0.8 ? 'bg-green-500' :
                            dim.score >= 0.6 ? 'bg-blue-500' :
                            'bg-amber-500'
                          )}
                          style={{ width: `${dim.score * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Complexity Metrics */}
            {orchestrationScore?.complexity_metrics && (
              <section>
                <h3 className="text-sm font-semibold text-white mb-3">Complexity</h3>
                <div className="grid grid-cols-2 gap-2">
                  <MetricCard
                    label="Agents"
                    value={orchestrationScore.complexity_metrics.agent_count}
                  />
                  <MetricCard
                    label="Nodes"
                    value={orchestrationScore.complexity_metrics.node_count}
                  />
                  <MetricCard
                    label="Connections"
                    value={orchestrationScore.complexity_metrics.connection_count}
                  />
                  <MetricCard
                    label="Max Depth"
                    value={orchestrationScore.complexity_metrics.max_depth}
                  />
                </div>
              </section>
            )}

            {/* Critical Issues */}
            {orchestrationScore?.critical_issues && orchestrationScore.critical_issues.length > 0 && (
              <section>
                <div className="flex items-center gap-2 mb-3">
                  <AlertCircle size={16} className="text-red-400" />
                  <h3 className="text-sm font-semibold text-red-400">Critical Issues</h3>
                </div>
                <div className="space-y-2">
                  {orchestrationScore.critical_issues.map((issue, idx) => (
                    <div
                      key={idx}
                      className="text-xs text-zinc-300 bg-red-500/10 border border-red-500/20 rounded-lg p-2"
                    >
                      {issue}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Key Findings */}
            {workflow.key_findings && workflow.key_findings.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-white mb-3">Key Findings</h3>
                <div className="space-y-2">
                  {workflow.key_findings.map((finding, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs text-zinc-300">
                      <span className="text-blue-400 flex-shrink-0">•</span>
                      <span>{finding}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        </aside>

        {/* Center - Workflow Diagram */}
        <main className="flex-1 relative bg-zinc-900">
          {handoffLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center">
                <Activity className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
                <p className="text-zinc-400">Loading workflow diagram...</p>
              </div>
            </div>
          ) : handoffAnalysis ? (
            <WorkflowGraphView
              workflow={workflow}
              handoffGraph={handoffAnalysis.handoff_graph}
              handoffMetrics={handoffMetrics}
              height={window.innerHeight - 140}
              onNodeClick={handleNodeClick}
              onEdgeClick={handleEdgeClick}
              exportRef={reactFlowRef}
            />
          ) : null}

          {/* Node Details Overlay */}
          {selectedNodeId && (
            <WorkflowNodeDetails
              agentId={selectedNodeId}
              workflow={workflow}
              onClose={() => setSelectedNodeId(null)}
            />
          )}

          {/* Edge Details Overlay */}
          {selectedEdgeId && (
            <WorkflowEdgeDetails
              edgeId={selectedEdgeId}
              handoffMetrics={handoffMetrics}
              workflow={workflow}
              onClose={() => setSelectedEdgeId(null)}
            />
          )}
        </main>
      </div>
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: number | string
}

function MetricCard({ label, value }: MetricCardProps) {
  return (
    <div className="bg-zinc-800/50 rounded-lg p-2.5">
      <div className="text-xs text-zinc-400 mb-0.5">{label}</div>
      <div className="text-lg font-bold text-white">{value}</div>
    </div>
  )
}
