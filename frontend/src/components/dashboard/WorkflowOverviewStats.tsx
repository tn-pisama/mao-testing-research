'use client'

import { Workflow, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react'
import type { QualityAssessment } from '@/lib/api'
import { cn } from '@/lib/utils'

interface WorkflowOverviewStatsProps {
  workflows: QualityAssessment[]
  isLoading?: boolean
}

interface HealthDistribution {
  excellent: number // A
  good: number // B+, B
  needsWork: number // C+, C
  critical: number // D, F
}

function calculateHealthDistribution(workflows: QualityAssessment[]): HealthDistribution {
  return workflows.reduce(
    (acc, w) => {
      const grade = w.overall_grade
      if (grade === 'A') acc.excellent++
      else if (grade === 'B+' || grade === 'B') acc.good++
      else if (grade === 'C+' || grade === 'C') acc.needsWork++
      else acc.critical++
      return acc
    },
    { excellent: 0, good: 0, needsWork: 0, critical: 0 }
  )
}

function calculateAverageQuality(workflows: QualityAssessment[]): number {
  if (workflows.length === 0) return 0
  const sum = workflows.reduce((acc, w) => acc + w.overall_score, 0)
  return sum / workflows.length
}

function countCriticalIssues(workflows: QualityAssessment[]): number {
  return workflows.reduce((acc, w) => acc + w.critical_issues_count, 0)
}

export function WorkflowOverviewStats({ workflows, isLoading }: WorkflowOverviewStatsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="h-20 bg-zinc-700/50 rounded-lg animate-pulse" />
        ))}
      </div>
    )
  }

  const health = calculateHealthDistribution(workflows)
  const avgQuality = calculateAverageQuality(workflows) / 100 // Normalize 0-100 integer to 0-1 for display
  const criticalIssues = countCriticalIssues(workflows)

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
      {/* Total Workflows */}
      <StatCard
        icon={<Workflow size={18} />}
        label="Total Workflows"
        value={workflows.length}
        color="slate"
      />

      {/* Excellent */}
      <StatCard
        icon={<CheckCircle size={18} />}
        label="Excellent"
        value={health.excellent}
        color="green"
        subtitle="Grade A"
      />

      {/* Good */}
      <StatCard
        icon={<TrendingUp size={18} />}
        label="Good"
        value={health.good}
        color="blue"
        subtitle="Grade B"
      />

      {/* Needs Work */}
      <StatCard
        icon={<AlertTriangle size={18} />}
        label="Needs Work"
        value={health.needsWork}
        color="amber"
        subtitle="Grade C"
      />

      {/* Critical */}
      <StatCard
        icon={<AlertTriangle size={18} />}
        label="Critical"
        value={health.critical}
        color="red"
        subtitle="Grade D/F"
      />

      {/* Average Quality */}
      <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
        <div className="flex items-center gap-2 mb-1">
          <div className="text-xs text-zinc-400">Avg Quality</div>
        </div>
        <div className={cn(
          'text-2xl font-bold',
          avgQuality >= 0.8 ? 'text-green-400' :
          avgQuality >= 0.6 ? 'text-blue-400' :
          avgQuality >= 0.4 ? 'text-amber-400' :
          'text-red-400'
        )}>
          {(avgQuality * 100).toFixed(0)}%
        </div>
        {criticalIssues > 0 && (
          <div className="text-xs text-red-400 mt-1">
            {criticalIssues} critical issue{criticalIssues !== 1 ? 's' : ''}
          </div>
        )}
      </div>
    </div>
  )
}

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: number
  color: 'slate' | 'green' | 'blue' | 'amber' | 'red'
  subtitle?: string
}

function StatCard({ icon, label, value, color, subtitle }: StatCardProps) {
  const colorClasses = {
    slate: 'bg-zinc-700/50 text-zinc-300',
    green: 'bg-green-500/20 text-green-400 border-green-500/30',
    blue: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    amber: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    red: 'bg-red-500/20 text-red-400 border-red-500/30',
  }

  return (
    <div className={cn(
      'rounded-lg p-3 border',
      color === 'slate' ? 'bg-zinc-800 border-zinc-700' : colorClasses[color]
    )}>
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <div className="text-xs text-zinc-400">{label}</div>
      </div>
      <div className="text-2xl font-bold">{value}</div>
      {subtitle && (
        <div className="text-xs text-zinc-300 mt-0.5">{subtitle}</div>
      )}
    </div>
  )
}
