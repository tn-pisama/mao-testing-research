import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChaosSession {
  id: string
  name: string
  status: string
  created_at: string
  started_at?: string
  completed_at?: string
  experiment_count: number
  target_description: string
}

export interface ChaosExperimentType {
  type: string
  name: string
  description: string
  params: string[]
}

export interface ChaosExperimentConfig {
  experiment_type: string
  name: string
  probability?: number
  min_delay_ms?: number
  max_delay_ms?: number
  error_codes?: number[]
  target_tools?: string[]
  target_agents?: string[]
  failure_mode?: string
  behaviors?: string[]
  truncation_percent?: number
}

export interface ChaosTargetConfig {
  target_type?: string
  agent_names?: string[]
  tool_names?: string[]
  tenant_ids?: string[]
  percentage?: number
  exclude_production?: boolean
}

export interface ChaosSafetyConfig {
  max_blast_radius?: string
  max_affected_requests?: number
  max_duration_seconds?: number
  auto_abort_on_cascade?: boolean
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createChaosApi(opts: FetchOptions) {
  return {
    async getChaosExperimentTypes() {
      return fetchApi<ChaosExperimentType[]>(`/tenants/{tenant_id}/chaos/experiment-types`, opts)
    },

    async listChaosSessions() {
      return fetchApi<ChaosSession[]>(`/tenants/{tenant_id}/chaos/sessions`, opts)
    },

    async getChaosSession(sessionId: string) {
      return fetchApi<Record<string, unknown>>(`/tenants/{tenant_id}/chaos/sessions/${sessionId}`, opts)
    },

    async createChaosSession(
      name: string,
      experiments: ChaosExperimentConfig[],
      target: ChaosTargetConfig,
      safety?: ChaosSafetyConfig
    ) {
      return fetchApi<ChaosSession>(`/tenants/{tenant_id}/chaos/sessions`, {
        ...opts,
        method: 'POST',
        body: { name, experiments, target, safety },
      })
    },

    async startChaosSession(sessionId: string) {
      return fetchApi<{ status: string; session_id: string }>(
        `/tenants/{tenant_id}/chaos/sessions/${sessionId}/start`,
        { ...opts, method: 'POST' }
      )
    },

    async stopChaosSession(sessionId: string) {
      return fetchApi<{ status: string; session_id: string }>(
        `/tenants/{tenant_id}/chaos/sessions/${sessionId}/stop`,
        { ...opts, method: 'POST' }
      )
    },

    async abortChaosSession(sessionId: string, reason: string = 'Manual abort') {
      return fetchApi<{ status: string; session_id: string; reason: string }>(
        `/tenants/{tenant_id}/chaos/sessions/${sessionId}/abort?reason=${encodeURIComponent(reason)}`,
        { ...opts, method: 'POST' }
      )
    },
  }
}
