'use client'

import { BarChart3, Info } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import type { QualityAssessment, QualityDimensionScore } from '@/lib/api'
import { cn } from '@/lib/utils'

interface QualityDimensionsChartProps {
  assessments?: QualityAssessment[]
  isLoading?: boolean
  type?: 'agent' | 'orchestration' | 'both'
}

interface DimensionAggregate {
  dimension: string
  avgScore: number
  issueCount: number
  totalSamples: number
}

function aggregateDimensions(
  assessments: QualityAssessment[],
  type: 'agent' | 'orchestration' | 'both'
): DimensionAggregate[] {
  const dimensionMap = new Map<string, { scores: number[]; issueCount: number }>()

  assessments.forEach(assessment => {
    let dimensions: QualityDimensionScore[] = []

    if (type === 'agent' || type === 'both') {
      // Aggregate from all agents
      assessment.agent_scores?.forEach(agent => {
        dimensions = [...dimensions, ...(agent.dimensions || [])]
      })
    }

    if (type === 'orchestration' || type === 'both') {
      // Add orchestration dimensions
      dimensions = [...dimensions, ...(assessment.orchestration_score?.dimensions || [])]
    }

    dimensions.forEach(dim => {
      if (!dimensionMap.has(dim.dimension)) {
        dimensionMap.set(dim.dimension, { scores: [], issueCount: 0 })
      }
      const entry = dimensionMap.get(dim.dimension)!
      entry.scores.push(dim.score)
      entry.issueCount += dim.issues?.length || 0
    })
  })

  return Array.from(dimensionMap.entries())
    .map(([dimension, data]) => ({
      dimension,
      avgScore: data.scores.reduce((sum, s) => sum + s, 0) / data.scores.length,
      issueCount: data.issueCount,
      totalSamples: data.scores.length,
    }))
    .sort((a, b) => b.avgScore - a.avgScore) // Sort by score descending
}

function getScoreColor(score: number): string {
  if (score >= 0.8) return 'bg-green-500'
  if (score >= 0.6) return 'bg-blue-500'
  if (score >= 0.4) return 'bg-amber-500'
  return 'bg-red-500'
}

function getScoreTextColor(score: number): string {
  if (score >= 0.8) return 'text-green-400'
  if (score >= 0.6) return 'text-blue-400'
  if (score >= 0.4) return 'text-amber-400'
  return 'text-red-400'
}

export function QualityDimensionsChart({
  assessments = [],
  isLoading,
  type = 'both',
}: QualityDimensionsChartProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-96 animate-pulse bg-blue-500/20 rounded-lg" />
      </Card>
    )
  }

  const dimensions = aggregateDimensions(assessments, type)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-400" />
            Quality Dimensions
            {type !== 'both' && (
              <span className="text-xs text-zinc-400 font-normal capitalize">({type})</span>
            )}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {dimensions.length === 0 ? (
          <div className="text-center py-8">
            <Info size={32} className="mx-auto mb-2 opacity-50 text-zinc-500" />
            <p className="text-zinc-400 text-sm">No quality dimension data available</p>
          </div>
        ) : (
          <div className="space-y-3">
            {dimensions.map((dim) => (
              <div key={dim.dimension} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-300 capitalize">{dim.dimension}</span>
                    {dim.issueCount > 0 && (
                      <span className="text-xs text-amber-400">
                        ({dim.issueCount} issue{dim.issueCount !== 1 ? 's' : ''})
                      </span>
                    )}
                  </div>
                  <span className={cn('font-semibold', getScoreTextColor(dim.avgScore))}>
                    {(dim.avgScore * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-zinc-700 rounded-full h-2 overflow-hidden">
                    <div
                      className={cn(
                        'h-2 rounded-full transition-all',
                        getScoreColor(dim.avgScore)
                      )}
                      style={{ width: `${dim.avgScore * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-zinc-500 w-16 text-right">
                    {dim.totalSamples} sample{dim.totalSamples !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>
            ))}

            {/* Legend */}
            <div className="pt-3 border-t border-zinc-700">
              <div className="text-xs text-zinc-400 mb-2">Score Ranges</div>
              <div className="flex flex-wrap gap-3 text-xs">
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 bg-green-500 rounded" />
                  <span className="text-zinc-400">80-100% Excellent</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 bg-blue-500 rounded" />
                  <span className="text-zinc-400">60-79% Good</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 bg-amber-500 rounded" />
                  <span className="text-zinc-400">40-59% Needs Work</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-3 h-3 bg-red-500 rounded" />
                  <span className="text-zinc-400">&lt;40% Critical</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
