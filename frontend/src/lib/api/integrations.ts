import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// N8n types
// ---------------------------------------------------------------------------

export interface N8nWorkflow {
  id: string
  workflow_id: string
  workflow_name?: string
  webhook_url: string
  ingestion_mode?: string
  registered_at: string
}

// ---------------------------------------------------------------------------
// OpenClaw types
// ---------------------------------------------------------------------------

export interface OpenClawInstance {
  id: string
  name: string
  gateway_url: string
  otel_enabled: boolean
  is_active: boolean
  channels_configured: string[]
  ingestion_mode: string
  created_at: string
}

export interface OpenClawAgent {
  id: string
  agent_key: string
  agent_name?: string
  model?: string
  monitoring_enabled: boolean
  ingestion_mode?: string
  total_sessions: number
  total_messages: number
  registered_at: string
}

// ---------------------------------------------------------------------------
// Dify types
// ---------------------------------------------------------------------------

export interface DifyInstance {
  id: string
  name: string
  base_url: string
  is_active: boolean
  app_types_configured: string[]
  ingestion_mode: string
  created_at: string
}

export interface DifyApp {
  id: string
  app_id: string
  app_name?: string
  app_type: string
  monitoring_enabled: boolean
  ingestion_mode?: string
  total_runs: number
  total_tokens: number
  registered_at: string
}

// ---------------------------------------------------------------------------
// LangGraph types
// ---------------------------------------------------------------------------

export interface LangGraphDeployment {
  id: string
  name: string
  api_url: string
  is_active: boolean
  deployment_id: string | null
  graph_name: string | null
  ingestion_mode: string
  created_at: string
}

export interface LangGraphAssistant {
  id: string
  deployment_id: string
  assistant_id: string
  graph_id: string
  name: string | null
  monitoring_enabled: boolean
  ingestion_mode: string | null
  total_runs: number
  registered_at: string
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createIntegrationsApi(opts: FetchOptions) {
  return {
    // N8n endpoints
    async registerN8nWorkflow(workflowId: string, workflowName?: string) {
      return fetchApi<N8nWorkflow>(`/n8n/workflows`, {
        ...opts,
        method: 'POST',
        body: { workflow_id: workflowId, workflow_name: workflowName },
      })
    },

    async listN8nWorkflows() {
      return fetchApi<N8nWorkflow[]>(`/n8n/workflows`, opts)
    },

    async syncN8nExecutions(workflowId?: string, limit: number = 20) {
      return fetchApi<{ synced_count: number; traces_created: number; errors: string[] }>(
        `/n8n/sync`,
        {
          ...opts,
          method: 'POST',
          body: { workflow_id: workflowId, limit },
        }
      )
    },

    async discoverWorkflows(connectionId: string) {
      return fetchApi<{
        workflows: Array<{
          id: string
          name: string
          active: boolean
          created_at: string
          updated_at: string
          nodes_count: number
        }>
        connection_name: string
      }>(
        `/n8n/discover`,
        {
          ...opts,
          method: 'POST',
          body: { connection_id: connectionId },
        }
      )
    },

    // OpenClaw endpoints
    async registerOpenClawInstance(data: { name: string; gateway_url: string; api_key: string; otel_endpoint?: string; otel_enabled?: boolean; ingestion_mode?: string }) {
      return fetchApi<OpenClawInstance>(`/openclaw/instances`, {
        ...opts,
        method: 'POST',
        body: data,
      })
    },

    async listOpenClawInstances() {
      return fetchApi<OpenClawInstance[]>(`/openclaw/instances`, opts)
    },

    async registerOpenClawAgent(data: { instance_id: string; agent_key: string; agent_name?: string; model?: string; ingestion_mode?: string }) {
      return fetchApi<OpenClawAgent>(`/openclaw/agents`, {
        ...opts,
        method: 'POST',
        body: data,
      })
    },

    async listOpenClawAgents(instanceId?: string) {
      const params = instanceId ? `?instance_id=${instanceId}` : ''
      return fetchApi<OpenClawAgent[]>(`/openclaw/agents${params}`, opts)
    },

    // Dify endpoints
    async registerDifyInstance(data: { name: string; base_url: string; api_key: string; ingestion_mode?: string }) {
      return fetchApi<DifyInstance>(`/dify/instances`, {
        ...opts,
        method: 'POST',
        body: data,
      })
    },

    async listDifyInstances() {
      return fetchApi<DifyInstance[]>(`/dify/instances`, opts)
    },

    async registerDifyApp(data: { instance_id: string; app_id: string; app_name?: string; app_type?: string; ingestion_mode?: string }) {
      return fetchApi<DifyApp>(`/dify/apps`, {
        ...opts,
        method: 'POST',
        body: data,
      })
    },

    async listDifyApps(instanceId?: string) {
      const params = instanceId ? `?instance_id=${instanceId}` : ''
      return fetchApi<DifyApp[]>(`/dify/apps${params}`, opts)
    },

    // LangGraph endpoints
    async registerLangGraphDeployment(data: { name: string; api_url: string; api_key: string; deployment_id?: string; graph_name?: string; ingestion_mode?: string }) {
      return fetchApi<LangGraphDeployment>(`/langgraph/deployments`, {
        ...opts,
        method: 'POST',
        body: data,
      })
    },

    async listLangGraphDeployments() {
      return fetchApi<LangGraphDeployment[]>(`/langgraph/deployments`, opts)
    },

    async registerLangGraphAssistant(data: { deployment_id: string; assistant_id: string; graph_id: string; name?: string; ingestion_mode?: string }) {
      return fetchApi<LangGraphAssistant>(`/langgraph/assistants`, {
        ...opts,
        method: 'POST',
        body: data,
      })
    },

    async listLangGraphAssistants(deploymentId?: string) {
      const params = deploymentId ? `?deployment_id=${deploymentId}` : ''
      return fetchApi<LangGraphAssistant[]>(`/langgraph/assistants${params}`, opts)
    },
  }
}
