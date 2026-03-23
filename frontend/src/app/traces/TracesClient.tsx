'use client'

import { useState, useMemo } from 'react'
import { Wifi, WifiOff } from 'lucide-react'
import { Layout } from '@/components/common/Layout'
import { TraceList } from '@/components/traces/TraceList'
import { TraceSearch } from '@/components/traces/TraceSearch'
import { useTracesQuery } from '@/hooks/useQueries'
import type { Trace } from '@/lib/api'

interface TracesClientProps {
  initialData: { traces: Trace[]; total: number } | null
}

export function TracesClient({ initialData }: TracesClientProps) {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [frameworkFilter, setFrameworkFilter] = useState<string | undefined>()

  const { traces: allTraces, total: _total, isLoading, isDemoMode } = useTracesQuery({
    page,
    perPage: 50,
    status: statusFilter,
  }, initialData)

  const filteredTraces = useMemo(() => {
    let result = allTraces
    if (statusFilter) {
      result = result.filter(t => t.status === statusFilter)
    }
    if (frameworkFilter) {
      result = result.filter(t => t.framework === frameworkFilter)
    }
    return result
  }, [allTraces, statusFilter, frameworkFilter])

  const paginatedTraces = useMemo(() => {
    const start = (page - 1) * 20
    return filteredTraces.slice(start, start + 20)
  }, [filteredTraces, page])

  if (isLoading) {
    return (
      <Layout>
        <div className="p-6">
          <div className="h-8 w-32 bg-zinc-700 rounded mb-6 animate-pulse" />
          <div className="space-y-4">
            {[1,2,3,4,5].map(i => (
              <div key={i} className="h-20 bg-zinc-700 rounded-xl animate-pulse" />
            ))}
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="p-6">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">Runs</h1>
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
          <TraceSearch
            statusFilter={statusFilter}
            onStatusChange={setStatusFilter}
            frameworkFilter={frameworkFilter}
            onFrameworkChange={setFrameworkFilter}
          />
        </div>

        <TraceList
          traces={paginatedTraces}
          isLoading={false}
          total={filteredTraces.length}
          page={page}
          perPage={20}
          onPageChange={setPage}
        />
      </div>
    </Layout>
  )
}
