'use client'

import { useSession, signOut as nextAuthSignOut } from 'next-auth/react'
import { useCallback, useMemo } from 'react'

// Global cache for backend token (shared across all component instances)
let cachedBackendToken: string | null = null
let backendTokenExpiresAt: number | null = null

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://mao-api.fly.dev/api/v1'

/**
 * Wrapper around NextAuth's useSession hook for compatibility.
 */
export function useSafeAuth() {
  const { data: session, status } = useSession()

  const extendedSession = session as (typeof session & { idToken?: string; user?: { id?: string } }) | null

  const idToken = useMemo(() => {
    return extendedSession?.idToken || null
  }, [extendedSession?.idToken])

  const getToken = useCallback(async () => {
    // Development mode: use API key
    if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEV_API_KEY) {
      const now = Date.now()
      if (cachedBackendToken && backendTokenExpiresAt && backendTokenExpiresAt > now) {
        return cachedBackendToken
      }

      try {
        const response = await fetch(`${API_BASE}/auth/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: process.env.NEXT_PUBLIC_DEV_API_KEY })
        })

        if (response.ok) {
          const data = await response.json()
          cachedBackendToken = data.access_token
          backendTokenExpiresAt = now + (23 * 60 * 60 * 1000)
          return data.access_token
        }
      } catch (error) {
        console.error('Error exchanging API key:', error)
      }

      if (cachedBackendToken) return cachedBackendToken
      return idToken
    }

    // Production: return the Google ID token directly
    // The backend accepts Google ID tokens via get_current_user_or_tenant
    return idToken
  }, [idToken])

  const signOut = useCallback(async () => {
    cachedBackendToken = null
    backendTokenExpiresAt = null
    await nextAuthSignOut({ callbackUrl: '/' })
  }, [])

  const isDevMode = process.env.NODE_ENV === 'development' && !!process.env.NEXT_PUBLIC_DEV_API_KEY

  return {
    isLoaded: status !== 'loading' || isDevMode,
    isSignedIn: status === 'authenticated' || isDevMode,
    userId: extendedSession?.user?.id || (isDevMode ? 'dev-user' : null),
    sessionId: session ? 'nextauth-session' : (isDevMode ? 'dev-session' : null),
    getToken,
    signOut,
    orgId: null,
    orgRole: null,
    orgSlug: null,
  }
}
