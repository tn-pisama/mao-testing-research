import { fetchApi } from './client'
import type { FetchOptions } from './client'
import type { FixSuggestionSummary } from './detections'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface QualityDimensionScore {
  dimension: string
  score: number
  weight: number
  issues: string[]
  evidence: Record<string, unknown>
  suggestions: string[]
  reasoning?: string
}

export interface AgentQualityScore {
  agent_id: string
  agent_name: string
  agent_type: string
  overall_score: number
  grade: string
  dimensions: QualityDimensionScore[]
  issues_count: number
  critical_issues: string[]
  metadata?: Record<string, unknown>
  reasoning?: string
}

export interface ComplexityMetrics {
  node_count: number
  agent_count: number
  connection_count: number
  max_depth: number
  cyclomatic_complexity: number
  coupling_ratio: number
  ai_node_ratio: number
  parallel_branches: number
  conditional_branches: number
}

export interface OrchestrationQualityScore {
  workflow_id: string
  workflow_name: string
  overall_score: number
  grade: string
  dimensions: QualityDimensionScore[]
  complexity_metrics: ComplexityMetrics
  issues_count: number
  critical_issues: string[]
  detected_pattern: string
  reasoning?: string
}

export interface QualityImprovement {
  id: string
  target_type: 'agent' | 'orchestration'
  target_id: string
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
  category: string
  title: string
  description: string
  rationale: string
  suggested_change?: string
  code_example?: string
  estimated_impact: string
  effort: 'low' | 'medium' | 'high'
}

export interface QualityAssessment {
  id: string
  workflow_id: string
  workflow_name: string
  trace_id?: string
  overall_score: number
  overall_grade: string
  agent_quality_score: number
  orchestration_quality_score: number
  agent_scores: AgentQualityScore[]
  orchestration_score: OrchestrationQualityScore
  improvements: QualityImprovement[]
  complexity_metrics?: ComplexityMetrics
  total_issues: number
  critical_issues_count: number
  source: string
  assessment_time_ms?: number
  summary?: string
  reasoning?: string
  key_findings?: string[]
  created_at: string
  assessed_at: string
}

export interface QualityAssessmentListResponse {
  assessments: QualityAssessment[]
  total: number
  page: number
  page_size: number
}

export interface QualityDimensionInfo {
  name: string
  description: string
  weight: number
  checks: string[]
}

export interface QualityDimensionsResponse {
  agent_dimensions: QualityDimensionInfo[]
  orchestration_dimensions: QualityDimensionInfo[]
}

// Quality Healing Types
export interface QualityHealingRecord {
  id: string
  assessment_id?: string
  status: string
  before_score: number
  after_score: number | null
  dimensions_targeted: string[]
  fix_suggestions_count: number
  fix_suggestions?: FixSuggestionSummary[]
  applied_fixes: unknown[]
  validation_results: unknown[]
  validation_status?: string | null
  rollback_available?: boolean
  is_successful: boolean
  score_improvement: number | null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata: Record<string, any>
}

export interface QualityHealingListResponse {
  items: QualityHealingRecord[]
  total: number
}

export interface QualityHealingTriggerResponse {
  healing_id: string
  status: string
  message: string
  fix_suggestions: FixSuggestionSummary[]
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createQualityApi(opts: FetchOptions) {
  return {
    // Quality Assessment endpoints
    async listQualityAssessments(params: {
      page?: number
      pageSize?: number
      workflowId?: string
      minGrade?: string
      groupId?: string
    } = {}) {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.pageSize) query.set('page_size', String(params.pageSize))
      if (params.workflowId) query.set('workflow_id', params.workflowId)
      if (params.minGrade) query.set('min_grade', params.minGrade)
      if (params.groupId) query.set('group_id', params.groupId)

      return fetchApi<QualityAssessmentListResponse>(
        `/enterprise/quality/tenants/{tenant_id}/assessments?${query}`,
        opts
      )
    },

    async getQualityAssessment(assessmentId: string) {
      return fetchApi<QualityAssessment>(
        `/enterprise/quality/tenants/{tenant_id}/assessments/${assessmentId}?include_reasoning=true`,
        opts
      )
    },

    async getQualityByTrace(traceId: string) {
      return fetchApi<QualityAssessment>(
        `/enterprise/quality/tenants/{tenant_id}/assessments/by-trace/${traceId}?include_reasoning=true`,
        opts
      )
    },

    async getQualityDimensions() {
      return fetchApi<QualityDimensionsResponse>(
        `/enterprise/quality/dimensions`,
        opts
      )
    },

    async assessWorkflowQuality(workflow: Record<string, unknown>, maxSuggestions: number = 10) {
      return fetchApi<QualityAssessment>(`/enterprise/quality/workflow`, {
        ...opts,
        method: 'POST',
        body: { workflow, max_suggestions: maxSuggestions },
      })
    },

    async assessAndSaveQuality(
      workflow: Record<string, unknown>,
      traceId?: string,
      maxSuggestions: number = 10
    ) {
      return fetchApi<QualityAssessment>(
        `/enterprise/quality/tenants/{tenant_id}/assess-and-save`,
        {
          ...opts,
          method: 'POST',
          body: { workflow, trace_id: traceId, max_suggestions: maxSuggestions },
        }
      )
    },

    // Quality Healing endpoints
    async triggerQualityHealing(
      workflow: Record<string, unknown>,
      options?: { threshold?: number; auto_apply?: boolean }
    ) {
      return fetchApi<QualityHealingTriggerResponse>(
        `/enterprise/quality-healing/tenants/{tenant_id}/trigger`,
        {
          ...opts,
          method: 'POST',
          body: { workflow, ...options },
        }
      )
    },

    async getQualityHealing(healingId: string) {
      return fetchApi<QualityHealingRecord>(
        `/enterprise/quality-healing/tenants/{tenant_id}/healings/${healingId}`,
        opts
      )
    },

    async approveQualityHealing(healingId: string, fixIds: string[], approvedBy?: string) {
      return fetchApi<QualityHealingRecord>(
        `/enterprise/quality-healing/tenants/{tenant_id}/healings/${healingId}/approve`,
        {
          ...opts,
          method: 'POST',
          body: { selected_fix_ids: fixIds, approved_by: approvedBy },
        }
      )
    },

    async rollbackQualityHealing(healingId: string) {
      return fetchApi<{ healing_id: string; rolled_back: boolean; message: string }>(
        `/enterprise/quality-healing/tenants/{tenant_id}/healings/${healingId}/rollback`,
        { ...opts, method: 'POST' }
      )
    },

    async listQualityHealings(params?: { page?: number; page_size?: number; status?: string }) {
      const query = new URLSearchParams()
      if (params?.page) query.set('page', String(params.page))
      if (params?.page_size) query.set('page_size', String(params.page_size))
      if (params?.status) query.set('status', params.status)

      return fetchApi<QualityHealingListResponse>(
        `/enterprise/quality-healing/tenants/{tenant_id}/healings?${query}`,
        opts
      )
    },

    async getQualityHealingStats() {
      return fetchApi<Record<string, unknown>>(
        `/enterprise/quality-healing/tenants/{tenant_id}/stats`,
        opts
      )
    },

    async verifyQualityHealing(healingId: string) {
      return fetchApi<QualityHealingRecord>(
        `/enterprise/quality-healing/tenants/{tenant_id}/healings/${healingId}/verify`,
        { ...opts, method: 'POST' }
      )
    },
  }
}
