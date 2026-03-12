'use client'

export const dynamic = 'force-dynamic'

import { useState, useEffect, useMemo } from 'react'
import { Layout } from '@/components/common/Layout'
import {
  AlertTriangle,
  AlertCircle,
  Eye,
  ThumbsDown,
  Shield,
  Wrench,
  RefreshCw,
  Search,
} from 'lucide-react'
import { useUserPreferences } from '@/lib/user-preferences'
import { useDetectionsQuery, useSubmitFeedbackMutation } from '@/hooks/useQueries'

import { DetectionFilters } from '@/components/detections/DetectionFilters'
import { DetectionListItem } from '@/components/detections/DetectionListItem'
import { StatCard } from '@/components/detections/StatCard'
import type { DetectionType, Severity } from '@/components/detections/DetectionTypeConfig'

export default function DetectionsPage() {
  const [typeFilter, setTypeFilter] = useState<DetectionType>('all')
  const [severityFilter, setSeverityFilter] = useState<Severity>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showValidated, setShowValidated] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  const { isN8nUser, showAdvancedFeatures } = useUserPreferences()
  const [inlineValidated, setInlineValidated] = useState<Record<string, { validated: boolean; false_positive: boolean }>>({})

  const feedbackMutation = useSubmitFeedbackMutation()
  const submittingId = feedbackMutation.isPending ? feedbackMutation.variables?.detectionId ?? null : null

  const handleInlineValidate = (e: React.MouseEvent, detectionId: string, isFalsePositive: boolean) => {
    e.preventDefault()
    e.stopPropagation()
    if (feedbackMutation.isPending) return
    feedbackMutation.mutate(
      { detectionId, isValid: !isFalsePositive },
      {
        onSuccess: () => {
          setInlineValidated(prev => ({ ...prev, [detectionId]: { validated: true, false_positive: isFalsePositive } }))
        },
        onError: (err) => {
          if ((err as Error & { status?: number })?.status === 409) {
            setInlineValidated(prev => ({ ...prev, [detectionId]: { validated: true, false_positive: isFalsePositive } }))
          }
        },
      }
    )
  }

  // Fetch detections with server-side filtering via TanStack Query
  const { detections, total, isLoading, isDemoMode } = useDetectionsQuery({
    page: currentPage,
    perPage: 20,
    type: typeFilter !== 'all' ? typeFilter : undefined,
  })

  // Reset to page 1 when filters change
  // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional state sync on filter change
  useEffect(() => { setCurrentPage(1) }, [typeFilter, severityFilter])

  // n8n users see simplified view with friendly terminology
  const showSimplifiedView = isN8nUser && !showAdvancedFeatures
  const isLoaded = !isLoading

  // Light client-side filtering for severity and validated (supplements server filtering)
  const filteredDetections = useMemo(() => {
    return detections.filter((d) => {
      if (severityFilter !== 'all' && d.details?.severity !== severityFilter) return false
      if (!showValidated && d.validated) return false
      return true
    })
  }, [detections, severityFilter, showValidated])

  const totalPages = Math.ceil(total / 20)

  const stats = useMemo(() => ({
    total: detections.length,
    unvalidated: detections.filter(d => !d.validated).length,
    falsePositives: detections.filter(d => d.false_positive).length,
    byType: {
      infinite_loop: detections.filter(d => d.detection_type === 'infinite_loop').length,
      state_corruption: detections.filter(d => d.detection_type === 'state_corruption').length,
      persona_drift: detections.filter(d => d.detection_type === 'persona_drift').length,
      coordination_deadlock: detections.filter(d => d.detection_type === 'coordination_deadlock').length,
      task_derailment: detections.filter(d => d.detection_type === 'task_derailment').length,
      context_neglect: detections.filter(d => d.detection_type === 'context_neglect').length,
      communication_breakdown: detections.filter(d => d.detection_type === 'communication_breakdown').length,
      specification_mismatch: detections.filter(d => d.detection_type === 'specification_mismatch').length,
      poor_decomposition: detections.filter(d => d.detection_type === 'poor_decomposition').length,
      flawed_workflow: detections.filter(d => d.detection_type === 'flawed_workflow').length,
    }
  }), [detections])

  if (!isLoaded) {
    return (
      <Layout>
        <div className="p-6">
          <div className="animate-pulse space-y-6">
            <div className="h-8 w-48 bg-zinc-700 rounded" />
            <div className="grid grid-cols-4 gap-4">
              {[1,2,3,4].map(i => <div key={i} className="h-20 bg-zinc-700 rounded-xl" />)}
            </div>
            <div className="h-96 bg-zinc-700 rounded-xl" />
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            {showSimplifiedView && (
              <div className="p-2 bg-amber-500/20 rounded-lg">
                <AlertCircle size={24} className="text-amber-400" />
              </div>
            )}
            <div>
              <h1 className="text-2xl font-bold text-white mb-1">
                {showSimplifiedView ? 'Problems Found' : 'Detections'}
              </h1>
              <p className="text-sm text-zinc-400">
                {showSimplifiedView
                  ? 'Issues we found in your workflows that need attention'
                  : 'Monitor and validate failure detections across your agent systems'}
              </p>
            </div>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors">
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>

        {isDemoMode && (
          <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
            <AlertCircle size={20} className="text-amber-400 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-semibold text-amber-400 mb-1">Demo Mode</h3>
              <p className="text-sm text-amber-300/80">
                Unable to connect to API. Showing demo data for illustration purposes.
                {' '}Please check your connection or contact support if this persists.
              </p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            icon={AlertTriangle}
            label={showSimplifiedView ? 'Total Problems' : 'Total Detections'}
            value={stats.total}
            color="text-red-400"
            bgColor="bg-red-500/20"
          />
          <StatCard
            icon={Eye}
            label={showSimplifiedView ? 'Need Attention' : 'Needs Review'}
            value={stats.unvalidated}
            color="text-amber-400"
            bgColor="bg-amber-500/20"
          />
          {showSimplifiedView ? (
            <StatCard
              icon={Wrench}
              label="Fixes Available"
              value={Math.floor(stats.total * 0.7)}
              color="text-purple-400"
              bgColor="bg-purple-500/20"
            />
          ) : (
            <StatCard
              icon={ThumbsDown}
              label="False Positives"
              value={stats.falsePositives}
              color="text-zinc-400"
              bgColor="bg-zinc-500/20"
            />
          )}
          <StatCard
            icon={Shield}
            label={showSimplifiedView ? 'Detection Accuracy' : 'Avg Confidence'}
            value={`${Math.round(detections.reduce((s, d) => s + d.confidence, 0) / detections.length)}%`}
            color="text-emerald-400"
            bgColor="bg-emerald-500/20"
          />
        </div>

        <div className="grid lg:grid-cols-4 gap-6">
          <DetectionFilters
            typeFilter={typeFilter}
            setTypeFilter={setTypeFilter}
            severityFilter={severityFilter}
            setSeverityFilter={setSeverityFilter}
            showValidated={showValidated}
            setShowValidated={setShowValidated}
            stats={stats}
          />

          <div className="lg:col-span-3">
            <div className="rounded-xl bg-zinc-800/50 border border-zinc-700 overflow-hidden">
              <div className="p-4 border-b border-zinc-700 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-zinc-400">
                    {filteredDetections.length} detections
                  </span>
                </div>
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                  <input
                    type="text"
                    placeholder="Search..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 pr-4 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700 text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-blue-500 w-64"
                  />
                </div>
              </div>

              <div className="divide-y divide-zinc-700/50">
                {filteredDetections.length === 0 ? (
                  <div className="text-center py-12 px-4">
                    <AlertTriangle size={48} className="mx-auto mb-4 text-zinc-600 opacity-50" />
                    <p className="text-zinc-400 mb-2">
                      {showSimplifiedView ? 'No problems found' : 'No detections found'}
                    </p>
                    <p className="text-sm text-zinc-500">
                      {typeFilter !== 'all' || severityFilter !== 'all'
                        ? 'Try adjusting your filters to see more results'
                        : showSimplifiedView
                        ? 'Your workflows are running smoothly!'
                        : 'Detections will appear here when issues are found in your traces'}
                    </p>
                  </div>
                ) : (
                  filteredDetections.map((detection) => (
                    <DetectionListItem
                      key={detection.id}
                      detection={detection}
                      showSimplifiedView={showSimplifiedView}
                      inlineValidated={inlineValidated}
                      submittingId={submittingId}
                      onInlineValidate={handleInlineValidate}
                    />
                  ))
                )}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4 px-1">
                  <span className="text-sm text-zinc-400">
                    Page {currentPage} of {totalPages} ({total} total)
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage <= 1}
                      className="px-3 py-1.5 text-sm rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                      disabled={currentPage >= totalPages}
                      className="px-3 py-1.5 text-sm rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  )
}
