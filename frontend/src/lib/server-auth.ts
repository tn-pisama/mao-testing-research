import { getServerSession } from 'next-auth'
import { authOptions } from '@/lib/auth'

import API_URL from '@/lib/api-url'

const API = API_URL

/** Get a valid API token + tenantId from the server side.
 *  ALWAYS uses server-token endpoint to get the freshest tenant from the DB.
 *  Session token is not trusted for tenant ID (can be stale after tenant changes).
 */
export async function getServerApiToken(): Promise<{ token: string; tenantId: string; email?: string } | null> {
  const session = await getServerSession(authOptions)
  const email = session?.user?.email || undefined

  if (email && process.env.SERVER_AUTH_SECRET) {
    try {
      const ctrl = new AbortController()
      const t = setTimeout(() => ctrl.abort(), 3000)
      const res = await fetch(`${API}/auth/server-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-server-secret': process.env.SERVER_AUTH_SECRET },
        body: JSON.stringify({ email }),
        signal: ctrl.signal,
      })
      clearTimeout(t)
      if (res.ok) {
        const data = await res.json()
        return { token: data.access_token, tenantId: data.tenant_id, email }
      }
    } catch {}
  }

  // Fallback to session token if server-token unavailable
  const token = (session as any)?.accessToken as string | undefined
  const tenantId = (session as any)?.tenantId as string | undefined
  if (!token || !tenantId) return null
  return { token, tenantId, email }
}

/** Fetch from backend API with automatic 401 retry via server-token. */
/**
 * Fetch from backend API. Path should start with / and can use {tenant_id} placeholder.
 * If no {tenant_id} in path, /tenants/{tenantId} is prepended automatically.
 */
export async function serverFetch<T>(path: string, auth: { token: string; tenantId: string; email?: string }): Promise<T | null> {
  const fullPath = path.includes('{tenant_id}')
    ? path.replace('{tenant_id}', auth.tenantId)
    : `/tenants/${auth.tenantId}${path}`
  const url = `${API}${fullPath}`
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${auth.token}` },
      cache: 'no-store',
      signal: controller.signal,
    })
    clearTimeout(timeout)
    if (res.ok) return res.json()

    if (res.status === 401 && auth.email && process.env.SERVER_AUTH_SECRET) {
      const ctrl2 = new AbortController()
      const t2 = setTimeout(() => ctrl2.abort(), 3000)
      const refreshRes = await fetch(`${API}/auth/server-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-server-secret': process.env.SERVER_AUTH_SECRET },
        body: JSON.stringify({ email: auth.email }),
        signal: ctrl2.signal,
      })
      clearTimeout(t2)
      if (refreshRes.ok) {
        const { access_token } = await refreshRes.json()
        const ctrl3 = new AbortController()
        const t3 = setTimeout(() => ctrl3.abort(), 5000)
        const retryRes = await fetch(url, {
          headers: { Authorization: `Bearer ${access_token}` },
          cache: 'no-store',
          signal: ctrl3.signal,
        })
        clearTimeout(t3)
        if (retryRes.ok) return retryRes.json()
      }
    }
  } catch {}
  return null
}
