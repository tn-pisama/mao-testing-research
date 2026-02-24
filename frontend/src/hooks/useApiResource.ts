'use client'

import { useState, useEffect, useRef } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient } from '@/lib/api'

type ApiClient = ReturnType<typeof createApiClient>

/**
 * Generic hook factory for API resources with demo-mode fallback.
 *
 * Eliminates boilerplate across hooks that follow the pattern:
 *   1. Get auth token + tenant
 *   2. Create API client
 *   3. Fetch data (try real API, catch → demo fallback)
 *   4. Track isLoading + isDemoMode state
 *
 * @param fetcher  Async function that calls the API client and returns data
 * @param fallback Sync function that returns demo/fallback data
 * @param deps     Dependency array for re-fetching (like useEffect deps)
 */
export function useApiResource<T>(
  fetcher: (api: ApiClient) => Promise<T>,
  fallback: () => T,
  deps: any[] = [],
): { data: T | null; isLoading: boolean; isDemoMode: boolean } {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [data, setData] = useState<T | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)
  const isMountedRef = useRef(true)

  useEffect(() => {
    isMountedRef.current = true

    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token, tenantId)
        const result = await fetcher(api)
        if (isMountedRef.current) {
          setData(result)
          setIsDemoMode(false)
        }
      } catch {
        if (isMountedRef.current) {
          setData(fallback())
          setIsDemoMode(true)
        }
      }
      if (isMountedRef.current) {
        setIsLoading(false)
      }
    }

    load()

    return () => {
      isMountedRef.current = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken, tenantId, ...deps])

  return { data, isLoading, isDemoMode }
}
