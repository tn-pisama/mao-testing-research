import { getServerApiToken, serverFetch } from '@/lib/server-auth'
import { DashboardClient } from './DashboardClient'
import type { DashboardData } from '@/hooks/useQueries'

export default async function DashboardPage() {
  const auth = await getServerApiToken()
  const initialData = auth
    ? await serverFetch<DashboardData>('/dashboard?days=30', auth)
    : null

  return <DashboardClient initialData={initialData} />
}
