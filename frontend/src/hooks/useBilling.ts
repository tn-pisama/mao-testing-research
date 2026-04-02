'use client'

import { useQuery, useMutation } from '@tanstack/react-query'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'

// ---------------------------------------------------------------------------
// Types — aligned with backend billing schemas
// ---------------------------------------------------------------------------

export interface BillingPlan {
  name: string           // PlanTier enum: "free", "pro", "team", "enterprise"
  slug: string           // Same as name value
  display_name: string
  price_monthly: number | null
  price_annual_monthly: number | null
  project_limit: number | null
  retention_days: number | null
  team_limit: number | null
  daily_run_limit: number | null
  alerts_per_day: number | null
  features: string[]
  stripe_price_id_monthly: string | null
  stripe_price_id_annual: string | null
}

export interface BillingStatus {
  plan: string
  plan_id: string
  plan_name: string
  status: string
  current_period_end: string | null
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

  return useMutation<CheckoutResponse, Error, { plan: string; annual?: boolean }>({
    mutationFn: async ({ plan, annual = false }) => {
      const headers = await getHeaders()
      const { default: API_BASE } = await import('@/lib/api-url')
      const res = await fetch(`${API_BASE}/billing/checkout`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({ plan, annual }),
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
