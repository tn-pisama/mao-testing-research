'use client'

import { useState } from 'react'
import { AgentQualityScore } from '@/lib/api'
import { QualityGradeBadge } from '@/components/quality/QualityGradeBadge'
import { AlertCircle, CheckCircle, AlertTriangle, ChevronDown, ChevronUp, User } from 'lucide-react'
import { cn } from '@/lib/utils'

interface AgentStatusGridProps {
  agents: AgentQualityScore[]
  isLoading?: boolean
}

export function AgentStatusGrid({ agents, isLoading }: AgentStatusGridProps) {
  const [expandedAgentId, setExpandedAgentId] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 bg-zinc-700/50 rounded-xl animate-pulse" />
        ))}
      </div>
    )
  }

  if (agents.length === 0) {
    return (
      <div className="text-center py-12 px-4 bg-zinc-800 rounded-xl border border-zinc-700">
        <User className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
        <p className="text-zinc-400 mb-2">No agent data available</p>
        <p className="text-zinc-500 text-sm">
          Agent quality scores will appear here once workflow assessments are completed
        </p>
      </div>
    )
  }

  return (
    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
      {agents.map((agent) => (
        <AgentCard
          key={agent.agent_id}
          agent={agent}
          isExpanded={expandedAgentId === agent.agent_id}
          onToggleExpand={() =>
            setExpandedAgentId(expandedAgentId === agent.agent_id ? null : agent.agent_id)
          }
        />
      ))}
    </div>
  )
}

interface AgentCardProps {
  agent: AgentQualityScore
  isExpanded: boolean
  onToggleExpand: () => void
}

function AgentCard({ agent, isExpanded, onToggleExpand }: AgentCardProps) {
  const healthStatus = getHealthStatus(agent)

  return (
    <div
      className={cn(
        'bg-zinc-800 rounded-xl border transition-all',
        isExpanded ? 'border-blue-500/50' : 'border-zinc-700',
        'hover:border-zinc-600 cursor-pointer'
      )}
      onClick={onToggleExpand}
    >
      {/* Card Header */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-white font-medium truncate">{agent.agent_name}</h3>
              <QualityGradeBadge grade={agent.grade} size="sm" />
            </div>
            <p className="text-xs text-zinc-400 capitalize">{agent.agent_type}</p>
          </div>
          <div className="ml-2 flex-shrink-0">
            {isExpanded ? (
              <ChevronUp size={18} className="text-zinc-400" />
            ) : (
              <ChevronDown size={18} className="text-zinc-400" />
            )}
          </div>
        </div>

        {/* Health Status */}
        <div className="flex items-center gap-2 mb-3">
          <div className={cn('flex items-center gap-1.5 text-xs font-medium', healthStatus.color)}>
            {healthStatus.icon}
            <span>{healthStatus.label}</span>
          </div>
          {agent.issues_count > 0 && (
            <span className="text-xs text-zinc-500">
              {agent.issues_count} issue{agent.issues_count !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Quick Metrics */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-zinc-700/50 rounded-lg p-2">
            <div className="text-xs text-zinc-400 mb-0.5">Score</div>
            <div className="text-lg font-semibold text-white">
              {(agent.overall_score * 100).toFixed(0)}%
            </div>
          </div>
          <div className="bg-zinc-700/50 rounded-lg p-2">
            <div className="text-xs text-zinc-400 mb-0.5">Critical</div>
            <div className="text-lg font-semibold text-white">
              {agent.critical_issues.length}
            </div>
          </div>
        </div>
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="border-t border-zinc-700 p-4 space-y-4">
          {/* Quality Dimensions */}
          {agent.dimensions && agent.dimensions.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-white mb-2">Quality Dimensions</h4>
              <div className="space-y-2">
                {agent.dimensions.map((dim) => (
                  <div key={dim.dimension} className="flex items-center gap-2">
                    <span className="text-xs text-zinc-400 w-24 capitalize">{dim.dimension}</span>
                    <div className="flex-1 bg-zinc-700 rounded-full h-1.5">
                      <div
                        className={cn(
                          'h-1.5 rounded-full transition-all',
                          dim.score >= 0.8
                            ? 'bg-green-500'
                            : dim.score >= 0.6
                            ? 'bg-blue-500'
                            : dim.score >= 0.4
                            ? 'bg-amber-500'
                            : 'bg-red-500'
                        )}
                        style={{ width: `${dim.score * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-zinc-400 w-12 text-right">
                      {(dim.score * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Critical Issues */}
          {agent.critical_issues.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-white mb-2">Critical Issues</h4>
              <div className="space-y-2">
                {agent.critical_issues.map((issue, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 text-xs text-zinc-300 bg-red-500/10 border border-red-500/20 rounded-lg p-2"
                  >
                    <AlertCircle size={14} className="text-red-400 flex-shrink-0 mt-0.5" />
                    <span>{issue}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* No Critical Issues */}
          {agent.critical_issues.length === 0 && (
            <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-2">
              <CheckCircle size={14} className="flex-shrink-0" />
              <span>No critical issues detected</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function getHealthStatus(agent: AgentQualityScore): {
  label: string
  color: string
  icon: React.ReactNode
} {
  if (agent.critical_issues.length > 0) {
    return {
      label: 'Critical',
      color: 'text-red-400',
      icon: <AlertCircle size={14} />,
    }
  }

  if (agent.issues_count > 3) {
    return {
      label: 'Issues',
      color: 'text-amber-400',
      icon: <AlertTriangle size={14} />,
    }
  }

  if (agent.overall_score < 0.6) {
    return {
      label: 'Needs Attention',
      color: 'text-amber-400',
      icon: <AlertTriangle size={14} />,
    }
  }

  return {
    label: 'Healthy',
    color: 'text-emerald-400',
    icon: <CheckCircle size={14} />,
  }
}
