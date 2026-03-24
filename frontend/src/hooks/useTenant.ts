'use client'

import { useSession } from 'next-auth/react'
import { useEffect, useState } from 'react'
import { getCachedTenantId } from './useSafeAuth'

import API_URL from '@/lib/api-url'

const API_BASE = API_URL

/** Read the last-used tenant synchronously for instant cache key matching. */
function getInitialTenant(): string {
  if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEV_TENANT_ID) {
    return process.env.NEXT_PUBLIC_DEV_TENANT_ID
  }
  if (typeof window === 'undefined') return 'default'
  try {
    return localStorage.getItem('pisama_last_tenant') || 'default'
  } catch {
    return 'default'
  }
}

/** Persist tenant to both the quick-access key and per-email key. */
function persistTenant(tenantId: string, email?: string): void {
  try {
    localStorage.setItem('pisama_last_tenant', tenantId)
    if (email) {
      localStorage.setItem(`pisama_tenant_${email}`, tenantId)
    }
  } catch {}
}

/**
 * Hook to get the current tenant ID.
 *
 * Resolution order (synchronous first for instant cache key matching):
 * 1. localStorage pisama_last_tenant (synchronous, in useState initializer)
 * 2. In-memory cache from token exchange (in useEffect)
 * 3. Per-email localStorage (in useEffect)
 * 4. Backend /auth/tenant-by-email (final fallback)
 */
export function useTenant() {
  const { data: session, status } = useSession()
  const email = session?.user?.email

  const [tenantId, setTenantId] = useState<string>(getInitialTenant)
  const [isLoading, setIsLoading] = useState<boolean>(() => {
    // If we got a real tenant from localStorage, we're already loaded
    return getInitialTenant() === 'default'
  })

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

    // Always fetch tenant from backend — session/cache can be stale after tenant changes
    // Skip straight to per-email localStorage check, then backend fetch

    // 1. Check per-email localStorage (quick, usually correct)
    try {
      const stored = localStorage.getItem(`pisama_tenant_${email}`)
      if (stored) {
        setTenantId(stored)
        setIsLoading(false)
        persistTenant(stored)
        return
      }
    } catch {}

    // 3. Fall back to backend fetch
    let cancelled = false

    async function fetchTenant() {
      try {
        const response = await fetch(
          `${API_BASE}/auth/tenant-by-email?email=${encodeURIComponent(email!)}`
        )
        if (!cancelled && response.ok) {
          const data = await response.json()
          const id = data.tenant_id || 'default'
          setTenantId(id)
          if (id !== 'default') {
            persistTenant(id, email!)
          }
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
    isLoaded: isDevMode || !isLoading,
    isDefaultTenant: tenantId === 'default',
  }
}
