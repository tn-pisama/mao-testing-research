import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { DashboardClient } from './DashboardClient'

export default async function DashboardPage() {
  const session = await getServerSession(authOptions)
  const token = (session as any)?.accessToken as string | undefined
  const tenantId = (session as any)?.tenantId as string | undefined

  let initialData = null
  if (token && tenantId) {
    try {
      const API = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'
      const url = `${API}/tenants/${tenantId}/dashboard?days=30`
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 5000)
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
        signal: controller.signal,
      })
      clearTimeout(timeout)
      if (res.ok) {
        initialData = await res.json()
      } else {
        console.warn('[dashboard-ssr] API returned', res.status)
      }
    } catch (err) {
      console.warn('[dashboard-ssr] fetch failed:', (err as Error).message)
    }
  } else {
    console.warn('[dashboard-ssr] missing auth:', { hasToken: !!token, hasTenantId: !!tenantId })
  }

  return <DashboardClient initialData={initialData} />
}
