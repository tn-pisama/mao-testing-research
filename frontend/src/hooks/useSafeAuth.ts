'use client'

import { useSession, signOut as nextAuthSignOut } from 'next-auth/react'
import { useCallback, useMemo, useRef } from 'react'

/**
 * Wrapper around NextAuth's useSession hook for compatibility.
 *
 * Provides a consistent API similar to the previous Clerk implementation.
 */
export function useSafeAuth() {
  const { data: session, status } = useSession()
  const devTokenRef = useRef<string | null>(null)

  // Type assertion for extended session
  const extendedSession = session as any

  // Memoize the extracted ID token to prevent unnecessary re-renders
  // Only changes when the actual token value changes, not when session object reference changes
  const idToken = useMemo(() => {
    return extendedSession?.idToken || null
  }, [extendedSession?.idToken])

  // Memoize getToken to prevent infinite re-renders in dependent hooks
  const getToken = useCallback(async () => {
    // Development mode: use API key if available
    if (process.env.NODE_ENV === 'development' && process.env.NEXT_PUBLIC_DEV_API_KEY) {
      // Return cached token if available
      if (devTokenRef.current) {
        return devTokenRef.current
      }

      // Exchange API key for JWT
      try {
        const response = await fetch('http://localhost:8000/api/v1/auth/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: process.env.NEXT_PUBLIC_DEV_API_KEY })
        })

        if (!response.ok) {
          console.error('Failed to exchange API key for token:', response.status)
          return idToken // Fall back to NextAuth token
        }

        const data = await response.json()
        devTokenRef.current = data.access_token
        return data.access_token
      } catch (error) {
        console.error('Error exchanging API key:', error)
        return idToken // Fall back to NextAuth token
      }
    }

    // Production: use NextAuth session token
    return idToken
  }, [idToken])

  // Memoize signOut to prevent unnecessary re-renders
  const signOut = useCallback(async () => {
    await nextAuthSignOut({ callbackUrl: '/' })
  }, [])

  // In development with dev API key, mark as signed in
  const isDevMode = process.env.NODE_ENV === 'development' && !!process.env.NEXT_PUBLIC_DEV_API_KEY

  return {
    isLoaded: status !== 'loading' || isDevMode,
    isSignedIn: status === 'authenticated' || isDevMode,
    userId: extendedSession?.user?.id || (isDevMode ? 'dev-user' : null),
    sessionId: session ? 'nextauth-session' : (isDevMode ? 'dev-session' : null),
    getToken,
    signOut,
    // Legacy compatibility fields (not used with Google OAuth)
    orgId: null,
    orgRole: null,
    orgSlug: null,
  }
}
