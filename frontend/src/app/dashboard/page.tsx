import { getServerApiToken, serverFetch } from '@/lib/server-auth'
import { DashboardClient } from './DashboardClient'
import type { DashboardData } from '@/hooks/useQueries'

export default async function DashboardPage() {
  // In dev mode, skip SSR data fetch — the client-side query handles auth
  // via dev API key exchange or tenant impersonation (both require browser APIs)
  const isDevMode = process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEV_API_KEY
  let initialData: DashboardData | null = null

  if (!isDevMode) {
    const auth = await getServerApiToken()
    initialData = auth
      ? await serverFetch<DashboardData>('/dashboard?days=30', auth)
      : null
  }

  return <DashboardClient initialData={initialData} />
}
