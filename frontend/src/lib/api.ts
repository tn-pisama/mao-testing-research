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

// Testing types
export interface AccuracyMetric {
  detection_type: string
  label: string
  accuracy: number
  trend: string
  change: number
  category: string
}

export interface IntegrationStatus {
  name: string
  version: string
  passed: number
  total: number
}

export interface HandoffAnalysis {
  total_handoffs: number
  successful_handoffs: number
  failed_handoffs: number
  avg_latency_ms: number
  max_latency_ms: number
  context_completeness: number
  data_loss_detected: boolean
  circular_handoffs: string[][]
  agents_involved: string[]
  handoff_graph: Record<string, string[]>
  issues: string[]
}

export interface Handoff {
  id: string
  handoff_type: string
  sender_agent: string
  receiver_agent: string
  timestamp: string
  latency_ms: number
  status: string
  error?: string
  fields_missing: string[]
}

// Replay types
export interface ReplayBundle {
  id: string
  name: string
  trace_id: string
  created_at: string
  event_count: number
  duration_ms: number
  status: string
  models_used: string[]
  tools_used: string[]
  agents_involved: string[]
  total_tokens: number
}

export interface ReplayResult {
  bundle_id: string
  status: string
  started_at: string
  completed_at?: string
  events_replayed: number
  events_total: number
  matches: number
  mismatches: number
  similarity_score: number
}

export interface ReplayDiff {
  step: number
  diff_type: string
  original: string
  replayed: string
  match: boolean
  similarity: number
  details: Record<string, any>
}

// Regression types
export interface Baseline {
  id: string
  name: string
  description: string
  entry_count: number
  model: string
  created_at: string
  updated_at: string
  last_tested?: string
}

export interface DriftAlert {
  id: string
  severity: string
  drift_type: string
  prompt: string
  similarity: number
  detected_at: string
  baseline_id: string
  details: Record<string, any>
}

export interface ModelFingerprint {
  model: string
  version: string
  provider: string
  fingerprint_hash: string
  last_seen: string
  status: string
  change_detected: boolean
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

    // Testing endpoints
    async getAccuracyMetrics(days: number = 30) {
      return fetchApi<AccuracyMetric[]>(`/tenants/{tenant_id}/testing/accuracy?days=${days}`, opts)
    },

    async getIntegrationStatus() {
      return fetchApi<IntegrationStatus[]>(`/tenants/{tenant_id}/testing/integrations`, opts)
    },

    async getHandoffs(limit: number = 10) {
      return fetchApi<Handoff[]>(`/tenants/{tenant_id}/testing/handoffs?limit=${limit}`, opts)
    },

    async analyzeHandoffs(traceData: Record<string, any>) {
      return fetchApi<HandoffAnalysis>(`/tenants/{tenant_id}/testing/analyze`, {
        ...opts,
        method: 'POST',
        body: { trace_data: traceData, include_graph: true },
      })
    },

    // Replay endpoints
    async getReplayBundles(limit: number = 20, offset: number = 0) {
      return fetchApi<ReplayBundle[]>(`/tenants/{tenant_id}/replay/bundles?limit=${limit}&offset=${offset}`, opts)
    },

    async getReplayBundle(bundleId: string) {
      return fetchApi<ReplayBundle>(`/tenants/{tenant_id}/replay/bundles/${bundleId}`, opts)
    },

    async createReplayBundle(traceId: string, name: string) {
      return fetchApi<ReplayBundle>(`/tenants/{tenant_id}/replay/bundles`, {
        ...opts,
        method: 'POST',
        body: { trace_id: traceId, name },
      })
    },

    async startReplay(bundleId: string, mode: string = 'deterministic') {
      return fetchApi<ReplayResult>(`/tenants/{tenant_id}/replay/bundles/${bundleId}/start`, {
        ...opts,
        method: 'POST',
        body: { bundle_id: bundleId, mode },
      })
    },

    async stopReplay(bundleId: string) {
      return fetchApi<ReplayResult>(`/tenants/{tenant_id}/replay/bundles/${bundleId}/stop`, {
        ...opts,
        method: 'POST',
      })
    },

    async getReplayStatus(bundleId: string) {
      return fetchApi<ReplayResult>(`/tenants/{tenant_id}/replay/bundles/${bundleId}/status`, opts)
    },

    async compareReplay(bundleId: string, newTraceData: Record<string, any>) {
      return fetchApi<{ bundle_id: string; overall_similarity: number; total_steps: number; matching_steps: number; diffs: ReplayDiff[] }>(
        `/tenants/{tenant_id}/replay/bundles/${bundleId}/compare`,
        { ...opts, method: 'POST', body: { bundle_id: bundleId, new_trace_data: newTraceData } }
      )
    },

    // Regression endpoints
    async getBaselines(limit: number = 20, offset: number = 0) {
      return fetchApi<Baseline[]>(`/tenants/{tenant_id}/regression/baselines?limit=${limit}&offset=${offset}`, opts)
    },

    async getBaseline(baselineId: string) {
      return fetchApi<Baseline>(`/tenants/{tenant_id}/regression/baselines/${baselineId}`, opts)
    },

    async createBaseline(name: string, description: string, model: string) {
      return fetchApi<Baseline>(`/tenants/{tenant_id}/regression/baselines`, {
        ...opts,
        method: 'POST',
        body: { name, description, model },
      })
    },

    async deleteBaseline(baselineId: string) {
      return fetchApi<void>(`/tenants/{tenant_id}/regression/baselines/${baselineId}`, {
        ...opts,
        method: 'DELETE',
      })
    },

    async testBaseline(baselineId: string, currentOutputs: Array<{ prompt_hash: string; output: string }>) {
      return fetchApi<{ total_alerts: number; critical_count: number; high_count: number; medium_count: number; low_count: number; models_affected: string[]; recent_alerts: DriftAlert[] }>(
        `/tenants/{tenant_id}/regression/baselines/${baselineId}/test`,
        { ...opts, method: 'POST', body: { baseline_id: baselineId, current_outputs: currentOutputs } }
      )
    },

    async getDriftAlerts(severity?: string, limit: number = 20) {
      const query = new URLSearchParams()
      if (severity) query.set('severity', severity)
      query.set('limit', String(limit))
      return fetchApi<DriftAlert[]>(`/tenants/{tenant_id}/regression/alerts?${query}`, opts)
    },

    async getModelFingerprints() {
      return fetchApi<ModelFingerprint[]>(`/tenants/{tenant_id}/regression/fingerprints`, opts)
    },

    async refreshFingerprints() {
      return fetchApi<{ status: string; models_queued: string[]; estimated_time_seconds: number }>(
        `/tenants/{tenant_id}/regression/fingerprints/refresh`,
        { ...opts, method: 'POST' }
      )
    },
  }
}

export const api = createApiClient()
