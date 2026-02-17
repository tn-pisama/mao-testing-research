'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import { Layout } from '@/components/common/Layout'
import { TraceViewer } from '@/components/traces/TraceViewer'
import { WaterfallTimeline } from '@/components/traces/WaterfallTimeline'
import { TraceFlowGraph } from '@/components/traces/TraceFlowGraph'
import { FailureCard } from '@/components/detection/FailureCard'
import { api } from '@/lib/api'

type TraceTab = 'waterfall' | 'flow' | 'states'

const tabs: { id: TraceTab; label: string }[] = [
  { id: 'waterfall', label: 'Waterfall' },
  { id: 'flow', label: 'Flow Graph' },
  { id: 'states', label: 'States' },
]

export default function TraceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [activeTab, setActiveTab] = useState<TraceTab>('waterfall')

  const { data: trace, isLoading: traceLoading } = useQuery({
    queryKey: ['trace', id],
    queryFn: () => api.getTrace(id),
    enabled: !!id,
  })

  const { data: states, isLoading: statesLoading } = useQuery({
    queryKey: ['trace', id, 'states'],
    queryFn: () => api.getTraceStates(id),
    enabled: !!id,
  })

  const { data: detections } = useQuery({
    queryKey: ['detections', 'trace', id],
    queryFn: () => api.getDetections({ traceId: id }),
    enabled: !!id,
  })

  if (traceLoading) {
    return (
      <Layout>
        <div className="p-6 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-2">
            Trace: {trace?.session_id?.slice(0, 8)}...
          </h1>
          <div className="flex gap-4 text-sm text-slate-400">
            <span>Framework: {trace?.framework}</span>
            <span>Status: {trace?.status}</span>
            <span>Tokens: {trace?.total_tokens?.toLocaleString()}</span>
            {trace?.total_cost_cents != null && trace.total_cost_cents > 0 && (
              <span>Cost: ${(trace.total_cost_cents / 100).toFixed(2)}</span>
            )}
            <span>States: {states?.length ?? trace?.state_count ?? 0}</span>
          </div>
        </div>

        {/* Detected Issues */}
        {detections && detections.length > 0 && (
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-white mb-3">Detected Issues</h2>
            <div className="grid gap-4">
              {detections.map((d: any) => (
                <FailureCard key={d.id} detection={d} />
              ))}
            </div>
          </div>
        )}

        {/* Tab bar */}
        <div className="flex gap-1 mb-6 bg-slate-800 rounded-lg p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-slate-700 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'waterfall' && (
          <WaterfallTimeline states={states || []} />
        )}

        {activeTab === 'flow' && (
          <TraceFlowGraph states={states || []} height={500} />
        )}

        {activeTab === 'states' && (
          <TraceViewer trace={trace} states={states || []} isLoading={statesLoading} />
        )}
      </div>
    </Layout>
  )
}
