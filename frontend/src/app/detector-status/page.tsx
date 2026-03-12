'use client'

import { Layout } from '@/components/common/Layout'
import { DetectorStatusDashboard } from '@/components/detection'
import { useDetectorStatusQuery } from '@/hooks/useQueries'

export default function DetectorStatusPage() {
  const { data, isLoading } = useDetectorStatusQuery()

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Detector Status</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Readiness tiers, calibration scores, and sample coverage for all detectors.
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          </div>
        ) : data ? (
          <DetectorStatusDashboard data={data} />
        ) : (
          <div className="text-center text-zinc-400 py-16">
            No detector status data available. Run calibration to generate data.
          </div>
        )}
      </div>
    </Layout>
  )
}
