'use client'

import Link from 'next/link'
import type { QualityAssessment } from '@/lib/api'
import { QualityGradeBadge } from '@/components/quality/QualityGradeBadge'
import { AlertCircle, Users, Clock, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'

interface WorkflowListViewProps {
  workflows: QualityAssessment[]
  onSelectWorkflow: (workflowId: string) => void
  selectedWorkflowId: string | null
  isLoading?: boolean
}

function getPatternIcon(pattern: string): string {
  const p = pattern.toLowerCase()
  if (p.includes('sequential')) return '→'
  if (p.includes('fan-out') || p.includes('fanout')) return '⇉'
  if (p.includes('parallel')) return '‖'
  if (p.includes('conditional')) return '⚡'
  return '◆'
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`

  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

export function WorkflowListView({
  workflows,
  onSelectWorkflow,
  selectedWorkflowId,
  isLoading,
}: WorkflowListViewProps) {
  if (isLoading) {
    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
          <div key={i} className="h-48 bg-zinc-700/50 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  if (workflows.length === 0) {
    return (
      <div className="text-center py-16 px-4 bg-zinc-800 rounded-xl border border-zinc-700">
        <div className="text-4xl mb-4">📋</div>
        <p className="text-zinc-400 mb-2 text-lg">No workflows found</p>
        <p className="text-zinc-500 text-sm">
          Workflows will appear here once quality assessments are completed
        </p>
      </div>
    )
  }

  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {workflows.map((workflow) => (
        <WorkflowCard
          key={workflow.workflow_id}
          workflow={workflow}
          isSelected={workflow.workflow_id === selectedWorkflowId}
          onClick={() => onSelectWorkflow(workflow.workflow_id)}
        />
      ))}
    </div>
  )
}

interface WorkflowCardProps {
  workflow: QualityAssessment
  isSelected: boolean
  onClick: () => void
}

function WorkflowCard({ workflow, isSelected, onClick }: WorkflowCardProps) {
  const pattern = workflow.orchestration_score?.detected_pattern || 'Unknown'
  const agentCount = workflow.agent_scores?.length || 0
  const hasCriticalIssues = workflow.critical_issues_count > 0

  return (
    <div
      onClick={onClick}
      className={cn(
        'bg-zinc-800 rounded-xl border p-4 cursor-pointer transition-all hover:border-blue-500/50',
        isSelected ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-zinc-700',
        'hover:shadow-lg hover:shadow-blue-500/10'
      )}
    >
      {/* Header: Grade + Workflow Name */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0 mr-2">
          <h3 className="text-white font-medium truncate mb-1">
            {workflow.workflow_name}
          </h3>
          <div className="text-xs text-zinc-500 truncate">
            ID: {workflow.workflow_id.substring(0, 8)}...
          </div>
        </div>
        <QualityGradeBadge grade={workflow.overall_grade} size="sm" />
      </div>

      {/* Score */}
      <div className="mb-3">
        <div className="flex items-baseline gap-2">
          <span className={cn(
            'text-2xl font-bold',
            workflow.overall_score >= 80 ? 'text-green-400' :
            workflow.overall_score >= 60 ? 'text-blue-400' :
            workflow.overall_score >= 40 ? 'text-amber-400' :
            'text-red-400'
          )}>
            {Math.round(workflow.overall_score)}%
          </span>
          <span className="text-sm text-zinc-400">quality</span>
        </div>
      </div>

      {/* Issues */}
      <div className="mb-3">
        {hasCriticalIssues ? (
          <div className="flex items-center gap-2 text-sm">
            <AlertCircle size={14} className="text-red-400" />
            <span className="text-red-400 font-medium">
              {workflow.critical_issues_count} critical issue{workflow.critical_issues_count !== 1 ? 's' : ''}
            </span>
          </div>
        ) : workflow.total_issues > 0 ? (
          <div className="flex items-center gap-2 text-sm">
            <AlertCircle size={14} className="text-amber-400" />
            <span className="text-amber-400">
              {workflow.total_issues} issue{workflow.total_issues !== 1 ? 's' : ''}
            </span>
          </div>
        ) : (
          <div className="text-sm text-emerald-400">
            ✓ No issues
          </div>
        )}
      </div>

      {/* Metadata Row */}
      <div className="flex items-center justify-between text-xs text-zinc-400 pt-3 border-t border-zinc-700">
        <div className="flex items-center gap-1">
          <span className="text-base">{getPatternIcon(pattern)}</span>
          <span className="capitalize">{pattern}</span>
        </div>
        <div className="flex items-center gap-1">
          <Users size={12} />
          <span>{agentCount}</span>
        </div>
      </div>

      {/* Last Assessed */}
      {workflow.assessed_at && (
        <div className="flex items-center gap-1 text-xs text-zinc-500 mt-2">
          <Clock size={11} />
          <span>{formatTimeAgo(workflow.assessed_at)}</span>
        </div>
      )}

      {/* View Full Button */}
      <Link
        href={`/workflows/${workflow.workflow_id}`}
        onClick={(e) => e.stopPropagation()}
        className="mt-3 w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
      >
        <ExternalLink size={14} />
        View Full Details
      </Link>
    </div>
  )
}
