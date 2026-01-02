'use client'

import { useUser } from '@clerk/nextjs'

/**
 * Hook to get the current tenant ID from Clerk user metadata.
 *
 * Tenant ID is stored in user.publicMetadata.tenantId
 * Falls back to 'default' if not set (for backwards compatibility).
 */
export function useTenant() {
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
