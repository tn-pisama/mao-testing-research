'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { Upload, Wifi, WifiOff, AlertTriangle } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { LoopAnalyticsCard } from '@/components/dashboard/LoopAnalyticsCard'
import { CostAnalyticsCard } from '@/components/dashboard/CostAnalyticsCard'
import { RecentDetectionsCard } from '@/components/dashboard/RecentDetectionsCard'
import { TraceStatusCard } from '@/components/traces/TraceStatusCard'
import { WorkflowAttentionList } from '@/components/dashboard/WorkflowAttentionList'
import { QualitySuggestionsCard } from '@/components/dashboard/QualitySuggestionsCard'
import { WorkflowOverviewStats } from '@/components/dashboard/WorkflowOverviewStats'
import { WorkflowDataTable } from '@/components/dashboard/WorkflowDataTable'
import { WorkflowDetailPanel } from '@/components/dashboard/WorkflowDetailPanel'
import { WorkflowGroupFilter } from '@/components/filters/WorkflowGroupFilter'
import { ManageGroupsModal } from '@/components/modals/ManageGroupsModal'
import { Button } from '@/components/ui/Button'
import { ImportModal } from '@/components/import'
import { useApiWithFallback } from '@/hooks/useApiWithFallback'
import { useUserPreferences } from '@/lib/user-preferences'

export default function DashboardPage() {
  const {
    isLoading,
    isDemoMode,
    error,
    loopAnalytics,
    costAnalytics,
    detections,
    traces,
    qualityAssessments,
    refresh,
  } = useApiWithFallback()
  const [showImportModal, setShowImportModal] = useState(false)
  const [isManageModalOpen, setIsManageModalOpen] = useState(false)
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null)
  const { isN8nUser, showAdvancedFeatures } = useUserPreferences()

  // n8n users see simplified view unless they enabled developer mode
  const showSimplifiedDashboard = isN8nUser && !showAdvancedFeatures

  // Get selected workflow
  const selectedWorkflow = selectedWorkflowId
    ? qualityAssessments.find(a => a.workflow_id === selectedWorkflowId)
    : null

  if (isLoading) {
    return (
      <Layout>
        <div className="p-6">
          <div className="h-8 w-40 bg-slate-700 rounded mb-6 animate-pulse" />
          <div className="grid lg:grid-cols-2 gap-6 mb-6">
            <div className="h-64 bg-slate-700 rounded-xl animate-pulse" />
            <div className="h-64 bg-slate-700 rounded-xl animate-pulse" />
          </div>
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="h-64 bg-slate-700 rounded-xl animate-pulse" />
            <div className="h-64 bg-slate-700 rounded-xl animate-pulse" />
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
            <h1 className="text-2xl font-bold text-white">
              {showSimplifiedDashboard ? 'Workflow Overview' : 'Dashboard'}
            </h1>
            {isDemoMode && (
              <span className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
                <WifiOff size={12} />
                Demo Mode
              </span>
            )}
            {!isDemoMode && (
              <span className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
                <Wifi size={12} />
                Live
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <WorkflowGroupFilter onManageGroups={() => setIsManageModalOpen(true)} />
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

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertTriangle size={20} className="text-red-400 flex-shrink-0" />
            <p className="text-sm text-red-300 flex-1">{error}</p>
            <Button variant="ghost" size="sm" onClick={refresh}>
              Retry
            </Button>
          </div>
        )}

        {showSimplifiedDashboard ? (
          <>
            {/* Simplified n8n user dashboard - WORKFLOW-CENTRIC */}

            {/* 1. Workflow Overview Stats */}
            <WorkflowOverviewStats workflows={qualityAssessments} isLoading={false} />

            {/* 2. Workflow List - PRIMARY FOCUS */}
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

            {/* 3. Workflows Needing Attention */}
            <WorkflowAttentionList detections={detections} isLoading={false} />

            {/* 4. Improvement Suggestions */}
            <div className="mt-6">
              <QualitySuggestionsCard
                suggestions={qualityAssessments.flatMap(a => a.improvements)}
                isLoading={false}
                maxItems={8}
              />
            </div>
          </>
        ) : (
          <>
            {/* Full developer dashboard - WORKFLOW-CENTRIC */}

            {/* 1. Workflow Overview Stats */}
            <WorkflowOverviewStats workflows={qualityAssessments} isLoading={false} />

            {/* 2. Workflow List - PRIMARY FOCUS */}
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

            {/* 3. Workflows Needing Attention */}
            <WorkflowAttentionList detections={detections} isLoading={false} />

            {/* 4. Improvement Suggestions */}
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

            {/* 5. Developer Analytics (Below Fold) */}
            <div className="mt-8 pt-8 border-t border-slate-700">
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
          </>
        )}
      </div>

      {/* Workflow Detail Panel (Slide-in) */}
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

      {/* Manage Groups Modal */}
      <ManageGroupsModal
        isOpen={isManageModalOpen}
        onClose={() => setIsManageModalOpen(false)}
      />
    </Layout>
  )
}
