'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import nextDynamic from 'next/dynamic'
import { Upload, Wifi, WifiOff } from 'lucide-react'
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
  useLoopAnalyticsQuery,
  useCostAnalyticsQuery,
  useDetectionsQuery,
  useTracesQuery,
  useQualityAssessmentsQuery,
} from '@/hooks/useQueries'
import { useQueryClient } from '@tanstack/react-query'
import { useUserPreferences } from '@/lib/user-preferences'
import { useUIStore } from '@/stores/uiStore'

export default function DashboardPage() {
  const queryClient = useQueryClient()
  const { filterPreferences } = useUIStore()

  const groupId = filterPreferences.workflowGroupId && filterPreferences.workflowGroupId !== 'all'
    ? filterPreferences.workflowGroupId
    : undefined

  const loopQ = useLoopAnalyticsQuery(30)
  const costQ = useCostAnalyticsQuery(30)
  const detectionsQ = useDetectionsQuery({ perPage: 10 })
  const tracesQ = useTracesQuery({ perPage: 10 })
  const qualityQ = useQualityAssessmentsQuery({ pageSize: 20, groupId })

  const isLoading = loopQ.isLoading || costQ.isLoading || detectionsQ.isLoading || tracesQ.isLoading || qualityQ.isLoading
  const isDemoMode = loopQ.isDemoMode || costQ.isDemoMode || detectionsQ.isDemoMode || tracesQ.isDemoMode || qualityQ.isDemoMode
  const loopAnalytics = loopQ.data ?? undefined
  const costAnalytics = costQ.data ?? undefined
  const detections = detectionsQ.detections
  const traces = tracesQ.traces
  const qualityAssessments = qualityQ.assessments

  const refresh = () => queryClient.invalidateQueries()

  const [showImportModal, setShowImportModal] = useState(false)
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null)
  const { isN8nUser, showAdvancedFeatures } = useUserPreferences()

  const showSimplifiedDashboard = isN8nUser && !showAdvancedFeatures

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
              <WorkflowOverviewStats workflows={qualityAssessments} isLoading={false} />
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
            <StaggerItem>
              <WorkflowOverviewStats workflows={qualityAssessments} isLoading={false} />
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
              <div className="grid lg:grid-cols-2 gap-6 mb-6 mt-6">
                <QualitySuggestionsCard
                  suggestions={qualityAssessments.flatMap(a => a.improvements)}
                  isLoading={false}
                  maxItems={6}
                />
                <TraceStatusCard
                  traces={traces}
                  isLoading={false}
                />
              </div>
            </StaggerItem>

            <StaggerItem>
              <div className="mt-8 pt-8 border-t border-zinc-800">
                <h2 className="text-lg font-semibold text-white mb-4">Developer Analytics</h2>
                <div className="grid lg:grid-cols-2 gap-6 mb-6">
                  <LoopAnalyticsCard data={loopAnalytics} isLoading={false} />
                  <CostAnalyticsCard data={costAnalytics} isLoading={false} />
                </div>
                <div className="grid lg:grid-cols-2 gap-6">
                  <RecentDetectionsCard
                    detections={detections}
                    isLoading={false}
                  />
                </div>
              </div>
            </StaggerItem>
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
