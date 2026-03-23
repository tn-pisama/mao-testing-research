import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'

const API = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'

/** Get a valid API token + tenantId from the server side. */
export async function getServerApiToken(): Promise<{ token: string; tenantId: string; email?: string } | null> {
  const session = await getServerSession(authOptions)
  let token = (session as any)?.accessToken as string | undefined
  let tenantId = (session as any)?.tenantId as string | undefined
  const email = session?.user?.email || undefined

  if ((!token || !tenantId) && email && process.env.SERVER_AUTH_SECRET) {
    try {
      const res = await fetch(`${API}/auth/server-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-server-secret': process.env.SERVER_AUTH_SECRET },
        body: JSON.stringify({ email }),
      })
      if (res.ok) {
        const data = await res.json()
        token = data.access_token
        tenantId = data.tenant_id
      }
    } catch {}
  }

  if (!token || !tenantId) return null
  return { token, tenantId, email }
}

/** Fetch from backend API with automatic 401 retry via server-token. */
export async function serverFetch<T>(path: string, auth: { token: string; tenantId: string; email?: string }): Promise<T | null> {
  const url = `${API}/tenants/${auth.tenantId}${path}`
  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${auth.token}` },
      cache: 'no-store',
    })
    if (res.ok) return res.json()

    if (res.status === 401 && auth.email && process.env.SERVER_AUTH_SECRET) {
      const refreshRes = await fetch(`${API}/auth/server-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-server-secret': process.env.SERVER_AUTH_SECRET },
        body: JSON.stringify({ email: auth.email }),
      })
      if (refreshRes.ok) {
        const { access_token } = await refreshRes.json()
        const retryRes = await fetch(url, {
          headers: { Authorization: `Bearer ${access_token}` },
          cache: 'no-store',
        })
        if (retryRes.ok) return retryRes.json()
      }
    }
  } catch {}
  return null
}
