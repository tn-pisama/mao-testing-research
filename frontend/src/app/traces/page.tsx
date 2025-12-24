'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Layout } from '@/components/common/Layout'
import { TraceList } from '@/components/traces/TraceList'
import { TraceSearch } from '@/components/traces/TraceSearch'
import { api } from '@/lib/api'

export default function TracesPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string | undefined>()

  const { data, isLoading } = useQuery({
    queryKey: ['traces', page, statusFilter],
    queryFn: () => api.getTraces({ page, perPage: 20, status: statusFilter }),
  })

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
          traces={data?.traces || []}
          isLoading={isLoading}
          total={data?.total || 0}
          page={page}
          perPage={20}
          onPageChange={setPage}
        />
      </div>
    </Layout>
  )
}
