'use client'

import { useState } from 'react'
import nextDynamic from 'next/dynamic'
import { Upload, Wifi, WifiOff, Activity, AlertTriangle, Layers } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { RecentDetectionsCard } from '@/components/dashboard/RecentDetectionsCard'
import { TraceStatusCard } from '@/components/traces/TraceStatusCard'
import { WorkflowAttentionList } from '@/components/dashboard/WorkflowAttentionList'
import { QualitySuggestionsCard } from '@/components/dashboard/QualitySuggestionsCard'
import { WorkflowOverviewStats } from '@/components/dashboard/WorkflowOverviewStats'
import { WorkflowDataTable } from '@/components/dashboard/WorkflowDataTable'
import { WorkflowDetailPanel } from '@/components/dashboard/WorkflowDetailPanel'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { FadeIn, StaggerContainer, StaggerItem } from '@/components/ui/Motion'
import { ImportModal } from '@/components/import'

const LoopAnalyticsCard = nextDynamic(
  () => import('@/components/dashboard/LoopAnalyticsCard').then(mod => ({ default: mod.LoopAnalyticsCard })),
  { ssr: false, loading: () => <Skeleton className="h-64 rounded-xl" /> }
)
const CostAnalyticsCard = nextDynamic(
  () => import('@/components/dashboard/CostAnalyticsCard').then(mod => ({ default: mod.CostAnalyticsCard })),
  { ssr: false, loading: () => <Skeleton className="h-64 rounded-xl" /> }
)
import {
  useDashboardQuery,
  type DashboardData,
} from '@/hooks/useQueries'
import { useQueryClient } from '@tanstack/react-query'
import { useUserPreferences } from '@/lib/user-preferences'

