'use client'

import { useSession } from 'next-auth/react'
import { useEffect, useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

/**
 * Hook to get the current tenant ID from the backend.
 *
 * Calls the backend tenant-by-email endpoint directly using the
 * session email (avoids the Next.js API route middleman that was
 * failing due to expired ID tokens and backend cold starts).
 */
export function useTenant() {
  const { data: session, status } = useSession()
  const [tenantId, setTenantId] = useState<string>(() => {
    if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEV_TENANT_ID) {
      return process.env.NEXT_PUBLIC_DEV_TENANT_ID
    }
    return 'default'
  })
  const [isLoading, setIsLoading] = useState(true)

  const email = session?.user?.email

  useEffect(() => {
    // Dev tenant override — skip fetch
    if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEV_TENANT_ID) {
      setIsLoading(false)
      return
    }

    if (status === 'loading') return

    if (status === 'unauthenticated' || !email) {
      setTenantId('default')
      setIsLoading(false)
      return
    }

    let cancelled = false

    async function fetchTenant() {
      try {
        const response = await fetch(
          `${API_BASE}/auth/tenant-by-email?email=${encodeURIComponent(email!)}`
        )
        if (!cancelled && response.ok) {
          const data = await response.json()
          setTenantId(data.tenant_id || 'default')
        } else if (!cancelled) {
          setTenantId('default')
        }
      } catch (error) {
        console.error('Failed to fetch tenant:', error)
        if (!cancelled) setTenantId('default')
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    fetchTenant()
    return () => { cancelled = true }
  }, [email, status])

  const isDevMode = process.env.NODE_ENV === 'development' && !!process.env.NEXT_PUBLIC_DEV_TENANT_ID

  return {
    tenantId,
    isLoaded: isDevMode || (status !== 'loading' && !isLoading),
    isDefaultTenant: tenantId === 'default',
  }
}
