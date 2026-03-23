'use client'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { Star, ChevronRight, Filter, Loader2, AlertTriangle } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { QualityGradeBadge, getScoreColor } from '@/components/quality/QualityGradeBadge'
import { createApiClient, QualityAssessment } from '@/lib/api'
import { useUIStore } from '@/stores/uiStore'
import Link from 'next/link'

interface QualityClientProps {
  initialAssessments: QualityAssessment[]
  initialTotal: number
}

export function QualityClient({ initialAssessments, initialTotal }: QualityClientProps) {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const { filterPreferences } = useUIStore()
  const [assessments, setAssessments] = useState<QualityAssessment[]>(initialAssessments)
  const [isLoading, setIsLoading] = useState(initialAssessments.length === 0 && initialTotal === 0 ? false : false)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(initialTotal)
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
    }
    setIsLoading(false)
  }, [getToken, tenantId, page, perPage, gradeFilter, filterPreferences.workflowGroupId])

  // Only fetch on filter/page changes (initial data comes from SSR)
  useEffect(() => {
    if (page > 1 || gradeFilter) {
      loadAssessments()
    }
  }, [page, gradeFilter, loadAssessments])

  const totalPages = Math.ceil(total / perPage)

  const tierOptions = [
    { label: 'Healthy',  minGrade: 'Healthy',  activeClass: 'bg-green-500/20 text-green-500 border-green-500/50' },
    { label: 'Degraded', minGrade: 'Degraded', activeClass: 'bg-violet-500/20 text-violet-500 border-violet-500/50' },
    { label: 'At Risk',  minGrade: 'At Risk',  activeClass: 'bg-orange-500/20 text-orange-400 border-orange-500/50' },
    { label: 'Critical', minGrade: 'Critical', activeClass: 'bg-red-500/20 text-red-500 border-red-500/50' },
  ]

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-amber-600/20 rounded-lg">
                <Star className="w-6 h-6 text-amber-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Workflows</h1>
            </div>
            <p className="text-zinc-400">
              Quality scores and improvement suggestions for your workflows
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-6 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-zinc-400" />
            <span className="text-sm text-zinc-400">Health:</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setGradeFilter(null)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                gradeFilter === null
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                  : 'bg-zinc-800 text-zinc-400 border border-zinc-700 hover:border-zinc-600'
              }`}
            >
              All
            </button>
            {tierOptions.map((tier) => (
              <button
                key={tier.label}
                onClick={() => setGradeFilter(tier.minGrade === gradeFilter ? null : tier.minGrade)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors border ${
                  gradeFilter === tier.minGrade
                    ? tier.activeClass
                    : 'bg-zinc-800 text-zinc-400 border-zinc-700 hover:border-zinc-600'
                }`}
              >
                {tier.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertTriangle size={20} className="text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300 flex-1">{error}</p>
            <Button variant="ghost" size="sm" onClick={loadAssessments}>
              Retry
            </Button>
          </div>
        )}

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
                <Star className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                <p className="text-zinc-400 mb-2">No quality assessments found</p>
                <p className="text-zinc-500 text-sm">
                  Quality assessments are generated when workflows are analyzed
                </p>
              </div>
            </Card>
          ) : (
            assessments.map((assessment) => (
              <Link key={assessment.id} href={`/quality/${assessment.id}`}>
                <Card className="hover:border-zinc-600 transition-colors cursor-pointer">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <QualityGradeBadge grade={assessment.overall_grade} size="lg" />
                        <div>
                          <h3 className="text-white font-medium mb-1">
                            {assessment.workflow_name}
                          </h3>
                          <div className="flex items-center gap-3 text-sm text-zinc-400">
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
                        <ChevronRight className="text-zinc-500" size={20} />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))
          )}
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-6">
            <p className="text-sm text-zinc-400">
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
