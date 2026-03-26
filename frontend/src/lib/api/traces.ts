import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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
  state_delta: Record<string, unknown>
  state_hash: string
  token_count: number
  latency_ms: number
  created_at: string
  // Claude Code specific fields (in metadata)
  metadata?: {
    user_input?: string
    reasoning?: string
    ai_output?: string
    model?: string
    input_tokens?: number
    output_tokens?: number
    cache_read_tokens?: number
    cost_usd?: number
    trace_type?: string
    skill_name?: string
    working_dir?: string
  }
}

export interface TraceListResponse {
  traces: Trace[]
  total: number
  page: number
  per_page: number
}

// Orchestration Quality types
export interface OrchestrationQualityResponse {
  overall: number
  topology: string
  dimensions: Record<string, number>
  issues: string[]
  agent_stats: Record<string, { state_count: number; total_latency_ms: number; errors: number; role: string }>
  critical_path: string[]
  mode: string
}

// Chain Analysis types
export interface ChainAnalysisIssue {
  issue_type: string
  description: string
  severity: string
  affected_traces: string[]
}

export interface ChainAnalysisResponse {
  detected: boolean
  confidence: number
  issues: ChainAnalysisIssue[]
  trace_count: number
  root_traces: string[]
  explanation: string
}

// ---------------------------------------------------------------------------
// API methods (bound into the client factory)
// ---------------------------------------------------------------------------

export function createTracesApi(opts: FetchOptions) {
  return {
    async getTraces(params: { page?: number; perPage?: number; status?: string }) {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.perPage) query.set('per_page', String(params.perPage))
      if (params.status) query.set('status_filter', params.status)

      return fetchApi<TraceListResponse>(
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
      return fetchApi<unknown>(`/tenants/{tenant_id}/traces/${traceId}/analyze`, { ...opts, method: 'POST' })
    },

    async getOrchestrationQuality(traceId: string) {
      return fetchApi<OrchestrationQualityResponse>(
        `/tenants/{tenant_id}/traces/${traceId}/orchestration-quality`,
        opts
      )
    },

    async getChainAnalysis(traceId: string) {
      return fetchApi<ChainAnalysisResponse>(
        `/tenants/{tenant_id}/traces/${traceId}/chain-analysis`,
        opts
      )
    },
  }
}
