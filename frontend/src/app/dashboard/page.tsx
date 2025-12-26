'use client'

import { useState, useEffect } from 'react'
import { Upload } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { LoopAnalyticsCard } from '@/components/detection/LoopAnalyticsCard'
import { CostAnalyticsCard } from '@/components/detection/CostAnalyticsCard'
import { RecentDetectionsCard } from '@/components/detection/RecentDetectionsCard'
import { TraceStatusCard } from '@/components/traces/TraceStatusCard'
import { Button } from '@/components/ui/Button'
import { ImportModal } from '@/components/import'
import {
  generateDemoLoopAnalytics,
  generateDemoCostAnalytics,
  generateDemoDetections,
  generateDemoTraces,
} from '@/lib/demo-data'
import type { LoopAnalytics, CostAnalytics, Detection, Trace } from '@/lib/api'

export default function DashboardPage() {
  const [isLoading, setIsLoading] = useState(true)
  const [loopAnalytics, setLoopAnalytics] = useState<LoopAnalytics | undefined>()
  const [costAnalytics, setCostAnalytics] = useState<CostAnalytics | undefined>()
  const [detections, setDetections] = useState<Detection[]>([])
  const [traces, setTraces] = useState<Trace[]>([])
  const [showImportModal, setShowImportModal] = useState(false)

  useEffect(() => {
    setLoopAnalytics(generateDemoLoopAnalytics())
    setCostAnalytics(generateDemoCostAnalytics())
    setDetections(generateDemoDetections(5))
    setTraces(generateDemoTraces(5))
    setIsLoading(false)
  }, [])

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
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <Button
            onClick={() => setShowImportModal(true)}
            leftIcon={<Upload size={16} />}
          >
            Import Historical Data
          </Button>
        </div>
        
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
      </div>

      <ImportModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        onImportComplete={(jobId) => {
          console.log('Import completed:', jobId)
        }}
      />
    </Layout>
  )
}
