'use client'

import { useUser } from '@clerk/nextjs'

const hasClerk = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY

/**
 * Hook to get the current tenant ID from Clerk user metadata.
 *
 * Tenant ID is stored in user.publicMetadata.tenantId
 * Falls back to 'default' if not set (for backwards compatibility).
 *
 * When Clerk is not configured (CI builds, etc.), returns default tenant.
 */
export function useTenant() {
  // If Clerk is not configured, return defaults immediately
  if (!hasClerk) {
    return {
      tenantId: 'default',
      isLoaded: true,
      isDefaultTenant: true,
    }
  }

  // eslint-disable-next-line react-hooks/rules-of-hooks
  const { user, isLoaded } = useUser()

  // Get tenantId from user metadata, fallback to 'default'
  const tenantId = (user?.publicMetadata?.tenantId as string) || 'default'

  return {
    tenantId,
    isLoaded,
    // Helper to check if using default tenant
    isDefaultTenant: tenantId === 'default',
  }
}
