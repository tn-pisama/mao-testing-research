'use client'

interface DimensionComparison {
  dimension: string
  before: number
  after: number
}

export interface QualityBeforeAfterChartProps {
  dimensions: DimensionComparison[]
  beforeLabel?: string
  afterLabel?: string
}

function getImprovementColor(before: number, after: number): string {
  const diff = after - before
  if (diff > 0.1) return 'bg-green-500'
  if (diff > 0) return 'bg-green-400'
  if (diff === 0) return 'bg-slate-400'
  if (diff > -0.1) return 'bg-amber-400'
  return 'bg-red-400'
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function QualityBeforeAfterChart({
  dimensions,
  beforeLabel = 'Before',
  afterLabel = 'After',
}: QualityBeforeAfterChartProps) {
  if (dimensions.length === 0) {
    return (
      <div className="text-center py-8 text-slate-500 text-sm">
        No dimension data available
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex items-center gap-6 text-xs text-slate-400 mb-2">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-slate-600" />
          <span>{beforeLabel}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-green-500" />
          <span>{afterLabel}</span>
        </div>
      </div>

      {/* Dimension bars */}
      {dimensions.map((dim) => {
        const beforePercent = Math.round(dim.before * 100)
        const afterPercent = Math.round(dim.after * 100)
        const improvement = afterPercent - beforePercent

        return (
          <div key={dim.dimension} className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-300 capitalize">
                {dim.dimension.replace(/_/g, ' ')}
              </span>
              <span className="text-xs text-slate-400">
                {formatPercent(dim.before)} → {formatPercent(dim.after)}
                {improvement !== 0 && (
                  <span
                    className={`ml-2 ${
                      improvement > 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {improvement > 0 ? '+' : ''}{improvement}%
                  </span>
                )}
              </span>
            </div>
            {/* Before bar */}
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-slate-600 transition-all duration-500 rounded-full"
                style={{ width: `${beforePercent}%` }}
              />
            </div>
            {/* After bar */}
            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-500 rounded-full ${getImprovementColor(
                  dim.before,
                  dim.after
                )}`}
                style={{ width: `${afterPercent}%` }}
              />
            </div>
          </div>
        )
      })}

      {/* Overall summary */}
      {dimensions.length > 0 && (() => {
        const avgBefore = dimensions.reduce((sum, d) => sum + d.before, 0) / dimensions.length
        const avgAfter = dimensions.reduce((sum, d) => sum + d.after, 0) / dimensions.length
        const avgImprovement = Math.round((avgAfter - avgBefore) * 100)

        return (
          <div className="mt-4 pt-4 border-t border-slate-700 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-300">Overall Average</span>
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-400">
                {formatPercent(avgBefore)} → {formatPercent(avgAfter)}
              </span>
              {avgImprovement !== 0 && (
                <span
                  className={`text-sm font-medium ${
                    avgImprovement > 0 ? 'text-green-400' : 'text-red-400'
                  }`}
                >
                  {avgImprovement > 0 ? '+' : ''}{avgImprovement}%
                </span>
              )}
            </div>
          </div>
        )
      })()}
    </div>
  )
}
