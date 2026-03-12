'use client'

import { Clock, ChevronDown, ChevronUp, ShieldCheck, XCircle } from 'lucide-react'
import { Badge } from '../ui/Badge'
import type { HealingRecord } from '@/lib/api'

const statusConfig = {
  pending: { label: 'Waiting', description: 'Fix is being prepared', variant: 'warning' as const, icon: Clock },
  in_progress: { label: 'Working on it', description: 'Fix is being applied', variant: 'info' as const, icon: Clock },
  staged: { label: 'Ready to test', description: 'Test it before going live', variant: 'warning' as const, icon: Clock },
  applied: { label: 'Fixed!', description: 'The fix is active', variant: 'success' as const, icon: Clock },
  failed: { label: "Couldn't fix", description: 'Something went wrong', variant: 'error' as const, icon: XCircle },
  rolled_back: { label: 'Undone', description: 'Fix was removed', variant: 'default' as const, icon: Clock },
  rejected: { label: 'Not applied', description: 'Fix was declined', variant: 'error' as const, icon: XCircle },
} as const

const deploymentStageConfig = {
  staged: { label: 'Ready to test', description: 'Fix is prepared but not live yet', color: 'text-amber-400 bg-amber-500/20' },
  promoted: { label: 'Live', description: 'Fix is active in your workflow', color: 'text-green-400 bg-green-500/20' },
  rejected: { label: 'Not applied', description: 'Fix was declined after review', color: 'text-red-400 bg-red-500/20' },
  rolled_back: { label: 'Undone', description: 'Fix was removed and workflow restored', color: 'text-zinc-400 bg-zinc-500/20' },
} as const

export function formatTime(isoString: string | null): string {
  if (!isoString) return 'N/A'
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

export function getStatusConfig(status: string) {
  return statusConfig[status as keyof typeof statusConfig] || statusConfig.pending
}

export function getDeploymentStageConfig(stage: string | undefined | null) {
  if (!stage) return null
  return deploymentStageConfig[stage as keyof typeof deploymentStageConfig] || null
}

interface HealingCardHeaderProps {
  healing: HealingRecord
  isExpanded: boolean
  onToggle: () => void
}

export function HealingCardHeader({ healing, isExpanded, onToggle }: HealingCardHeaderProps) {
  const status = getStatusConfig(healing.status)
  const StatusIcon = status.icon
  const deploymentStage = getDeploymentStageConfig(healing.deployment_stage)

  return (
    <div
      className="p-4 cursor-pointer hover:bg-zinc-800/50 transition-colors"
      onClick={onToggle}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <StatusIcon
            size={20}
            className={
              healing.status === 'in_progress' ? 'animate-spin text-blue-400' :
              healing.status === 'applied' ? 'text-green-400' :
              healing.status === 'failed' || healing.status === 'rejected' ? 'text-red-400' :
              healing.status === 'staged' ? 'text-amber-400' :
              'text-zinc-400'
            }
          />
          <div>
            <p className="text-sm font-medium text-white">
              {healing.fix_type.replace(/_/g, ' ')}
            </p>
            <p className="text-xs text-zinc-500">
              Detection: {healing.detection_id.slice(0, 8)}...
              {healing.workflow_id && ` | Workflow: ${healing.workflow_id}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={status.variant} size="sm">
            {status.label}
          </Badge>
          {healing.approval_required && healing.status === 'pending' && (
            <Badge variant="info" size="sm">
              Awaiting Approval
            </Badge>
          )}
          {deploymentStage && (
            <span className={`text-xs px-2 py-1 rounded ${deploymentStage.color}`}>
              {deploymentStage.label}
            </span>
          )}
          {healing.validation_status === 'passed' && (
            <span className="text-xs px-2 py-1 rounded bg-green-500/20 text-green-400 flex items-center gap-1">
              <ShieldCheck size={12} />
              Verified
            </span>
          )}
          {healing.validation_status === 'failed' && (
            <span className="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 flex items-center gap-1">
              <XCircle size={12} />
              Unverified
            </span>
          )}
          <div className="flex items-center gap-1 text-xs text-zinc-500">
            <Clock size={12} />
            {formatTime(healing.created_at)}
          </div>
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>
    </div>
  )
}
