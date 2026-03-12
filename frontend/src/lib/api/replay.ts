import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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
  details: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createReplayApi(opts: FetchOptions) {
  return {
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

    async compareReplay(bundleId: string, newTraceData: Record<string, unknown>) {
      return fetchApi<{ bundle_id: string; overall_similarity: number; total_steps: number; matching_steps: number; diffs: ReplayDiff[] }>(
        `/tenants/{tenant_id}/replay/bundles/${bundleId}/compare`,
        { ...opts, method: 'POST', body: { bundle_id: bundleId, new_trace_data: newTraceData } }
      )
    },
  }
}
