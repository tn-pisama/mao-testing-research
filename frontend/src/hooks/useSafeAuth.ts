'use client'

import { useSession, signOut as nextAuthSignOut } from 'next-auth/react'
import { useCallback, useMemo } from 'react'

// Global cache for backend JWT (shared across all component instances)
let cachedBackendToken: string | null = null
let backendTokenExpiresAt: number | null = null
let exchangePromise: Promise<string | null> | null = null

/**
 * Exchange the Google ID token for a long-lived backend JWT.
 * Uses a singleton promise to prevent duplicate exchanges.
 */
async function exchangeToken(): Promise<string | null> {
  try {
    const res = await fetch('/api/auth/exchange-token', { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      cachedBackendToken = data.access_token
      // Cache for 23 hours (backend JWT expires in 24h)
      backendTokenExpiresAt = Date.now() + 23 * 60 * 60 * 1000
      return data.access_token
    }
    console.warn('[auth] Token exchange failed:', res.status)
    return null
  } catch (err) {
    console.warn('[auth] Token exchange error:', err)
    return null
  } finally {
    exchangePromise = null
  }
}

/**
 * Wrapper around NextAuth's useSession hook.
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
      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'
      try {
        const response = await fetch(`${API_BASE}/auth/token`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: process.env.NEXT_PUBLIC_DEV_API_KEY })
        })
        if (response.ok) {
          const data = await response.json()
          cachedBackendToken = data.access_token
          backendTokenExpiresAt = now + 23 * 60 * 60 * 1000
          return data.access_token
        }
      } catch (error) {
        console.error('Error exchanging API key:', error)
      }
      if (cachedBackendToken) return cachedBackendToken
      return idToken
    }

    // Production: exchange Google ID token for backend JWT
    if (!idToken) return null

    // Return cached backend JWT if still valid
    const now = Date.now()
    if (cachedBackendToken && backendTokenExpiresAt && backendTokenExpiresAt > now) {
      return cachedBackendToken
    }

    // Exchange token (deduplicate concurrent calls)
    if (!exchangePromise) {
      exchangePromise = exchangeToken()
    }
    const backendToken = await exchangePromise

    // If exchange succeeded, use backend JWT; otherwise fall back to Google token
    return backendToken || idToken
  }, [idToken])

  const signOut = useCallback(async () => {
    cachedBackendToken = null
    backendTokenExpiresAt = null
    exchangePromise = null
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
