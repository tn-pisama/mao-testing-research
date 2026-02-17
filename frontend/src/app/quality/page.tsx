'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { Star, ChevronRight, Filter, Loader2, AlertTriangle } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { QualityGradeBadge, getScoreColor } from '@/components/quality/QualityGradeBadge'
import { createApiClient, QualityAssessment } from '@/lib/api'
import { useUIStore } from '@/stores/uiStore'
import Link from 'next/link'

export default function QualityPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const { filterPreferences } = useUIStore()
  const [assessments, setAssessments] = useState<QualityAssessment[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [gradeFilter, setGradeFilter] = useState<string | null>(null)
  const perPage = 10

  const loadAssessments = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const result = await api.listQualityAssessments({
        page,
        pageSize: perPage,
        minGrade: gradeFilter || undefined,
        groupId: filterPreferences.workflowGroupId && filterPreferences.workflowGroupId !== 'all'
          ? filterPreferences.workflowGroupId
          : undefined,
      })
      setAssessments(result.assessments)
      setTotal(result.total)
    } catch (err) {
      console.warn('Failed to load quality assessments:', err)
      setError('Failed to load quality assessments. Please try again.')
      setAssessments([])
      setTotal(0)
    }
    setIsLoading(false)
  }, [getToken, tenantId, page, perPage, gradeFilter, filterPreferences.workflowGroupId])

  useEffect(() => {
    loadAssessments()
  }, [loadAssessments])

  const totalPages = Math.ceil(total / perPage)

  const gradeOptions = ['A', 'B+', 'B', 'C+', 'C', 'D', 'F']

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-amber-600/20 rounded-lg">
                <Star className="w-6 h-6 text-amber-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Quality Assessments</h1>
            </div>
            <p className="text-slate-400">
              Review quality scores and improvement suggestions for your workflows
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-6 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-slate-400" />
            <span className="text-sm text-slate-400">Grade:</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setGradeFilter(null)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                gradeFilter === null
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                  : 'bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600'
              }`}
            >
              All
            </button>
            {gradeOptions.map((grade) => (
              <button
                key={grade}
                onClick={() => setGradeFilter(grade === gradeFilter ? null : grade)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  gradeFilter === grade
                    ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                    : 'bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600'
                }`}
              >
                {grade}
              </button>
            ))}
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertTriangle size={20} className="text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300 flex-1">{error}</p>
            <Button variant="ghost" size="sm" onClick={loadAssessments}>
              Retry
            </Button>
          </div>
        )}

        {/* Assessment List */}
        <div className="space-y-4">
          {isLoading ? (
            <Card>
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
              </div>
            </Card>
          ) : assessments.length === 0 ? (
            <Card>
              <div className="text-center py-12">
                <Star className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <p className="text-slate-400 mb-2">No quality assessments found</p>
                <p className="text-slate-500 text-sm">
                  Quality assessments are generated when workflows are analyzed
                </p>
              </div>
            </Card>
          ) : (
            assessments.map((assessment) => (
              <Link key={assessment.id} href={`/quality/${assessment.id}`}>
                <Card className="hover:border-slate-600 transition-colors cursor-pointer">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <QualityGradeBadge grade={assessment.overall_grade} size="lg" />
                        <div>
                          <h3 className="text-white font-medium mb-1">
                            {assessment.workflow_name}
                          </h3>
                          <div className="flex items-center gap-3 text-sm text-slate-400">
                            <span className={getScoreColor(assessment.overall_score / 100)}>
                              {Math.round(assessment.overall_score)}% overall
                            </span>
                            <span>|</span>
                            <span>{assessment.agent_scores.length} agents</span>
                            <span>|</span>
                            <span>{new Date(assessment.assessed_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-4">
                        {assessment.critical_issues_count > 0 && (
                          <div className="flex items-center gap-2 text-red-400">
                            <AlertTriangle size={16} />
                            <span className="text-sm font-medium">
                              {assessment.critical_issues_count} critical
                            </span>
                          </div>
                        )}
                        {assessment.total_issues > 0 && assessment.critical_issues_count === 0 && (
                          <Badge variant="warning">
                            {assessment.total_issues} suggestions
                          </Badge>
                        )}
                        <ChevronRight className="text-slate-500" size={20} />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-6">
            <p className="text-sm text-slate-400">
              Showing {(page - 1) * perPage + 1} - {Math.min(page * perPage, total)} of {total}
            </p>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

    </Layout>
  )
}
