const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

interface FetchOptions {
  method?: string
  body?: any
  headers?: Record<string, string>
  token?: string | null
  tenantId?: string | null
}

async function fetchApi<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { token, tenantId } = options
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const url = endpoint.includes('{tenant_id}') && tenantId
    ? `${API_BASE}${endpoint.replace('{tenant_id}', tenantId)}`
    : `${API_BASE}${endpoint}`

  const response = await fetch(url, {
    method: options.method || 'GET',
    headers,
    credentials: 'include',
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`)
  }

  return response.json()
}

export interface Trace {
  id: string
  session_id: string
  framework: string
  status: string
  total_tokens: number
  total_cost_cents: number
  created_at: string
  completed_at?: string
  state_count: number
  detection_count: number
}

export interface State {
  id: string
  sequence_num: number
  agent_id: string
  state_delta: Record<string, any>
  state_hash: string
  token_count: number
  latency_ms: number
  created_at: string
}

export interface Detection {
  id: string
  trace_id: string
  state_id?: string
  detection_type: string
  confidence: number
  method: string
  details: Record<string, any>
  validated: boolean
  false_positive?: boolean
  created_at: string
}

export interface LoopAnalytics {
  total_loops_detected: number
  loops_by_method: Record<string, number>
  avg_loop_length: number
  top_agents_in_loops: Array<{ agent_id: string; count: number }>
  time_series: Array<{ date: string; count: number }>
}

export interface CostAnalytics {
  total_cost_cents: number
  total_tokens: number
  cost_by_framework: Record<string, number>
  cost_by_day: Array<{ date: string; cost_cents: number }>
  top_expensive_traces: Array<{
    trace_id: string
    session_id: string
    cost_cents: number
    tokens: number
  }>
}

export function createApiClient(token?: string | null, tenantId?: string | null) {
  const opts = { token, tenantId }
  
  return {
    async getTraces(params: { page?: number; perPage?: number; status?: string }) {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.perPage) query.set('per_page', String(params.perPage))
      if (params.status) query.set('status_filter', params.status)
      
      return fetchApi<{ traces: Trace[]; total: number; page: number; per_page: number }>(
        `/tenants/{tenant_id}/traces?${query}`,
        opts
      )
    },

    async getTrace(id: string) {
      return fetchApi<Trace>(`/tenants/{tenant_id}/traces/${id}`, opts)
    },

    async getTraceStates(traceId: string) {
      return fetchApi<State[]>(`/tenants/{tenant_id}/traces/${traceId}/states`, opts)
    },

    async analyzeTrace(traceId: string) {
      return fetchApi(`/tenants/{tenant_id}/traces/${traceId}/analyze`, { ...opts, method: 'POST' })
    },

    async getDetections(params: { page?: number; perPage?: number; traceId?: string; type?: string }) {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.perPage) query.set('per_page', String(params.perPage))
      if (params.type) query.set('detection_type', params.type)
      
      return fetchApi<Detection[]>(`/tenants/{tenant_id}/detections?${query}`, opts)
    },

    async validateDetection(id: string, falsePositive: boolean, notes?: string) {
      return fetchApi<Detection>(`/tenants/{tenant_id}/detections/${id}/validate`, {
        ...opts,
        method: 'POST',
        body: { false_positive: falsePositive, notes },
      })
    },

    async getLoopAnalytics(days: number = 30) {
      return fetchApi<LoopAnalytics>(`/tenants/{tenant_id}/analytics/loops?days=${days}`, opts)
    },

    async getCostAnalytics(days: number = 30) {
      return fetchApi<CostAnalytics>(`/tenants/{tenant_id}/analytics/cost?days=${days}`, opts)
    },
  }
}

export const api = createApiClient()
