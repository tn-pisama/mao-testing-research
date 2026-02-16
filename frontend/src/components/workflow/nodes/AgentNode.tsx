'use client'

import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { QualityGradeBadge } from '@/components/quality/QualityGradeBadge'
import { AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { getHealthColor } from '@/lib/workflow-layout'

interface AgentNodeData {
  label: string
  agentType?: string
  score: number
  grade: string
  issuesCount: number
  criticalIssues: string[]
  hasIssues: boolean
  hasCritical: boolean
}

export const AgentNode = memo(({ data, selected }: NodeProps<AgentNodeData>) => {
  const borderColor = getHealthColor(data.score)
  const borderWidth = data.hasCritical ? 3 : selected ? 2 : 1.5

  return (
    <div
      className={clsx(
        'px-4 py-3 rounded-lg bg-slate-800 min-w-[180px] transition-all',
        selected && 'ring-2 ring-blue-500 ring-offset-2 ring-offset-slate-900'
      )}
      style={{
        borderWidth: `${borderWidth}px`,
        borderStyle: 'solid',
        borderColor,
        opacity: 0.85 + data.score * 0.15, // Higher score = more opaque
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-slate-600 !border-2 !border-slate-400"
      />

      {/* Header: Agent Name + Grade */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="font-medium text-white text-sm truncate flex-1">{data.label}</div>
        <QualityGradeBadge grade={data.grade} size="sm" />
      </div>

      {/* Agent Type */}
      {data.agentType && (
        <div className="text-xs text-slate-400 mb-2 capitalize">{data.agentType}</div>
      )}

      {/* Score */}
      <div className="flex items-baseline gap-2 mb-2">
        <span
          className="text-lg font-bold"
          style={{ color: borderColor }}
        >
          {(data.score * 100).toFixed(0)}%
        </span>
        <span className="text-xs text-slate-400">health</span>
      </div>

      {/* Issues Badge */}
      {data.hasIssues ? (
        <div className="flex items-center gap-1.5 text-xs">
          <AlertTriangle
            size={12}
            className={data.hasCritical ? 'text-red-400' : 'text-amber-400'}
          />
          <span className={data.hasCritical ? 'text-red-400' : 'text-amber-400'}>
            {data.issuesCount} issue{data.issuesCount !== 1 ? 's' : ''}
            {data.hasCritical && ' (critical)'}
          </span>
        </div>
      ) : (
        <div className="text-xs text-emerald-400">✓ No issues</div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-slate-600 !border-2 !border-slate-400"
      />
    </div>
  )
})

AgentNode.displayName = 'AgentNode'
