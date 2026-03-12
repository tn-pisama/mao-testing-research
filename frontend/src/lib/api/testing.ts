import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

export interface AssertionResult {
  assertion_type: string
  passed: boolean
  message: string
  details: Record<string, unknown>
}

export interface GeneratedTestSuite {
  name: string
  test_count: number
  tests: Array<{
    id: string
    name: string
    type: string
    description: string
  }>
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createTestingApi(opts: FetchOptions) {
  return {
    async getAccuracyMetrics(days: number = 30) {
      return fetchApi<AccuracyMetric[]>(`/tenants/{tenant_id}/testing/accuracy?days=${days}`, opts)
    },

    async getIntegrationStatus() {
      return fetchApi<IntegrationStatus[]>(`/tenants/{tenant_id}/testing/integrations`, opts)
    },

    async getHandoffs(limit: number = 10) {
      return fetchApi<Handoff[]>(`/tenants/{tenant_id}/testing/handoffs?limit=${limit}`, opts)
    },

    async analyzeHandoffs(traceData: Record<string, unknown>) {
      return fetchApi<HandoffAnalysis>(`/tenants/{tenant_id}/testing/analyze`, {
        ...opts,
        method: 'POST',
        body: { trace_data: traceData, include_graph: true },
      })
    },

    async runAssertions(traceData: Record<string, unknown>) {
      return fetchApi<AssertionResult[]>(`/tenants/{tenant_id}/testing/assertions`, {
        ...opts,
        method: 'POST',
        body: { trace_data: traceData },
      })
    },

    async generateTests(traceData: Record<string, unknown>, testTypes: string[] = ['handoff', 'context', 'sla']) {
      return fetchApi<GeneratedTestSuite>(`/tenants/{tenant_id}/testing/generate`, {
        ...opts,
        method: 'POST',
        body: { trace_data: traceData, test_types: testTypes },
      })
    },
  }
}
