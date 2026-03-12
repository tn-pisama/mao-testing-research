'use client'

import { useState } from 'react'
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  Clock,
  ExternalLink,
} from 'lucide-react'
import { Card, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import type { HealingRecord } from '@/lib/api'

interface ApprovalQueueProps {
  healings: HealingRecord[]
  isLoading?: boolean
  onApprove: (healingId: string, notes: string) => Promise<void>
  onReject: (healingId: string, notes: string) => Promise<void>
}

function formatTime(isoString: string | null): string {
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

function ApprovalItem({
  healing,
  onApprove,
  onReject,
}: {
  healing: HealingRecord
  onApprove: (healingId: string, notes: string) => Promise<void>
  onReject: (healingId: string, notes: string) => Promise<void>
}) {
  const [notes, setNotes] = useState('')
  const [isApproving, setIsApproving] = useState(false)
  const [isRejecting, setIsRejecting] = useState(false)

  const handleApprove = async () => {
    setIsApproving(true)
    try {
      await onApprove(healing.id, notes)
    } finally {
      setIsApproving(false)
    }
  }

  const handleReject = async () => {
    setIsRejecting(true)
    try {
      await onReject(healing.id, notes)
    } finally {
      setIsRejecting(false)
    }
  }

  const isActing = isApproving || isRejecting

  return (
    <Card>
      <CardContent className="p-4 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <ShieldCheck size={20} className="text-purple-400" />
            </div>
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
          <div className="flex items-center gap-2">
            <Badge variant="warning" size="sm">Awaiting Approval</Badge>
            <span className="text-xs text-zinc-500 flex items-center gap-1">
              <Clock size={12} />
              {formatTime(healing.created_at)}
            </span>
          </div>
        </div>

        {/* Fix Suggestions */}
        {healing.fix_suggestions && healing.fix_suggestions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-zinc-500">Proposed Fixes</p>
            {healing.fix_suggestions.map((suggestion, idx) => (
              <div
                key={suggestion.id || idx}
                className="bg-zinc-800/50 rounded-lg p-3"
              >
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-medium text-white">{suggestion.title}</p>
                  <Badge variant="info" size="sm">
                    {suggestion.confidence}
                  </Badge>
                </div>
                <p className="text-xs text-zinc-400">{suggestion.description}</p>
              </div>
            ))}
          </div>
        )}

        {/* Notes Input */}
        <div>
          <label className="text-xs text-zinc-500 mb-1 block">
            Approval Notes (optional)
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add notes for audit trail..."
            rows={2}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm placeholder:text-zinc-600 focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
          />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2 border-t border-zinc-700">
          <Button
            variant="success"
            size="sm"
            onClick={handleApprove}
            isLoading={isApproving}
            disabled={isActing}
            leftIcon={<CheckCircle2 size={14} />}
          >
            Approve
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={handleReject}
            isLoading={isRejecting}
            disabled={isActing}
            leftIcon={<XCircle size={14} />}
          >
            Reject
          </Button>
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<ExternalLink size={14} />}
            onClick={() => window.open(`/detections/${healing.detection_id}`, '_blank')}
          >
            View Detection
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function ApprovalQueue({
  healings,
  isLoading = false,
  onApprove,
  onReject,
}: ApprovalQueueProps) {
  const pendingApprovals = healings.filter(
    (h) => h.approval_required && h.status === 'pending'
  )

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <div className="animate-pulse space-y-3">
                <div className="h-5 bg-zinc-700 rounded w-1/3" />
                <div className="h-3 bg-zinc-700 rounded w-1/2" />
                <div className="h-16 bg-zinc-700 rounded" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (pendingApprovals.length === 0) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-zinc-400">
          <ShieldCheck size={32} className="mx-auto mb-3 opacity-50" />
          <p className="text-sm">No fixes awaiting approval</p>
          <p className="text-xs text-zinc-500 mt-1">
            Fixes triggered with approval_required will appear here for review
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      {pendingApprovals.map((healing) => (
        <ApprovalItem
          key={healing.id}
          healing={healing}
          onApprove={onApprove}
          onReject={onReject}
        />
      ))}
    </div>
  )
}
