'use client'

export const dynamic = 'force-dynamic'

import { useState } from 'react'
import { Upload, Wifi, WifiOff } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { LoopAnalyticsCard } from '@/components/dashboard/LoopAnalyticsCard'
import { CostAnalyticsCard } from '@/components/dashboard/CostAnalyticsCard'
import { RecentDetectionsCard } from '@/components/dashboard/RecentDetectionsCard'
import { TraceStatusCard } from '@/components/traces/TraceStatusCard'
import { WorkflowHealthCard } from '@/components/dashboard/WorkflowHealthCard'
import { ProblemsOverviewCard } from '@/components/dashboard/ProblemsOverviewCard'
import { FixesStatusCard } from '@/components/dashboard/FixesStatusCard'
import { WorkflowAttentionList } from '@/components/dashboard/WorkflowAttentionList'
import { Button } from '@/components/ui/Button'
import { ImportModal } from '@/components/import'
import { useApiWithFallback } from '@/hooks/useApiWithFallback'
import { useUserPreferences } from '@/lib/user-preferences'

export default function DashboardPage() {
  const {
    isLoading,
    isDemoMode,
    loopAnalytics,
    costAnalytics,
    detections,
    traces,
    refresh,
  } = useApiWithFallback()
  const [showImportModal, setShowImportModal] = useState(false)
  const { isN8nUser, showAdvancedFeatures } = useUserPreferences()

  // n8n users see simplified view unless they enabled developer mode
  const showSimplifiedDashboard = isN8nUser && !showAdvancedFeatures

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
          <div className="flex items-center gap-2">
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

        {showSimplifiedDashboard ? (
          <>
            {/* Simplified n8n user dashboard */}
            <div className="grid lg:grid-cols-3 gap-6 mb-6">
              <WorkflowHealthCard traces={traces} isLoading={false} />
              <ProblemsOverviewCard detections={detections} isLoading={false} />
              <FixesStatusCard isLoading={false} />
            </div>

            <WorkflowAttentionList detections={detections} isLoading={false} />
          </>
        ) : (
          <>
            {/* Full developer dashboard */}
            <div className="grid lg:grid-cols-2 gap-6 mb-6">
              <LoopAnalyticsCard data={loopAnalytics} isLoading={false} />
              <CostAnalyticsCard data={costAnalytics} isLoading={false} />
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
              <RecentDetectionsCard
                detections={detections}
                isLoading={false}
              />
              <TraceStatusCard
                traces={traces}
                isLoading={false}
              />
            </div>
          </>
        )}
      </div>

      <ImportModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        onImportComplete={() => {}}
      />
    </Layout>
  )
}
