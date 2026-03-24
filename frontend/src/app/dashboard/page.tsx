import { getServerApiToken, serverFetch } from '@/lib/server-auth'
import { DashboardClient } from './DashboardClient'
import type { DashboardData } from '@/hooks/useQueries'

export default async function DashboardPage() {
  const auth = await getServerApiToken()
  const initialData = auth
    ? await serverFetch<DashboardData>('/dashboard?days=30', auth)
    : null

  // Temporary debug: show what the SSR resolved
  const debugInfo = {
    hasTenant: !!auth?.tenantId,
    tenant: auth?.tenantId?.slice(0, 8),
    hasData: !!initialData,
    traces: (initialData as any)?.traces?.total ?? 'none',
  }

  return (
    <>
      {/* Debug banner — remove after verifying */}
      <div className="bg-zinc-900 text-zinc-500 text-xs px-4 py-1 font-mono">
        SSR: tenant={debugInfo.tenant || 'null'} traces={debugInfo.traces}
      </div>
      <DashboardClient initialData={initialData} />
    </>
  )
}
