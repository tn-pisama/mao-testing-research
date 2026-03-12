import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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
  details: Record<string, unknown>
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

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createRegressionApi(opts: FetchOptions) {
  return {
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
