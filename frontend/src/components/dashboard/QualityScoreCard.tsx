'use client'

import { Star, AlertTriangle, ChevronRight, TrendingUp, TrendingDown } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card'
import { QualityGradeBadge, getScoreColor } from '../quality/QualityGradeBadge'
import Link from 'next/link'
import type { QualityAssessment } from '@/lib/api'

interface QualityScoreCardProps {
  assessments?: QualityAssessment[]
  isLoading?: boolean
}

function calculateAverageScore(assessments: QualityAssessment[]): number {
  if (assessments.length === 0) return 0
  const sum = assessments.reduce((acc, a) => acc + a.overall_score, 0)
  return sum / assessments.length
}

function getAverageGrade(score: number): string {
  if (score >= 0.9) return 'Healthy'
  if (score >= 0.8) return 'Good'
  if (score >= 0.7) return 'Needs Attention'
  if (score >= 0.5) return 'At Risk'
  return 'Critical'
}

export function QualityScoreCard({ assessments = [], isLoading }: QualityScoreCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="h-40 animate-pulse bg-blue-500/20 rounded-lg" />
      </Card>
    )
  }

  const totalAssessments = assessments.length
  const avgScore = calculateAverageScore(assessments)
  const avgGrade = getAverageGrade(avgScore)

  const criticalIssues = assessments.reduce((acc, a) => acc + a.critical_issues_count, 0)
  const totalIssues = assessments.reduce((acc, a) => acc + a.total_issues, 0)

  // Calculate scores for different grades (overall_score is 0-100 integer)
  const excellentCount = assessments.filter(a => a.overall_score >= 0.80).length
  const needsWorkCount = assessments.filter(a => a.overall_score < 0.60).length

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Star className="h-5 w-5 text-amber-400" />
            Quality Score
          </CardTitle>
          <Link
            href="/quality"
            className="flex items-center gap-1 text-sm text-blue-500 hover:text-blue-400"
          >
            View details
            <ChevronRight size={16} />
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {totalAssessments === 0 ? (
          <div className="text-center py-4">
            <div className="text-blue-400 text-sm mb-2">No quality assessments yet</div>
            <Link
              href="/n8n"
              className="text-sm text-blue-500 hover:text-blue-400"
            >
              Register a workflow to get started
            </Link>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-4 mb-4">
              <QualityGradeBadge grade={avgGrade} size="lg" />
              <div>
                <div className={`text-3xl font-bold ${getScoreColor(avgScore)}`}>
                  {Math.round(avgScore * 100)}%
                </div>
                <div className="text-sm text-white/60">
                  Average across {totalAssessments} workflow{totalAssessments !== 1 ? 's' : ''}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="bg-green-500/20 border border-green-500/30 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp size={14} className="text-green-500" />
                  <span className="text-xs text-white/60">Excellent</span>
                </div>
                <div className="text-lg font-semibold text-green-500 font-mono">
                  {excellentCount}
                </div>
              </div>
              <div className="bg-violet-500/20 border border-violet-500/30 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingDown size={14} className="text-violet-500" />
                  <span className="text-xs text-white/60">Needs Work</span>
                </div>
                <div className="text-lg font-semibold text-violet-500 font-mono">
                  {needsWorkCount}
                </div>
              </div>
            </div>

            {criticalIssues > 0 && (
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                <div className="flex items-center gap-2 text-sm text-red-400">
                  <AlertTriangle size={14} />
                  <span className="font-medium">{criticalIssues} critical issue{criticalIssues !== 1 ? 's' : ''}</span>
                  <span className="text-red-400/70">need attention</span>
                </div>
              </div>
            )}

            {criticalIssues === 0 && totalIssues > 0 && (
              <div className="text-sm text-white/60">
                {totalIssues} improvement suggestion{totalIssues !== 1 ? 's' : ''} available
              </div>
            )}

            {totalIssues === 0 && (
              <div className="text-sm text-green-500">
                All workflows are well configured!
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
