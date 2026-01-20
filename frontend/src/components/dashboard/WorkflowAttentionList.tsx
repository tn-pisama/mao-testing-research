'use client'

import { AlertTriangle, ChevronRight, Wrench } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import Link from 'next/link'
import type { Detection } from '@/lib/api'

interface WorkflowAttentionListProps {
  detections: Detection[]
  isLoading?: boolean
}

function getSeverity(details?: { severity?: string }): 'critical' | 'high' | 'medium' | 'low' {
  const severity = details?.severity
  if (severity === 'critical' || severity === 'high' || severity === 'medium' || severity === 'low') {
    return severity
  }
  return 'medium'
}

function formatTime(isoString: string): string {
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

function getPlainEnglishType(type: string): string {
  const mappings: Record<string, string> = {
    infinite_loop: 'Stuck in a loop',
    state_corruption: 'Data got corrupted',
    persona_drift: 'Behavior changed unexpectedly',
    coordination_failure: 'Communication breakdown',
    tool_misuse: 'Tool used incorrectly',
    cost_anomaly: 'Unusual costs detected',
    timeout: 'Taking too long',
    error_pattern: 'Repeated errors',
  }
  return mappings[type] || type.replace(/_/g, ' ')
}

export function WorkflowAttentionList({ detections, isLoading }: WorkflowAttentionListProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-64 animate-pulse bg-slate-700 rounded-lg" />
      </Card>
    )
  }

  // Filter to high priority issues
  const needsAttention = detections.filter(d => {
    const severity = getSeverity(d.details as { severity?: string })
    return severity === 'critical' || severity === 'high'
  }).slice(0, 5)

  return (
    <Card className="col-span-2">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-amber-400" />
            Workflows Needing Attention
          </CardTitle>
          {needsAttention.length > 0 && (
            <span className="px-2 py-1 text-xs font-medium bg-red-500/20 text-red-400 rounded-full">
              {needsAttention.length} issues
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {needsAttention.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-green-400 text-lg mb-2">All Clear!</div>
            <p className="text-slate-400 text-sm">
              No workflows need immediate attention. Great work!
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {needsAttention.map((detection) => {
              const severity = getSeverity(detection.details as { severity?: string })
              return (
                <div
                  key={detection.id}
                  className="flex items-center justify-between p-4 bg-slate-800/50 rounded-lg border border-slate-700"
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-2 h-2 rounded-full ${
                      severity === 'critical' ? 'bg-red-500' : 'bg-yellow-500'
                    }`} />
                    <div>
                      <p className="text-sm font-medium text-white">
                        {getPlainEnglishType(detection.detection_type)}
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatTime(detection.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/healing?detection=${detection.id}`}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
                    >
                      <Wrench size={14} />
                      Fix
                    </Link>
                    <Link
                      href={`/detections/${detection.id}`}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm text-slate-400 hover:text-white transition-colors"
                    >
                      Details
                      <ChevronRight size={14} />
                    </Link>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
