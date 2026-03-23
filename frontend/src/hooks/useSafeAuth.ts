'use client'

import { useSession, signOut as nextAuthSignOut } from 'next-auth/react'
import { useCallback, useMemo } from 'react'

const TOKEN_STORAGE_KEY = 'pisama_backend_token'

// Global cache for backend JWT (shared across all component instances)
let cachedBackendToken: string | null = null
let backendTokenExpiresAt: number | null = null
let exchangePromise: Promise<string | null> | null = null
let cachedTenantId: string | null = null

// Rehydrate from sessionStorage on module init (client only)
if (typeof window !== 'undefined') {
  try {
    const stored = sessionStorage.getItem(TOKEN_STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      if (parsed.expiresAt > Date.now()) {
        cachedBackendToken = parsed.token
        backendTokenExpiresAt = parsed.expiresAt
        if (parsed.tenantId) cachedTenantId = parsed.tenantId
      } else {
        sessionStorage.removeItem(TOKEN_STORAGE_KEY)
      }
    }
  } catch {
    // Corrupted data, ignore
  }
}

/** Return the tenant_id obtained during token exchange, or null. */
export function getCachedTenantId(): string | null {
  return cachedTenantId
}

/** Clear the cached tenant ID (call on sign-out). */
export function clearCachedTenantId(): void {
  cachedTenantId = null
}

/** Clear ALL client-side caches. Must be called from every sign-out path. */
export function clearAllCaches(): void {
  cachedBackendToken = null
  backendTokenExpiresAt = null
  exchangePromise = null
  cachedTenantId = null
  if (typeof window !== 'undefined') {
    try {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY)
      localStorage.removeItem('pisama_last_tenant')
      localStorage.removeItem('pisama_query_cache')
      const keys = Object.keys(localStorage)
      for (const key of keys) {
        if (key.startsWith('pisama_tenant_')) {
          localStorage.removeItem(key)
        }
      }
    } catch {}
  }
}

function persistToken(token: string, expiresAt: number, tenantId?: string): void {
  if (typeof window === 'undefined') return
  try {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify({
      token,
      expiresAt,
      tenantId: tenantId || null,
    }))
  } catch {}
}

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
      if (data.tenant_id) cachedTenantId = data.tenant_id
      // Cache for 23 hours (backend JWT expires in 24h)
      backendTokenExpiresAt = Date.now() + 23 * 60 * 60 * 1000
      persistToken(data.access_token, backendTokenExpiresAt, data.tenant_id)
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

  const extendedSession = session as (typeof session & {
    idToken?: string
    accessToken?: string
    tenantId?: string
    user?: { id?: string }
  }) | null

  const idToken = useMemo(() => {
    return extendedSession?.idToken || null
  }, [extendedSession?.idToken])

  // If NextAuth JWT callback already exchanged the token, cache it
  // But don't blindly set a fresh TTL — the token might already be expired
  const sessionAccessToken = extendedSession?.accessToken
  const sessionTenantId = extendedSession?.tenantId
  if (sessionAccessToken && !cachedBackendToken) {
    cachedBackendToken = sessionAccessToken
    if (sessionTenantId) cachedTenantId = sessionTenantId
    // Don't assume the token is fresh — set a short TTL so getToken() verifies quickly
    // If the token works, the API call succeeds. If not, the refresh path kicks in.
    backendTokenExpiresAt = Date.now() + 5 * 60 * 1000 // 5 min check
    persistToken(sessionAccessToken, backendTokenExpiresAt, sessionTenantId)
  }

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
          persistToken(data.access_token, backendTokenExpiresAt)
          return data.access_token
        }
      } catch (error) {
        console.error('Error exchanging API key:', error)
      }
      if (cachedBackendToken) return cachedBackendToken
      return idToken
    }

    // Return cached backend JWT if still valid (even before NextAuth session loads)
    const now = Date.now()
    if (cachedBackendToken && backendTokenExpiresAt && backendTokenExpiresAt > now) {
      return cachedBackendToken
    }

    // Try refreshing an expired backend token first (works even if Google ID token expired)
    if (cachedBackendToken) {
      try {
        const refreshRes = await fetch('/api/auth/refresh-token', { method: 'POST' })
        if (refreshRes.ok) {
          const data = await refreshRes.json()
          cachedBackendToken = data.access_token
          if (data.tenant_id) cachedTenantId = data.tenant_id
          backendTokenExpiresAt = Date.now() + 23 * 60 * 60 * 1000
          persistToken(data.access_token, backendTokenExpiresAt, data.tenant_id)
          return data.access_token
        }
      } catch {}
    }

    // Production: exchange Google ID token for backend JWT
    if (!idToken) return null

    // Exchange token (deduplicate concurrent calls)
    if (!exchangePromise) {
      exchangePromise = exchangeToken()
    }
    const backendToken = await exchangePromise

    // If exchange succeeded, use backend JWT; otherwise fall back to Google token
    return backendToken || idToken
  }, [idToken])

  const signOut = useCallback(async () => {
    clearAllCaches()
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