export function DashboardClient({ initialData }: { initialData: DashboardData | null }) {
  const queryClient = useQueryClient()

  const dashQ = useDashboardQuery(30, initialData)

  const isLoading = dashQ.isLoading
  const isDemoMode = dashQ.isDemoMode
  const loopAnalytics = dashQ.loopAnalytics ?? undefined
  const costAnalytics = dashQ.costAnalytics ?? undefined
  const detections = dashQ.detections
  const traces = dashQ.traces
  const qualityAssessments = dashQ.assessments

  const refresh = () => queryClient.invalidateQueries()

  const [showImportModal, setShowImportModal] = useState(false)
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null)
  const { isN8nUser, showAdvancedFeatures } = useUserPreferences()

  const showSimplifiedDashboard = isN8nUser && !showAdvancedFeatures
  const hasAssessments = qualityAssessments.length > 0

  const selectedWorkflow = selectedWorkflowId
    ? qualityAssessments.find(a => a.workflow_id === selectedWorkflowId)
    : null

  if (isLoading) {
    return (
      <Layout>
        <div className="p-6">
          <Skeleton className="h-8 w-40 mb-6" />
          <div className="grid lg:grid-cols-2 gap-6 mb-6">
            <Skeleton className="h-64 rounded-xl" />
            <Skeleton className="h-64 rounded-xl" />
          </div>
          <div className="grid lg:grid-cols-2 gap-6">
            <Skeleton className="h-64 rounded-xl" />
            <Skeleton className="h-64 rounded-xl" />
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <FadeIn>
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white">
                {showSimplifiedDashboard ? 'Workflow Overview' : 'Dashboard'}
              </h1>
              {isDemoMode && (
                <span className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  <WifiOff size={12} />
                  Demo Mode
                </span>
              )}
              {!isDemoMode && (
                <span className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-full bg-green-500/10 text-green-400 border border-green-500/20">
                  <Wifi size={12} />
                  Live
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <Button
                onClick={refresh}
                variant="secondary"
                size="sm"
              >
                Refresh
              </Button>
              {!showSimplifiedDashboard && (
                <Button
                  onClick={() => setShowImportModal(true)}
                >
                  <Upload size={16} className="mr-2" />
                  Import Historical Data
                </Button>
              )}
            </div>
          </div>
        </FadeIn>

        {showSimplifiedDashboard ? (
          <StaggerContainer stagger={0.06}>
            <StaggerItem>
              <WorkflowOverviewStats workflows={qualityAssessments} total={dashQ.assessmentsTotal} isLoading={false} />
            </StaggerItem>

            <StaggerItem>
              <div className="mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-white">Your Workflows</h2>
                </div>
                <WorkflowDataTable
                  workflows={qualityAssessments}
                  onSelectWorkflow={setSelectedWorkflowId}
                  selectedWorkflowId={selectedWorkflowId}
                />
              </div>
            </StaggerItem>

            <StaggerItem>
              <WorkflowAttentionList detections={detections} isLoading={false} />
            </StaggerItem>

            <StaggerItem>
              <div className="mt-6">
                <QualitySuggestionsCard
                  suggestions={qualityAssessments.flatMap(a => a.improvements)}
                  isLoading={false}
                  maxItems={8}
                />
              </div>
            </StaggerItem>
          </StaggerContainer>
        ) : (
          <StaggerContainer stagger={0.06}>
            {/* Overview stats: show general stats when no assessments, workflow stats when they exist */}
            <StaggerItem>
              {hasAssessments ? (
                <WorkflowOverviewStats workflows={qualityAssessments} total={dashQ.assessmentsTotal} isLoading={false} />
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                  <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
                    <div className="flex items-center gap-2 mb-1">
                      <Layers size={18} className="text-blue-400" />
                      <div className="text-xs text-zinc-400">Total Runs</div>
                    </div>
                    <div className="text-2xl font-bold text-blue-400">{dashQ.tracesTotal}</div>
                    <div className="text-xs text-zinc-500 mt-0.5">Last 30 days</div>
                  </div>
                  <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
                    <div className="flex items-center gap-2 mb-1">
                      <AlertTriangle size={18} className="text-amber-400" />
                      <div className="text-xs text-zinc-400">Detections</div>
                    </div>
                    <div className="text-2xl font-bold text-amber-400">{dashQ.detectionsTotal}</div>
                    <div className="text-xs text-zinc-500 mt-0.5">Issues found</div>
                  </div>
                  <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
                    <div className="flex items-center gap-2 mb-1">
                      <Activity size={18} className="text-green-400" />
                      <div className="text-xs text-zinc-400">Detection Rate</div>
                    </div>
                    <div className="text-2xl font-bold text-green-400">
                      {dashQ.tracesTotal > 0
                        ? `${((dashQ.detectionsTotal / dashQ.tracesTotal) * 100).toFixed(0)}%`
                        : '—'}
                    </div>
                    <div className="text-xs text-zinc-500 mt-0.5">Issues per trace</div>
                  </div>
                  <div className="bg-zinc-800 rounded-lg p-3 border border-zinc-700">
                    <div className="flex items-center gap-2 mb-1">
                      <div className="text-xs text-zinc-400">Assessments</div>
                    </div>
                    <div className="text-2xl font-bold text-zinc-500">{dashQ.assessmentsTotal}</div>
                    <div className="text-xs text-zinc-500 mt-0.5">Quality reviews</div>
                  </div>
                </div>
              )}
            </StaggerItem>

            {/* Traces and detections first (always visible) */}
            <StaggerItem>
              <div className="grid lg:grid-cols-2 gap-6 mb-6">
                <TraceStatusCard
                  traces={traces}
                  isLoading={false}
                />
                <RecentDetectionsCard
                  detections={detections}
                  isLoading={false}
                />
              </div>
            </StaggerItem>

            {/* Detection alerts */}
            <StaggerItem>
              <WorkflowAttentionList detections={detections} isLoading={false} />
            </StaggerItem>

            {/* Analytics */}
            <StaggerItem>
              <div className="grid lg:grid-cols-2 gap-6 mb-6 mt-6">
                <LoopAnalyticsCard data={loopAnalytics} isLoading={false} />
                <CostAnalyticsCard data={costAnalytics} isLoading={false} />
              </div>
            </StaggerItem>

            {/* Quality assessments section — only show when there's data */}
            {hasAssessments && (
              <>
                <StaggerItem>
                  <div className="mt-8 pt-8 border-t border-zinc-800">
                    <h2 className="text-lg font-semibold text-white mb-4">Workflow Quality</h2>
                    <WorkflowOverviewStats workflows={qualityAssessments} total={dashQ.assessmentsTotal} isLoading={false} />
                  </div>
                </StaggerItem>

                <StaggerItem>
                  <div className="mb-6">
                    <WorkflowDataTable
                      workflows={qualityAssessments}
                      onSelectWorkflow={setSelectedWorkflowId}
                      selectedWorkflowId={selectedWorkflowId}
                    />
                  </div>
                </StaggerItem>

                <StaggerItem>
                  <QualitySuggestionsCard
                    suggestions={qualityAssessments.flatMap(a => a.improvements)}
                    isLoading={false}
                    maxItems={6}
                  />
                </StaggerItem>
              </>
            )}
          </StaggerContainer>
        )}
      </div>

      {selectedWorkflow && (
        <WorkflowDetailPanel
          workflow={selectedWorkflow}
          onClose={() => setSelectedWorkflowId(null)}
        />
      )}

      <ImportModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        onImportComplete={() => {}}
      />

    </Layout>
  )
}
