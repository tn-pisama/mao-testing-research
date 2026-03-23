import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'
import { DashboardClient } from './DashboardClient'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'

/** Get a fresh backend JWT via server-to-server auth */
async function getServerToken(email: string): Promise<{ access_token: string; tenant_id: string } | null> {
  const secret = process.env.SERVER_AUTH_SECRET
  if (!secret) return null
  try {
    const res = await fetch(`${API}/auth/server-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-server-secret': secret },
      body: JSON.stringify({ email }),
    })
    if (res.ok) return res.json()
  } catch {}
  return null
}

export default async function DashboardPage() {
  const session = await getServerSession(authOptions)
  let token = (session as any)?.accessToken as string | undefined
  let tenantId = (session as any)?.tenantId as string | undefined
  const email = session?.user?.email

  // Fallback: if no token from session, get one via server-to-server auth
  if ((!token || !tenantId) && email) {
    const serverAuth = await getServerToken(email)
    if (serverAuth) {
      token = serverAuth.access_token
      tenantId = serverAuth.tenant_id
    }
  }

  let initialData = null
  if (token && tenantId) {
    try {
      const res = await fetch(`${API}/tenants/${tenantId}/dashboard?days=30`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: 'no-store',
      })
      if (res.ok) {
        initialData = await res.json()
      } else if (res.status === 401 && email) {
        // Token expired — get fresh one via server-token and retry
        const serverAuth = await getServerToken(email)
        if (serverAuth) {
          const retryRes = await fetch(`${API}/tenants/${serverAuth.tenant_id}/dashboard?days=30`, {
            headers: { Authorization: `Bearer ${serverAuth.access_token}` },
            cache: 'no-store',
          })
          if (retryRes.ok) initialData = await retryRes.json()
        }
      }
    } catch {}
  }

  return <DashboardClient initialData={initialData} />
}
