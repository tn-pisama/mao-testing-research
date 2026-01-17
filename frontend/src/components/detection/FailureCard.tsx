'use client'

import { useState } from 'react'
import {
  AlertTriangle,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Loader2
} from 'lucide-react'
import { Card, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { FixPreviewModal } from '../healing/FixPreviewModal'
import type { Detection, N8nConnection, WorkflowDiff } from '@/lib/api'

interface FailureCardProps {
  detection: Detection
  connections?: N8nConnection[]
  onGenerateFix?: (detectionId: string) => Promise<{
    fix?: { type: string; description: string; confidence: string }
    diff?: WorkflowDiff
  }>
  onApplyFix?: (detectionId: string, connectionId: string, stage: boolean) => Promise<void>
}

const severityConfig = {
  critical: { label: 'Critical', variant: 'error' as const, color: 'text-red-400', bg: 'bg-red-500/20' },
  high: { label: 'High', variant: 'warning' as const, color: 'text-orange-400', bg: 'bg-orange-500/20' },
  medium: { label: 'Medium', variant: 'info' as const, color: 'text-amber-400', bg: 'bg-amber-500/20' },
  low: { label: 'Low', variant: 'default' as const, color: 'text-slate-400', bg: 'bg-slate-500/20' },
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

export function FailureCard({
  detection,
  connections = [],
  onGenerateFix,
  onApplyFix
}: FailureCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [fixData, setFixData] = useState<{
    fix?: { type: string; description: string; confidence: string }
    diff?: WorkflowDiff
  } | null>(null)
  const [isApplying, setIsApplying] = useState(false)

  const severity = (detection.details?.severity as keyof typeof severityConfig) || 'medium'
  const severityStyle = severityConfig[severity] || severityConfig.medium

  const handleGenerateFix = async () => {
    if (!onGenerateFix) return

    setIsGenerating(true)
    try {
      const result = await onGenerateFix(detection.id)
      setFixData(result)
      setShowPreview(true)
    } catch (err) {
      console.error('Failed to generate fix:', err)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleApplyFix = async (connectionId: string, stage: boolean) => {
    if (!onApplyFix) return

    setIsApplying(true)
    try {
      await onApplyFix(detection.id, connectionId, stage)
      setShowPreview(false)
      setFixData(null)
    } catch (err) {
      console.error('Failed to apply fix:', err)
    } finally {
      setIsApplying(false)
    }
  }

  return (
    <>
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          {/* Header */}
          <div
            className="p-4 cursor-pointer hover:bg-slate-800/50 transition-colors"
            onClick={() => setIsExpanded(!isExpanded)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${severityStyle.bg}`}>
                  <AlertTriangle size={20} className={severityStyle.color} />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">
                    {detection.detection_type.replace(/_/g, ' ')}
                  </p>
                  <p className="text-xs text-slate-500">
                    Trace: {detection.trace_id.slice(0, 8)}...
                    {detection.method && ` | via ${detection.method.replace(/_/g, ' ')}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Badge variant={severityStyle.variant} size="sm">
                  {severityStyle.label}
                </Badge>
                <span className="text-xs text-slate-500">
                  {Math.round(detection.confidence * 100)}% confidence
                </span>
                <div className="flex items-center gap-1 text-xs text-slate-500">
                  <Clock size={12} />
                  {formatTime(detection.created_at)}
                </div>
                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
            </div>
          </div>

          {/* Expanded Content */}
          {isExpanded && (
            <div className="border-t border-slate-700 p-4 space-y-4">
              {/* Explanation */}
              {detection.explanation && (
                <div>
                  <p className="text-xs text-slate-500 mb-1">Explanation</p>
                  <p className="text-sm text-slate-300">{detection.explanation}</p>
                </div>
              )}

              {/* Business Impact */}
              {detection.business_impact && (
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3">
                  <p className="text-xs text-amber-400 mb-1">Business Impact</p>
                  <p className="text-sm text-amber-300">{detection.business_impact}</p>
                </div>
              )}

              {/* Suggested Action */}
              {detection.suggested_action && (
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
                  <p className="text-xs text-blue-400 mb-1">Suggested Action</p>
                  <p className="text-sm text-blue-300">{detection.suggested_action}</p>
                </div>
              )}

              {/* Details */}
              {detection.details && Object.keys(detection.details).length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 mb-2">Details</p>
                  <div className="bg-slate-800/50 rounded-lg p-3">
                    <pre className="text-xs text-slate-400 overflow-x-auto">
                      {JSON.stringify(detection.details, null, 2)}
                    </pre>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2 pt-2 border-t border-slate-700">
                {onGenerateFix && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleGenerateFix}
                    isLoading={isGenerating}
                    leftIcon={isGenerating ? <Loader2 className="animate-spin" size={14} /> : <Sparkles size={14} />}
                  >
                    Generate Fix
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<ExternalLink size={14} />}
                  onClick={() => window.open(`/traces/${detection.trace_id}`, '_blank')}
                >
                  View Trace
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Fix Preview Modal */}
      <FixPreviewModal
        isOpen={showPreview}
        onClose={() => {
          setShowPreview(false)
          setFixData(null)
        }}
        onApply={handleApplyFix}
        connections={connections}
        fix={fixData?.fix}
        diff={fixData?.diff}
        isApplying={isApplying}
      />
    </>
  )
}
