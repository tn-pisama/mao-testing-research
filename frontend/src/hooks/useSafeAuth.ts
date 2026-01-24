'use client'

import { useSession, signOut as nextAuthSignOut } from 'next-auth/react'

/**
 * Wrapper around NextAuth's useSession hook for compatibility.
 *
 * Provides a consistent API similar to the previous Clerk implementation.
 */
export function useSafeAuth() {
  const { data: session, status } = useSession()

  return {
    isLoaded: status !== 'loading',
    isSignedIn: status === 'authenticated',
    userId: session?.user?.id || null,
    sessionId: session ? 'nextauth-session' : null,
    getToken: async () => {
      // Return the ID token from the session if available
      return (session as any)?.idToken || null
    },
    signOut: async () => {
      await nextAuthSignOut({ callbackUrl: '/' })
    },
    // Legacy compatibility fields (not used with Google OAuth)
    orgId: null,
    orgRole: null,
    orgSlug: null,
  }
}
