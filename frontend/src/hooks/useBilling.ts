'use client'

import { useQuery, useMutation } from '@tanstack/react-query'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BillingPlan {
  id: string
  name: string
  slug: string
  price_cents: number
  interval: 'month' | 'year'
  features: string[]
  limits: {
    projects: number
    daily_runs: number
    detectors: number
    retention_days: number
  }
  stripe_price_id: string | null
}

export interface BillingStatus {
  plan_id: string
  plan_name: string
  status: 'active' | 'past_due' | 'canceled' | 'trialing' | 'incomplete'
  current_period_end: string
  cancel_at_period_end: boolean
  usage: {
    projects_used: number
    projects_limit: number
    daily_runs_used: number
    daily_runs_limit: number
  }
}

export interface CheckoutResponse {
  checkout_url: string
  session_id: string
}

export interface PortalResponse {
  portal_url: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function useApiHeaders() {
  const { getToken } = useAuth()
  const { tenantId, isLoaded: tenantLoaded } = useTenant()

  const getHeaders = async () => {
    const token = await getToken()
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`
    return headers
  }

  return { getHeaders, tenantId, tenantLoaded }
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const billingKeys = {
  plans: () => ['billing', 'plans'] as const,
  status: () => ['billing', 'status'] as const,
} as const

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

export function useBillingPlans() {
  const { getHeaders, tenantId, tenantLoaded } = useApiHeaders()

  const query = useQuery<BillingPlan[]>({
    queryKey: [...billingKeys.plans(), tenantId],
    queryFn: async () => {
      const headers = await getHeaders()
      const { default: API_BASE } = await import('@/lib/api-url')
      const res = await fetch(`${API_BASE}/billing/plans`, {
        headers,
        credentials: 'include',
      })
      if (!res.ok) throw new Error(`Billing plans API error: ${res.status}`)
      return res.json()
    },
    enabled: tenantLoaded,
    staleTime: 10 * 60 * 1000,
  })

  return {
    plans: query.data ?? [],
    isLoading: query.isLoading || (query.isPending && !query.data),
    isError: query.isError,
    error: query.error,
  }
}

export function useBillingStatus() {
  const { getHeaders, tenantId, tenantLoaded } = useApiHeaders()

  const query = useQuery<BillingStatus>({
    queryKey: [...billingKeys.status(), tenantId],
    queryFn: async () => {
      const headers = await getHeaders()
      const { default: API_BASE } = await import('@/lib/api-url')
      const res = await fetch(`${API_BASE}/billing/status`, {
        headers,
        credentials: 'include',
      })
      if (!res.ok) throw new Error(`Billing status API error: ${res.status}`)
      return res.json()
    },
    enabled: tenantLoaded,
    staleTime: 60 * 1000,
  })

  return {
    status: query.data ?? null,
    isLoading: query.isLoading || (query.isPending && !query.data),
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  }
}

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

export function useCreateCheckout() {
  const { getHeaders } = useApiHeaders()

  return useMutation<CheckoutResponse, Error, { price_id: string }>({
    mutationFn: async ({ price_id }) => {
      const headers = await getHeaders()
      const { default: API_BASE } = await import('@/lib/api-url')
      const res = await fetch(`${API_BASE}/billing/checkout`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({ price_id }),
      })
      if (!res.ok) throw new Error(`Checkout API error: ${res.status}`)
      return res.json()
    },
  })
}

export function useBillingPortal() {
  const { getHeaders } = useApiHeaders()

  return useMutation<PortalResponse, Error, void>({
    mutationFn: async () => {
      const headers = await getHeaders()
      const { default: API_BASE } = await import('@/lib/api-url')
      const res = await fetch(`${API_BASE}/billing/portal`, {
        headers,
        credentials: 'include',
      })
      if (!res.ok) throw new Error(`Billing portal API error: ${res.status}`)
      return res.json()
    },
  })
}
