'use client'

import { DiagnoseResult, DiagnoseDetection } from '@/lib/api'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Zap,
  ChevronDown,
  ChevronRight,
  Wrench,
  Activity,
  Target,
  Lightbulb
} from 'lucide-react'
import { clsx } from 'clsx'
import { useState } from 'react'

interface DiagnosisResultsProps {
  result: DiagnoseResult
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  }[severity] || 'bg-slate-500/20 text-slate-400 border-slate-500/30'

  return (
    <span className={clsx('px-2 py-0.5 text-xs font-medium rounded-full border', styles)}>
      {severity.toUpperCase()}
    </span>
  )
}

function DetectionCard({ detection, isExpanded, onToggle }: {
  detection: DiagnoseDetection
  isExpanded: boolean
  onToggle: () => void
}) {
  return (
    <div className="bg-slate-800/50 rounded-lg border border-slate-700 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full p-4 flex items-center justify-between hover:bg-slate-700/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-slate-400" />
          )}
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className="font-medium text-white">{detection.title}</span>
              <SeverityBadge severity={detection.severity} />
            </div>
            <p className="text-sm text-slate-400 mt-1">{detection.category}</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm text-slate-400">
            {Math.round(detection.confidence * 100)}% confidence
          </div>
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 border-t border-slate-700 pt-4 space-y-4">
          <div>
            <h4 className="text-sm font-medium text-slate-300 mb-2">Description</h4>
            <p className="text-sm text-slate-400">{detection.description}</p>
          </div>

          {detection.evidence && detection.evidence.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-slate-300 mb-2">Evidence</h4>
              <pre className="text-xs text-slate-400 bg-slate-900 p-3 rounded-lg overflow-x-auto">
                {JSON.stringify(detection.evidence, null, 2)}
              </pre>
            </div>
          )}

          {detection.affected_spans && detection.affected_spans.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-slate-300 mb-2">Affected Spans</h4>
              <div className="flex flex-wrap gap-1">
                {detection.affected_spans.map((spanId, i) => (
                  <span key={i} className="px-2 py-1 text-xs bg-slate-700 text-slate-300 rounded">
                    {spanId}
                  </span>
                ))}
              </div>
            </div>
          )}

          {detection.suggested_fix && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <Lightbulb className="w-4 h-4 text-emerald-400" />
                <h4 className="text-sm font-medium text-emerald-400">Suggested Fix</h4>
              </div>
              <p className="text-sm text-slate-300">{detection.suggested_fix}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function DiagnosisResults({ result }: DiagnosisResultsProps) {
  const [expandedDetections, setExpandedDetections] = useState<Set<number>>(new Set([0]))

  const toggleDetection = (index: number) => {
    setExpandedDetections(prev => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  return (
    <div className="space-y-6">
      {/* Summary Header */}
      <div className={clsx(
        'p-4 rounded-xl border',
        result.has_failures
          ? 'bg-red-500/10 border-red-500/30'
          : 'bg-emerald-500/10 border-emerald-500/30'
      )}>
        <div className="flex items-center gap-3">
          {result.has_failures ? (
            <AlertTriangle className="w-6 h-6 text-red-400" />
          ) : (
            <CheckCircle2 className="w-6 h-6 text-emerald-400" />
          )}
          <div>
            <h2 className={clsx(
              'text-lg font-semibold',
              result.has_failures ? 'text-red-400' : 'text-emerald-400'
            )}>
              {result.has_failures
                ? `${result.failure_count} Issue${result.failure_count !== 1 ? 's' : ''} Detected`
                : 'No Issues Detected'
              }
            </h2>
            <p className="text-sm text-slate-400">
              Analyzed {result.total_spans} spans in {result.detection_time_ms}ms
            </p>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Activity className="w-3.5 h-3.5" />
            Total Spans
          </div>
          <div className="text-xl font-semibold text-white">{result.total_spans}</div>
        </div>
        <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <AlertTriangle className="w-3.5 h-3.5" />
            Error Spans
          </div>
          <div className="text-xl font-semibold text-white">{result.error_spans}</div>
        </div>
        <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Zap className="w-3.5 h-3.5" />
            Total Tokens
          </div>
          <div className="text-xl font-semibold text-white">{result.total_tokens.toLocaleString()}</div>
        </div>
        <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Clock className="w-3.5 h-3.5" />
            Duration
          </div>
          <div className="text-xl font-semibold text-white">{(result.duration_ms / 1000).toFixed(1)}s</div>
        </div>
      </div>

      {/* Root Cause */}
      {result.root_cause_explanation && (
        <div className="p-4 bg-slate-800/50 rounded-xl border border-slate-700">
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-5 h-5 text-primary-400" />
            <h3 className="font-semibold text-white">Root Cause Analysis</h3>
          </div>
          <p className="text-slate-300 text-sm whitespace-pre-line">
            {result.root_cause_explanation}
          </p>
        </div>
      )}

      {/* Self-Healing Preview */}
      {result.self_healing_available && result.auto_fix_preview && (
        <div className="p-4 bg-purple-500/10 border border-purple-500/30 rounded-xl">
          <div className="flex items-center gap-2 mb-3">
            <Wrench className="w-5 h-5 text-purple-400" />
            <h3 className="font-semibold text-purple-300">Self-Healing Available</h3>
            <span className="px-2 py-0.5 text-xs bg-purple-500/20 text-purple-300 rounded-full">
              {Math.round(result.auto_fix_preview.confidence * 100)}% confidence
            </span>
          </div>
          <p className="text-sm text-slate-300 mb-2">{result.auto_fix_preview.description}</p>
          <p className="text-sm text-slate-400">{result.auto_fix_preview.action}</p>
        </div>
      )}

      {/* All Detections */}
      {result.all_detections.length > 0 && (
        <div>
          <h3 className="font-semibold text-white mb-3">All Detections ({result.all_detections.length})</h3>
          <div className="space-y-2">
            {result.all_detections.map((detection, index) => (
              <DetectionCard
                key={index}
                detection={detection}
                isExpanded={expandedDetections.has(index)}
                onToggle={() => toggleDetection(index)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Detectors Run */}
      <div className="text-xs text-slate-500">
        Detectors: {result.detectors_run.join(', ')}
      </div>
    </div>
  )
}
