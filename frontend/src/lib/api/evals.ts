import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface EvalResult {
  overall_score: number
  passed: boolean
  scores: Record<string, number>
  results: Array<Record<string, unknown>>
}

export interface QuickEvalResult {
  relevance: number
  coherence: number
  helpfulness: number
  safety: number
  overall: number
}

export interface LLMJudgeResult {
  score: number
  passed: boolean
  reasoning: string
  confidence: number
  model_used: string
  tokens_used: number
}

// Custom Scorers
export interface CustomScorer {
  id: string
  name: string
  description: string
  prompt_template: string
  scoring_criteria: unknown[]
  scoring_rubric?: string
  model_key: string
  is_active: boolean
  created_at: string
}

export interface ScorerResult {
  id: string
  scorer_id: string
  trace_id: string
  score: number
  confidence: number
  verdict: string
  reasoning: string
  evidence: unknown[]
  suggestions: unknown[]
  cost_usd: number
  created_at: string
}

export interface ScorerRunSummary {
  scorer_id: string
  traces_scored: number
  avg_score: number
  pass_count: number
  warn_count: number
  fail_count: number
  total_cost_usd: number
  results: ScorerResult[]
}

// Conversation Evaluations
export interface ConversationEvaluation {
  id: string
  trace_id: string
  overall_score: number
  overall_grade: string
  dimension_scores: unknown[]
  summary?: string
  turn_annotations: unknown[]
  scoring_method: string
  total_turns: number
  eval_cost_usd: number
  created_at: string
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createEvalsApi(opts: FetchOptions) {
  return {
    async evaluate(
      output: string,
      evalTypes: string[] = ['relevance', 'coherence', 'helpfulness', 'safety'],
      context?: string,
      expected?: string,
      useLlmJudge: boolean = false,
      threshold: number = 0.7
    ) {
      return fetchApi<EvalResult>(`/tenants/{tenant_id}/evals/evaluate`, {
        ...opts,
        method: 'POST',
        body: { output, eval_types: evalTypes, context, expected, use_llm_judge: useLlmJudge, threshold },
      })
    },

    async quickEval(output: string, context?: string) {
      return fetchApi<QuickEvalResult>(`/tenants/{tenant_id}/evals/quick`, {
        ...opts,
        method: 'POST',
        body: { output, context },
      })
    },

    async llmJudgeEval(
      output: string,
      evalType: string = 'relevance',
      model: string = 'gpt-4o-mini',
      context?: string,
      expected?: string
    ) {
      return fetchApi<LLMJudgeResult>(`/tenants/{tenant_id}/evals/llm-judge`, {
        ...opts,
        method: 'POST',
        body: { output, eval_type: evalType, model, context, expected },
      })
    },

    async getEvalTypes() {
      return fetchApi<{ types: string[]; descriptions: Record<string, string> }>(
        `/tenants/{tenant_id}/evals/types`,
        opts
      )
    },

    // Custom Scorers
    async createScorer(description: string, modelKey?: string) {
      return fetchApi<CustomScorer>(`/tenants/{tenant_id}/scorers`, {
        ...opts,
        method: 'POST',
        body: { description, model_key: modelKey },
      })
    },

    async listScorers(activeOnly?: boolean) {
      const query = new URLSearchParams()
      if (activeOnly !== undefined) query.set('active_only', String(activeOnly))
      return fetchApi<CustomScorer[]>(`/tenants/{tenant_id}/scorers?${query}`, opts)
    },

    async runScorer(scorerId: string, params: { latest_n?: number; framework?: string }) {
      return fetchApi<ScorerRunSummary>(`/tenants/{tenant_id}/scorers/${scorerId}/run`, {
        ...opts,
        method: 'POST',
        body: params,
      })
    },

    async updateScorerPrompt(scorerId: string, promptTemplate: string) {
      return fetchApi<CustomScorer>(`/tenants/{tenant_id}/scorers/${scorerId}`, {
        ...opts,
        method: 'PATCH',
        body: { prompt_template: promptTemplate },
      })
    },

    async deleteScorer(scorerId: string) {
      return fetchApi<void>(`/tenants/{tenant_id}/scorers/${scorerId}`, {
        ...opts,
        method: 'DELETE',
      })
    },

    // Conversation Evaluations
    async evaluateConversation(traceId: string, useLlmJudge?: boolean) {
      return fetchApi<ConversationEvaluation>(
        `/tenants/{tenant_id}/conversation-evaluations`,
        {
          ...opts,
          method: 'POST',
          body: { trace_id: traceId, use_llm_judge: useLlmJudge },
        }
      )
    },

    async listConversationEvaluations(params?: { page?: number; per_page?: number; grade?: string }) {
      const query = new URLSearchParams()
      if (params?.page) query.set('page', String(params.page))
      if (params?.per_page) query.set('per_page', String(params.per_page))
      if (params?.grade) query.set('grade', params.grade)
      return fetchApi<{ evaluations: ConversationEvaluation[]; total: number }>(
        `/tenants/{tenant_id}/conversation-evaluations?${query}`,
        opts
      )
    },
  }
}
