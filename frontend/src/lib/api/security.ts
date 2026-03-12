import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface InjectionCheckResult {
  detected: boolean
  confidence: number
  attack_type?: string
  severity: string
  matched_patterns: string[]
  details: Record<string, unknown>
}

export interface HallucinationCheckResult {
  detected: boolean
  confidence: number
  hallucination_type?: string
  grounding_score: number
  evidence: string[]
  details: Record<string, unknown>
}

export interface OverflowCheckResult {
  severity: string
  current_tokens: number
  context_window: number
  usage_percent: number
  remaining_tokens: number
  estimated_overflow_in?: number
  warnings: string[]
  suggestions: string[]
  details: Record<string, unknown>
}

export interface CostCalculation {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  input_cost_usd: number
  output_cost_usd: number
  total_cost_usd: number
  total_cost_cents: number
  model: string
  provider: string
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createSecurityApi(opts: FetchOptions) {
  return {
    async checkInjection(text: string, context?: string, isUserInput: boolean = true) {
      return fetchApi<InjectionCheckResult>(`/tenants/{tenant_id}/security/injection/check`, {
        ...opts,
        method: 'POST',
        body: { text, context, is_user_input: isUserInput },
      })
    },

    async checkHallucination(
      output: string,
      sources?: string[],
      context?: string,
      toolResults?: Record<string, unknown>[]
    ) {
      return fetchApi<HallucinationCheckResult>(`/tenants/{tenant_id}/security/hallucination/check`, {
        ...opts,
        method: 'POST',
        body: { output, sources, context, tool_results: toolResults },
      })
    },

    async checkOverflow(
      currentTokens: number,
      model: string,
      messages?: Record<string, unknown>[],
      expectedOutputTokens: number = 4096
    ) {
      return fetchApi<OverflowCheckResult>(`/tenants/{tenant_id}/security/overflow/check`, {
        ...opts,
        method: 'POST',
        body: { current_tokens: currentTokens, model, messages, expected_output_tokens: expectedOutputTokens },
      })
    },

    async calculateCost(model: string, inputTokens: number, outputTokens: number) {
      return fetchApi<CostCalculation>(`/tenants/{tenant_id}/security/cost/calculate`, {
        ...opts,
        method: 'POST',
        body: { model, input_tokens: inputTokens, output_tokens: outputTokens },
      })
    },

    async listSecurityModels() {
      return fetchApi<Record<string, { input_per_1m: number; output_per_1m: number; context_window: number; provider: string }>>(
        `/tenants/{tenant_id}/security/models`,
        opts
      )
    },
  }
}
