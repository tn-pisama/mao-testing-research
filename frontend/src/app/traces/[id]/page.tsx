'use client'

import { useQuery } from '@tanstack/react-query'
import { useParams } from 'next/navigation'
import { Layout } from '@/components/common/Layout'
import { TraceViewer } from '@/components/traces/TraceViewer'
import { TraceTimeline } from '@/components/traces/TraceTimeline'
import { StateHistory } from '@/components/states/StateHistory'
import { FailureCard } from '@/components/detection/FailureCard'
import { api } from '@/lib/api'

export default function TraceDetailPage() {
  const { id } = useParams<{ id: string }>()

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
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-2">
            Trace: {trace?.session_id?.slice(0, 8)}...
          </h1>
          <div className="flex gap-4 text-sm text-slate-400">
            <span>Framework: {trace?.framework}</span>
            <span>Status: {trace?.status}</span>
            <span>Tokens: {trace?.total_tokens?.toLocaleString()}</span>
          </div>
        </div>

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

        <div className="grid lg:grid-cols-2 gap-6">
          <div>
            <h2 className="text-lg font-semibold text-white mb-3">Timeline</h2>
            <TraceTimeline states={states || []} isLoading={statesLoading} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white mb-3">State History</h2>
            <StateHistory states={states || []} isLoading={statesLoading} />
          </div>
        </div>

        <div className="mt-6">
          <h2 className="text-lg font-semibold text-white mb-3">Trace Visualization</h2>
          <TraceViewer states={states || []} />
        </div>
      </div>
    </Layout>
  )
}
