'use client'

import { useState, useEffect, useMemo } from 'react'
import { Layout } from '@/components/common/Layout'
import { TraceList } from '@/components/traces/TraceList'
import { TraceSearch } from '@/components/traces/TraceSearch'
import { generateDemoTraces } from '@/lib/demo-data'
import type { Trace } from '@/lib/api'

export default function TracesPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [isLoading, setIsLoading] = useState(true)
  const [allTraces, setAllTraces] = useState<Trace[]>([])

  useEffect(() => {
    setAllTraces(generateDemoTraces(50))
    setIsLoading(false)
  }, [])

  const filteredTraces = useMemo(() => {
    if (!statusFilter) return allTraces
    return allTraces.filter(t => t.status === statusFilter)
  }, [allTraces, statusFilter])

  const paginatedTraces = useMemo(() => {
    const start = (page - 1) * 20
    return filteredTraces.slice(start, start + 20)
  }, [filteredTraces, page])

  if (isLoading) {
    return (
      <Layout>
        <div className="p-6">
          <div className="h-8 w-32 bg-slate-700 rounded mb-6 animate-pulse" />
          <div className="space-y-4">
            {[1,2,3,4,5].map(i => (
              <div key={i} className="h-20 bg-slate-700 rounded-xl animate-pulse" />
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
          <h1 className="text-2xl font-bold text-white">Traces</h1>
          <TraceSearch 
            statusFilter={statusFilter} 
            onStatusChange={setStatusFilter} 
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
