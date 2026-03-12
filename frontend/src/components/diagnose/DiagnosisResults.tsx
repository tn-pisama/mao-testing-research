'use client'

import { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Zap,
  Activity,
  Loader2,
  type LucideIcon
} from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { TermTooltip, getPlainEnglishTitle } from '../ui/Tooltip'
import type { DiagnoseResult, DiagnoseDetection } from '@/lib/api'

interface DiagnosisResultsProps {
  result: DiagnoseResult
  onApplyAutoFix?: () => Promise<void>
}

const severityConfig = {
  critical: { label: 'Urgent', description: 'Needs immediate attention', variant: 'error' as const, color: 'text-red-400', bg: 'bg-red-500/20' },
  high: { label: 'Important', description: 'Should fix soon', variant: 'warning' as const, color: 'text-orange-400', bg: 'bg-orange-500/20' },
  medium: { label: 'Worth Fixing', description: 'Can cause issues over time', variant: 'info' as const, color: 'text-amber-400', bg: 'bg-amber-500/20' },
  low: { label: 'Minor', description: 'Small improvement opportunity', variant: 'default' as const, color: 'text-zinc-400', bg: 'bg-zinc-500/20' },
}

const categoryIcons: Record<string, LucideIcon> = {
  infinite_loop: Activity,
  state_corruption: AlertTriangle,
  persona_drift: Zap,
  coordination_deadlock: XCircle,
}

// Plain English category names
const categoryNames: Record<string, string> = {
  infinite_loop: 'Running Forever',
  state_corruption: 'Data Scrambled',
  persona_drift: 'AI Changed',
  coordination_deadlock: 'Steps Stuck',
}

