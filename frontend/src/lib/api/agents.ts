import { fetchApi } from './client'
import type { FetchOptions } from './client'
import type { AgentInfo } from '@/components/agents'

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createAgentsApi(opts: FetchOptions) {
  return {
    async listAgents() {
      return fetchApi<{ agents: AgentInfo[]; total: number }>(
        `/tenants/{tenant_id}/agents`,
        opts
      )
    },
  }
}
