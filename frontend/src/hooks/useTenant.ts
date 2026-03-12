'use client'

import { useSession } from 'next-auth/react'
import { useEffect, useState, useMemo } from 'react'

/**
 * Get initial tenant ID synchronously to prevent race conditions.
 */
function getInitialTenantId(): string {
  if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEV_TENANT_ID) {
    return process.env.NEXT_PUBLIC_DEV_TENANT_ID
  }
  return 'default'
}

/**
 * Hook to get the current tenant ID from the backend.
 *
 * Fetches tenant information based on the authenticated user.
 * Falls back to 'default' if not set or on error.
 */
export function useTenant() {
  const { data: session, status } = useSession()
  const [tenantId, setTenantId] = useState<string>(getInitialTenantId())
  const [isLoading, setIsLoading] = useState(true)

  // Extract the idToken value to prevent re-fetches when session object reference changes
  const sessionIdToken = (session as (typeof session & { idToken?: string }) | null)?.idToken
  const idToken = useMemo(() => {
    return sessionIdToken || null
  }, [sessionIdToken])

  useEffect(() => {
    async function fetchTenant() {
      // Skip if already have dev tenant ID (initialized synchronously)
      if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEV_TENANT_ID) {
        setIsLoading(false)
        return
      }

      if (status === 'loading') {
        return
      }

      if (status === 'unauthenticated') {
        setTenantId('default')
        setIsLoading(false)
        return
      }

      try {
        // Get ID token for backend authentication
        if (!idToken) {
          setTenantId('default')
          setIsLoading(false)
          return
        }

        // Fetch user/tenant info from backend
        const response = await fetch('/api/user/tenant', {
          headers: {
            Authorization: `Bearer ${idToken}`,
          },
        })

        if (response.ok) {
          const data = await response.json()
          setTenantId(data.tenantId || 'default')
        } else {
          setTenantId('default')
        }
      } catch (error) {
        console.error('Failed to fetch tenant:', error)
        setTenantId('default')
      } finally {
        setIsLoading(false)
      }
    }

    fetchTenant()
  }, [idToken, status])

  const isDevMode = process.env.NODE_ENV === 'development' && !!process.env.NEXT_PUBLIC_DEV_TENANT_ID

  return {
    tenantId,
    isLoaded: isDevMode || (status !== 'loading' && !isLoading),
    // Helper to check if using default tenant
    isDefaultTenant: tenantId === 'default',
  }
}
