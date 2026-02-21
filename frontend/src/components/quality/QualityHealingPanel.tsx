'use client'

import { useState } from 'react'
import { ChevronDown, Wrench, Zap, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { QualityHealingStatusBadge } from './QualityHealingStatusBadge'
import { QualityBeforeAfterChart } from './QualityBeforeAfterChart'
import type { HealingRecord, FixSuggestionSummary } from '@/lib/api'

export interface QualityHealingPanelProps {
  healingRecord: HealingRecord | null
  fixSuggestions: FixSuggestionSummary[]
  isApplying?: boolean
  onApplyFix?: (fixId: string) => void
  onApplyAll?: () => void
  onRollback?: () => void
  beforeScores?: Record<string, number>
  afterScores?: Record<string, number>
}

const confidenceColors: Record<string, string> = {
  high: 'text-green-400',
  medium: 'text-amber-400',
  low: 'text-red-400',
}

const effortLabels: Record<string, { label: string; color: string }> = {
  low: { label: 'Low effort', color: 'text-green-400' },
  medium: { label: 'Medium effort', color: 'text-amber-400' },
  high: { label: 'High effort', color: 'text-red-400' },
}

interface GroupedFixes {
  [dimension: string]: FixSuggestionSummary[]
}

function groupByDimension(fixes: FixSuggestionSummary[]): GroupedFixes {
  const grouped: GroupedFixes = {}
  for (const fix of fixes) {
    const dimension = fix.fix_type || 'general'
    if (!grouped[dimension]) {
      grouped[dimension] = []
    }
    grouped[dimension].push(fix)
  }
  return grouped
}

function DimensionGroup({
  dimension,
  fixes,
  isApplying,
  onApplyFix,
}: {
  dimension: string
  fixes: FixSuggestionSummary[]
  isApplying?: boolean
  onApplyFix?: (fixId: string) => void
}) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="mb-4">
      <button
        className="flex items-center gap-2 w-full text-left mb-2"
        onClick={() => setExpanded(!expanded)}
      >
        <ChevronDown
          size={16}
          className={`text-slate-400 transition-transform ${expanded ? '' : '-rotate-90'}`}
        />
        <span className="text-sm font-medium text-slate-300 capitalize">
          {dimension.replace(/_/g, ' ')}
        </span>
        <Badge variant="default">{fixes.length}</Badge>
      </button>

      {expanded && (
        <div className="ml-6 space-y-3">
          {fixes.map((fix) => (
            <FixCard
              key={fix.id}
              fix={fix}
              isApplying={isApplying}
              onApply={onApplyFix}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function FixCard({
  fix,
  isApplying,
  onApply,
}: {
  fix: FixSuggestionSummary
  isApplying?: boolean
  onApply?: (fixId: string) => void
}) {
  const [showDetails, setShowDetails] = useState(false)
  const effort = effortLabels[fix.confidence] || effortLabels.medium

  return (
    <Card>
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div className="p-1.5 bg-blue-500/20 rounded-lg flex-shrink-0 mt-0.5">
              <Wrench size={14} className="text-blue-400" />
            </div>
            <div className="flex-1 min-w-0">
              <h4 className="text-sm text-white font-medium mb-1">{fix.title}</h4>
              <p className="text-xs text-slate-400 mb-2">{fix.description}</p>
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`text-xs ${confidenceColors[fix.confidence] || 'text-slate-400'}`}>
                  {fix.confidence} confidence
                </span>
                <span className={`text-xs flex items-center gap-1 ${effort.color}`}>
                  <Clock size={10} />
                  {effort.label}
                </span>
                <span className="text-xs text-slate-500">{fix.fix_type}</span>
              </div>
            </div>
          </div>

          {onApply && (
            <Button
              variant="primary"
              size="sm"
              disabled={isApplying}
              isLoading={isApplying}
              onClick={() => onApply(fix.id)}
            >
              Apply
            </Button>
          )}
        </div>

        {fix.code_changes && fix.code_changes.length > 0 && (
          <>
            <button
              className="text-xs text-blue-400 hover:text-blue-300 mt-2"
              onClick={() => setShowDetails(!showDetails)}
            >
              {showDetails ? 'Hide' : 'Show'} code changes ({fix.code_changes.length})
            </button>
            {showDetails && (
              <div className="mt-2 space-y-2">
                {fix.code_changes.map((change, i) => (
                  <div key={i} className="bg-slate-900 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs text-slate-500">{change.file_path}</span>
                      <span className="text-xs text-slate-600">({change.language})</span>
                    </div>
                    <p className="text-xs text-slate-400 mb-2">{change.description}</p>
                    {change.diff && (
                      <pre className="text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap">
                        {change.diff}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

export function QualityHealingPanel({
  healingRecord,
  fixSuggestions,
  isApplying,
  onApplyFix,
  onApplyAll,
  onRollback,
  beforeScores,
  afterScores,
}: QualityHealingPanelProps) {
  const grouped = groupByDimension(fixSuggestions)
  const dimensionKeys = Object.keys(grouped)

  // Build dimension comparison data for chart
  const chartDimensions =
    beforeScores && afterScores
      ? Object.keys(beforeScores).map((dim) => ({
          dimension: dim,
          before: beforeScores[dim] || 0,
          after: afterScores[dim] || 0,
        }))
      : []

  return (
    <div className="space-y-6">
      {/* Healing status header */}
      {healingRecord && (
        <div className="flex items-center justify-between p-4 bg-slate-800 rounded-lg">
          <div className="flex items-center gap-4">
            <QualityHealingStatusBadge status={healingRecord.status} />
            <div>
              <p className="text-sm text-slate-300">
                Healing record <span className="text-white font-mono text-xs">{healingRecord.id.slice(0, 8)}</span>
              </p>
              <p className="text-xs text-slate-500">
                Created {new Date(healingRecord.created_at).toLocaleString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {healingRecord.rollback_available && onRollback && (
              <Button variant="danger" size="sm" onClick={onRollback}>
                Rollback
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Validation results */}
      {healingRecord && healingRecord.validation_status && (
        <div
          className={`p-4 rounded-lg border ${
            healingRecord.validation_status === 'passed'
              ? 'bg-green-500/10 border-green-500/30'
              : healingRecord.validation_status === 'failed'
              ? 'bg-red-500/10 border-red-500/30'
              : 'bg-amber-500/10 border-amber-500/30'
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            {healingRecord.validation_status === 'passed' ? (
              <CheckCircle size={16} className="text-green-400" />
            ) : (
              <AlertCircle size={16} className="text-red-400" />
            )}
            <span className="text-sm font-medium text-white capitalize">
              Validation {healingRecord.validation_status}
            </span>
          </div>
          {healingRecord.validation_results && Object.keys(healingRecord.validation_results).length > 0 && (
            <div className="text-xs text-slate-400 space-y-1">
              {Object.entries(healingRecord.validation_results).map(([key, val]) => (
                <div key={key}>
                  <span className="text-slate-500">{key.replace(/_/g, ' ')}:</span>{' '}
                  {String(val)}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Before/After chart */}
      {chartDimensions.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-slate-300 mb-3">Score Comparison</h3>
          <QualityBeforeAfterChart dimensions={chartDimensions} />
        </div>
      )}

      {/* Fix suggestions grouped by dimension */}
      {fixSuggestions.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-slate-300 flex items-center gap-2">
              <Zap size={16} className="text-amber-400" />
              Fix Suggestions ({fixSuggestions.length})
            </h3>
            {onApplyAll && fixSuggestions.length > 1 && (
              <Button
                variant="success"
                size="sm"
                disabled={isApplying}
                isLoading={isApplying}
                onClick={onApplyAll}
              >
                Apply All
              </Button>
            )}
          </div>

          {dimensionKeys.map((dimension) => (
            <DimensionGroup
              key={dimension}
              dimension={dimension}
              fixes={grouped[dimension]}
              isApplying={isApplying}
              onApplyFix={onApplyFix}
            />
          ))}
        </div>
      )}

      {fixSuggestions.length === 0 && !healingRecord && (
        <div className="text-center py-8">
          <Wrench className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">No fix suggestions available</p>
          <p className="text-slate-500 text-xs mt-1">
            Trigger a healing analysis to generate fix suggestions
          </p>
        </div>
      )}
    </div>
  )
}
