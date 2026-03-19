'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useCallback } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { Heart, ChevronRight, Filter, Loader2, AlertTriangle } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { QualityHealingStatusBadge } from '@/components/quality/QualityHealingStatusBadge'
import { createApiClient, QualityHealingRecord } from '@/lib/api'
import Link from 'next/link'

const statusOptions = [
  { label: 'All', value: null },
  { label: 'Pending', value: 'pending', activeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/50' },
  { label: 'Success', value: 'success', activeClass: 'bg-green-500/20 text-green-400 border-green-500/50' },
  { label: 'Partial', value: 'partial_success', activeClass: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50' },
  { label: 'Failed', value: 'failed', activeClass: 'bg-red-500/20 text-red-400 border-red-500/50' },
  { label: 'Rolled Back', value: 'rolled_back', activeClass: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/50' },
]

export default function QualityHealingListPage() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [healings, setHealings] = useState<QualityHealingRecord[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string | null>(null)
  const perPage = 10

  const loadHealings = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)
      const result = await api.listQualityHealings({
        page: page,
        page_size: perPage,
        status: statusFilter || undefined,
      })
      setHealings(result.items)
      setTotal(result.total)
    } catch (err) {
      console.warn('Failed to load quality healings:', err)
      setError('Failed to load quality healing records. Please try again.')
      setHealings([])
      setTotal(0)
    }
    setIsLoading(false)
  }, [getToken, tenantId, page, perPage, statusFilter])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetching pattern
    loadHealings()
  }, [loadHealings])

  const totalPages = Math.ceil(total / perPage)

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-green-600/20 rounded-lg">
                <Heart className="w-6 h-6 text-green-400" />
              </div>
              <h1 className="text-2xl font-bold text-white">Quality Healing</h1>
            </div>
            <p className="text-zinc-400">
              Review and manage quality healing records for your workflows
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 mb-6 flex-wrap">
          <div className="flex items-center gap-2">
            <Filter size={16} className="text-zinc-400" />
            <span className="text-sm text-zinc-400">Status:</span>
          </div>
          <div className="flex gap-2">
            {statusOptions.map((opt) => (
              <button
                key={opt.label}
                onClick={() => {
                  setStatusFilter(opt.value === statusFilter ? null : opt.value)
                  setPage(1)
                }}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors border ${
                  statusFilter === opt.value
                    ? opt.activeClass || 'bg-blue-500/20 text-blue-400 border-blue-500/50'
                    : 'bg-zinc-800 text-zinc-400 border-zinc-700 hover:border-zinc-600'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertTriangle size={20} className="text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300 flex-1">{error}</p>
            <Button variant="ghost" size="sm" onClick={loadHealings}>
              Retry
            </Button>
          </div>
        )}

        {/* Healing List */}
        <div className="space-y-4">
          {isLoading ? (
            <Card>
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-green-400 animate-spin" />
              </div>
            </Card>
          ) : healings.length === 0 ? (
            <Card>
              <div className="text-center py-12">
                <Heart className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                <p className="text-zinc-400 mb-2">No quality healing records found</p>
                <p className="text-zinc-500 text-sm">
                  Quality healing records are generated when healing is triggered on assessments
                </p>
              </div>
            </Card>
          ) : (
            healings.map((healing) => (
              <Link key={healing.id} href={`/quality/healing/${healing.id}`}>
                <Card className="hover:border-zinc-600 transition-colors cursor-pointer">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <QualityHealingStatusBadge status={healing.status} size="md" />
                        <div>
                          <div className="flex items-center gap-3 mb-1">
                            <span className="text-white font-medium">
                              Score: {Math.round(healing.before_score)}%
                              {healing.after_score !== null && (
                                <>
                                  {' '}&rarr;{' '}
                                  <span
                                    className={
                                      healing.after_score > healing.before_score
                                        ? 'text-green-400'
                                        : healing.after_score < healing.before_score
                                        ? 'text-red-400'
                                        : 'text-zinc-400'
                                    }
                                  >
                                    {Math.round(healing.after_score)}%
                                  </span>
                                </>
                              )}
                            </span>
                            {healing.score_improvement !== null && healing.score_improvement > 0 && (
                              <span className="text-xs text-green-400 font-medium">
                                +{Math.round(healing.score_improvement)}%
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-sm text-zinc-400">
                            <span>{healing.dimensions_targeted.length} dimensions targeted</span>
                            <span>|</span>
                            <span>{healing.fix_suggestions_count} suggestions</span>
                            <span>|</span>
                            <span>{healing.applied_fixes.length} applied</span>
                            <span>|</span>
                            <span>
                              {new Date(healing.metadata?.created_at || healing.id).toLocaleDateString()}
                            </span>
                          </div>
                          {healing.dimensions_targeted.length > 0 && (
                            <div className="flex gap-1.5 mt-2 flex-wrap">
                              {healing.dimensions_targeted.slice(0, 4).map((dim) => (
                                <span
                                  key={dim}
                                  className="px-2 py-0.5 text-xs bg-zinc-800 text-zinc-400 rounded capitalize"
                                >
                                  {dim.replace(/_/g, ' ')}
                                </span>
                              ))}
                              {healing.dimensions_targeted.length > 4 && (
                                <span className="px-2 py-0.5 text-xs bg-zinc-800 text-zinc-500 rounded">
                                  +{healing.dimensions_targeted.length - 4} more
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                      <ChevronRight className="text-zinc-500" size={20} />
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
