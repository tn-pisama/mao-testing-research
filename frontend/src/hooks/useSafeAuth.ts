'use client'

import { useAuth } from '@clerk/nextjs'

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

/**
 * Safe wrapper around Clerk's useAuth hook.
 *
 * Returns mock values when Clerk is not configured (CI builds, etc.).
 */
export function useSafeAuth() {
  // If Clerk is not configured, return mock auth state
  if (!hasClerk) {
    return {
      isLoaded: true,
      isSignedIn: false,
      userId: null,
      sessionId: null,
      getToken: async () => null,
      signOut: async () => {},
      orgId: null,
      orgRole: null,
      orgSlug: null,
    }
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useAuth()
}
