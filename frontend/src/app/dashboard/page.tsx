'use client'

import { useQuery } from '@tanstack/react-query'
import { Layout } from '@/components/common/Layout'
import { LoopAnalyticsCard } from '@/components/detection/LoopAnalyticsCard'
import { CostAnalyticsCard } from '@/components/detection/CostAnalyticsCard'
import { RecentDetectionsCard } from '@/components/detection/RecentDetectionsCard'
import { TraceStatusCard } from '@/components/traces/TraceStatusCard'
import { api } from '@/lib/api'

export default function DashboardPage() {
  const { data: loopAnalytics, isLoading: loopsLoading } = useQuery({
    queryKey: ['analytics', 'loops'],
    queryFn: () => api.getLoopAnalytics(30),
  })

  const { data: costAnalytics, isLoading: costLoading } = useQuery({
    queryKey: ['analytics', 'cost'],
    queryFn: () => api.getCostAnalytics(30),
  })

  const { data: detections, isLoading: detectionsLoading } = useQuery({
    queryKey: ['detections', 'recent'],
    queryFn: () => api.getDetections({ page: 1, perPage: 5 }),
  })

  const { data: traces, isLoading: tracesLoading } = useQuery({
    queryKey: ['traces', 'recent'],
    queryFn: () => api.getTraces({ page: 1, perPage: 5 }),
  })

  return (
    <Layout>
      <div className="p-6">
        <h1 className="text-2xl font-bold text-white mb-6">Dashboard</h1>
        
        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          <LoopAnalyticsCard data={loopAnalytics} isLoading={loopsLoading} />
          <CostAnalyticsCard data={costAnalytics} isLoading={costLoading} />
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <RecentDetectionsCard 
            detections={detections?.detections || []} 
            isLoading={detectionsLoading} 
          />
          <TraceStatusCard 
            traces={traces?.traces || []} 
            isLoading={tracesLoading} 
          />
        </div>
      </div>
    </Layout>
  )
}
