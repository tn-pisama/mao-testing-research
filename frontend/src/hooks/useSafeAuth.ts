'use client'

import { useSession, signOut as nextAuthSignOut } from 'next-auth/react'
import { useCallback, useMemo } from 'react'

/**
 * Wrapper around NextAuth's useSession hook for compatibility.
 *
 * Provides a consistent API similar to the previous Clerk implementation.
 */
export function useSafeAuth() {
  const { data: session, status } = useSession()

  // Type assertion for extended session
  const extendedSession = session as any

  // Memoize the extracted ID token to prevent unnecessary re-renders
  // Only changes when the actual token value changes, not when session object reference changes
  const idToken = useMemo(() => {
    return extendedSession?.idToken || null
  }, [extendedSession?.idToken])

  // Memoize getToken to prevent infinite re-renders in dependent hooks
  const getToken = useCallback(async () => {
    // Return the ID token from the session if available
    return idToken
  }, [idToken])

  // Memoize signOut to prevent unnecessary re-renders
  const signOut = useCallback(async () => {
    await nextAuthSignOut({ callbackUrl: '/' })
  }, [])

  return {
    isLoaded: status !== 'loading',
    isSignedIn: status === 'authenticated',
    userId: extendedSession?.user?.id || null,
    sessionId: session ? 'nextauth-session' : null,
    getToken,
    signOut,
    // Legacy compatibility fields (not used with Google OAuth)
    orgId: null,
    orgRole: null,
    orgSlug: null,
  }
}