function DetectionItem({ detection }: { detection: DiagnoseDetection }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const severity = (detection.severity as keyof typeof severityConfig) || 'medium'
  const severityStyle = severityConfig[severity]
  const Icon = categoryIcons[detection.category] || AlertTriangle

  return (
    <div className="border border-zinc-700 rounded-lg overflow-hidden">
      <div
        className="p-3 cursor-pointer hover:bg-zinc-800/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-1.5 rounded-lg ${severityStyle.bg}`}>
              <Icon size={16} className={severityStyle.color} />
            </div>
            <div>
              <p className="text-sm font-medium text-white">
                {getPlainEnglishTitle(detection.category) || detection.title}
              </p>
              <p className="text-xs text-zinc-500">
                {categoryNames[detection.category] || detection.category.replace(/_/g, ' ')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <TermTooltip term={detection.category}>
              <Badge variant={severityStyle.variant} size="sm">
                {severityStyle.label}
              </Badge>
            </TermTooltip>
            <TermTooltip term="confidence">
              <span className="text-xs text-zinc-500">
                {Math.round(detection.confidence * 100)}% certain
              </span>
            </TermTooltip>
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </div>
        </div>
      </div>

      {isExpanded && (
        <div className="border-t border-zinc-700 p-3 space-y-3 bg-zinc-800/30">
          {/* What happened - plain explanation */}
          <div>
            <p className="text-xs text-zinc-500 mb-1">What Happened</p>
            <p className="text-sm text-zinc-300">{detection.description}</p>
          </div>

          {/* What you can do about it */}
          {detection.suggested_fix && (
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
              <p className="text-xs text-blue-400 mb-1">How to Fix This</p>
              <p className="text-sm text-blue-300">{detection.suggested_fix}</p>
            </div>
          )}

          {/* Technical details - hidden by default */}
          {((detection.evidence && detection.evidence.length > 0) ||
            (detection.affected_spans && detection.affected_spans.length > 0)) && (
            <details className="group">
              <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-400">
                Technical Details (click to expand)
              </summary>
              <div className="mt-2 space-y-3">
                {detection.evidence && detection.evidence.length > 0 && (
                  <div>
                    <p className="text-xs text-zinc-500 mb-2">Evidence</p>
                    <div className="space-y-1">
                      {detection.evidence.map((ev, idx) => (
                        <div
                          key={idx}
                          className="text-xs text-zinc-400 bg-zinc-800/50 px-2 py-1 rounded"
                        >
                          {typeof ev === 'string' ? ev : JSON.stringify(ev)}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {detection.affected_spans && detection.affected_spans.length > 0 && (
                  <div>
                    <p className="text-xs text-zinc-500 mb-1">Affected Steps</p>
                    <div className="flex flex-wrap gap-1">
                      {detection.affected_spans.map((span, idx) => (
                        <span
                          key={idx}
                          className="text-xs text-zinc-400 bg-zinc-700 px-2 py-0.5 rounded"
                        >
                          {span}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  )
}

export function DiagnosisResults({ result, onApplyAutoFix }: DiagnosisResultsProps) {
  const [isApplying, setIsApplying] = useState(false)

  const handleApplyAutoFix = async () => {
    if (!onApplyAutoFix) return
    setIsApplying(true)
    try {
      await onApplyAutoFix()
    } finally {
      setIsApplying(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Summary Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Workflow Analysis</CardTitle>
            <Badge
              variant={result.has_failures ? 'error' : 'success'}
              size="sm"
            >
              {result.has_failures ? `${result.failure_count} Problems Found` : 'All Good!'}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <TermTooltip term="trace">
                <p className="text-xs text-zinc-500 mb-1">Workflow Run ID</p>
              </TermTooltip>
              <p className="text-sm text-white font-mono">{result.trace_id.slice(0, 12)}...</p>
            </div>
            <div>
              <TermTooltip term="span">
                <p className="text-xs text-zinc-500 mb-1">Total Steps</p>
              </TermTooltip>
              <p className="text-sm text-white">{result.total_spans}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-1">Steps with Errors</p>
              <p className="text-sm text-white">{result.error_spans}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-1">Analysis Time</p>
              <p className="text-sm text-white">{result.detection_time_ms}ms</p>
            </div>
          </div>

          {result.detectors_run && result.detectors_run.length > 0 && (
            <details className="mt-4 group">
              <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-400">
                Checks Performed ({result.detectors_run.length})
              </summary>
              <div className="mt-2 flex flex-wrap gap-1">
                {result.detectors_run.map((detector, idx) => (
                  <span
                    key={idx}
                    className="text-xs text-zinc-400 bg-zinc-700 px-2 py-0.5 rounded"
                  >
                    {detector.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </details>
          )}
        </CardContent>
      </Card>

      {/* Root Cause - Why this is happening */}
      {result.root_cause_explanation && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <AlertTriangle size={20} className="text-red-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-white mb-1">Why This Is Happening</p>
                <p className="text-sm text-zinc-300">{result.root_cause_explanation}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Auto-Fix Preview - We can fix this for you */}
      {result.self_healing_available && result.auto_fix_preview && (
        <Card className="border-green-500/30">
          <CardContent className="p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-green-500/20 rounded-lg">
                  <Sparkles size={20} className="text-green-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-green-400 mb-1">We Can Fix This For You</p>
                  <p className="text-sm text-zinc-300 mb-2">{result.auto_fix_preview.description}</p>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-zinc-500">
                      What we&apos;ll do: <span className="text-zinc-300">{result.auto_fix_preview.action}</span>
                    </span>
                    <TermTooltip term="confidence">
                      <span className="text-zinc-500">
                        {Math.round(result.auto_fix_preview.confidence * 100)}% certain this will work
                      </span>
                    </TermTooltip>
                  </div>
                </div>
              </div>
              {onApplyAutoFix && (
                <Button
                  variant="success"
                  size="sm"
                  onClick={handleApplyAutoFix}
                  isLoading={isApplying}
                  leftIcon={isApplying ? <Loader2 className="animate-spin" size={14} /> : <Sparkles size={14} />}
                >
                  Fix This Now
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Detections List - Problems we found */}
      {result.all_detections && result.all_detections.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Problems Found ({result.all_detections.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {result.all_detections.map((detection, idx) => (
                <DetectionItem key={idx} detection={detection} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* No Failures State - Everything is working */}
      {!result.has_failures && (
        <Card>
          <CardContent className="p-8 text-center">
            <CheckCircle2 size={48} className="mx-auto mb-4 text-green-400 opacity-50" />
            <p className="text-lg font-medium text-white mb-2">Everything Looks Good!</p>
            <p className="text-sm text-zinc-400">
              We analyzed your workflow and found no problems. Nice work!
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
