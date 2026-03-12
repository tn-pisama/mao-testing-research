'use client'

import { Network, Info } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import type { QualityAssessment, ComplexityMetrics } from '@/lib/api'
import { cn } from '@/lib/utils'

interface ComplexityMetricsCardProps {
  assessments?: QualityAssessment[]
  isLoading?: boolean
}

function getComplexityColor(value: number, type: 'cyclomatic' | 'coupling' | 'depth'): string {
  if (type === 'cyclomatic') {
    // Cyclomatic complexity: <10 good, 10-20 moderate, >20 high
    if (value <= 10) return 'text-green-400'
    if (value <= 20) return 'text-amber-400'
    return 'text-red-400'
  }
  if (type === 'coupling') {
    // Coupling ratio: <0.3 good, 0.3-0.6 moderate, >0.6 high
    if (value < 0.3) return 'text-green-400'
    if (value < 0.6) return 'text-amber-400'
    return 'text-red-400'
  }
  if (type === 'depth') {
    // Max depth: <5 good, 5-10 moderate, >10 deep
    if (value < 5) return 'text-green-400'
    if (value <= 10) return 'text-amber-400'
    return 'text-red-400'
  }
  return 'text-zinc-400'
}

function getHealthIndicator(value: number, type: 'cyclomatic' | 'coupling' | 'depth'): React.ReactNode {
  const color = getComplexityColor(value, type)
  const isHealthy = color === 'text-green-400'
  const isModerate = color === 'text-amber-400'

  return (
    <span className={cn('text-xs font-medium', color)}>
      {isHealthy ? '✓ Good' : isModerate ? '⚠ Moderate' : '✗ High'}
    </span>
  )
}

function calculateAverageMetrics(assessments: QualityAssessment[]): ComplexityMetrics | null {
  const metricsArray = assessments
    .map(a => a.orchestration_score?.complexity_metrics)
    .filter(m => m != null) as ComplexityMetrics[]

  if (metricsArray.length === 0) return null

  return {
    node_count: Math.round(metricsArray.reduce((sum, m) => sum + m.node_count, 0) / metricsArray.length),
    agent_count: Math.round(metricsArray.reduce((sum, m) => sum + m.agent_count, 0) / metricsArray.length),
    connection_count: Math.round(metricsArray.reduce((sum, m) => sum + m.connection_count, 0) / metricsArray.length),
    max_depth: Math.round(metricsArray.reduce((sum, m) => sum + m.max_depth, 0) / metricsArray.length),
    cyclomatic_complexity: Math.round(metricsArray.reduce((sum, m) => sum + m.cyclomatic_complexity, 0) / metricsArray.length),
    coupling_ratio: metricsArray.reduce((sum, m) => sum + m.coupling_ratio, 0) / metricsArray.length,
    ai_node_ratio: metricsArray.reduce((sum, m) => sum + m.ai_node_ratio, 0) / metricsArray.length,
    parallel_branches: Math.round(metricsArray.reduce((sum, m) => sum + m.parallel_branches, 0) / metricsArray.length),
    conditional_branches: Math.round(metricsArray.reduce((sum, m) => sum + m.conditional_branches, 0) / metricsArray.length),
  }
}

function getDetectedPatterns(assessments: QualityAssessment[]): string[] {
  return assessments
    .map(a => a.orchestration_score?.detected_pattern)
    .filter((p): p is string => p != null && p !== '')
    .slice(0, 3) // Show up to 3 unique patterns
}

export function ComplexityMetricsCard({ assessments = [], isLoading }: ComplexityMetricsCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-64 animate-pulse bg-purple-500/20 rounded-lg" />
      </Card>
    )
  }

  const avgMetrics = calculateAverageMetrics(assessments)
  const patterns = getDetectedPatterns(assessments)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Network className="h-5 w-5 text-purple-400" />
            Workflow Complexity
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {!avgMetrics ? (
          <div className="text-center py-8">
            <Info size={32} className="mx-auto mb-2 opacity-50 text-zinc-500" />
            <p className="text-zinc-400 text-sm">No complexity data available</p>
          </div>
        ) : (
          <>
            {/* Key Metrics Grid */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="bg-zinc-700/50 rounded-lg p-3">
                <div className="text-xs text-zinc-400 mb-1">Agents</div>
                <div className="text-2xl font-bold text-white">{avgMetrics.agent_count}</div>
              </div>
              <div className="bg-zinc-700/50 rounded-lg p-3">
                <div className="text-xs text-zinc-400 mb-1">Nodes</div>
                <div className="text-2xl font-bold text-white">{avgMetrics.node_count}</div>
              </div>
              <div className="bg-zinc-700/50 rounded-lg p-3">
                <div className="text-xs text-zinc-400 mb-1">Connections</div>
                <div className="text-2xl font-bold text-white">{avgMetrics.connection_count}</div>
              </div>
              <div className="bg-zinc-700/50 rounded-lg p-3">
                <div className="text-xs text-zinc-400 mb-1">Branches</div>
                <div className="text-2xl font-bold text-white">
                  {avgMetrics.parallel_branches + avgMetrics.conditional_branches}
                </div>
              </div>
            </div>

            {/* Complexity Indicators */}
            <div className="space-y-2 mb-4">
              <div className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-300">Cyclomatic Complexity</span>
                  <button
                    className="text-zinc-500 hover:text-zinc-400"
                    title="Measures decision points in the workflow. Lower is simpler."
                    aria-label="Cyclomatic complexity info"
                  >
                    <Info size={14} />
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <span className={cn('text-lg font-bold', getComplexityColor(avgMetrics.cyclomatic_complexity, 'cyclomatic'))}>
                    {avgMetrics.cyclomatic_complexity}
                  </span>
                  {getHealthIndicator(avgMetrics.cyclomatic_complexity, 'cyclomatic')}
                </div>
              </div>

              <div className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-300">Coupling Ratio</span>
                  <button
                    className="text-zinc-500 hover:text-zinc-400"
                    title="Measures dependencies between components. Lower is better."
                    aria-label="Coupling ratio info"
                  >
                    <Info size={14} />
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <span className={cn('text-lg font-bold', getComplexityColor(avgMetrics.coupling_ratio, 'coupling'))}>
                    {avgMetrics.coupling_ratio.toFixed(2)}
                  </span>
                  {getHealthIndicator(avgMetrics.coupling_ratio, 'coupling')}
                </div>
              </div>

              <div className="flex items-center justify-between p-2 bg-zinc-800/50 rounded">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-300">Max Depth</span>
                  <button
                    className="text-zinc-500 hover:text-zinc-400"
                    title="Maximum nesting level. Shallower workflows are easier to understand."
                    aria-label="Max depth info"
                  >
                    <Info size={14} />
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <span className={cn('text-lg font-bold', getComplexityColor(avgMetrics.max_depth, 'depth'))}>
                    {avgMetrics.max_depth}
                  </span>
                  {getHealthIndicator(avgMetrics.max_depth, 'depth')}
                </div>
              </div>
            </div>

            {/* Detected Patterns */}
            {patterns.length > 0 && (
              <div className="pt-3 border-t border-zinc-700">
                <div className="text-xs text-zinc-400 mb-2">Detected Patterns</div>
                <div className="flex flex-wrap gap-2">
                  {patterns.map((pattern, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-1 text-xs bg-purple-500/20 text-purple-300 rounded border border-purple-500/30"
                    >
                      {pattern}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
