import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FeedbackStats {
  total_feedback: number
  true_positives: number
  false_positives: number
  false_negatives: number
  true_negatives: number
  precision: number
  recall: number
  f1_score: number
  by_framework: Record<string, { total: number; correct: number; incorrect: number }>
  by_detection_type: Record<string, { total: number; correct: number; incorrect: number }>
  by_method: Record<string, { total: number; correct: number; incorrect: number }>
}

export interface ThresholdRecommendation {
  framework: string
  current_structural_threshold: number
  current_semantic_threshold: number
  recommended_structural_threshold: number
  recommended_semantic_threshold: number
  confidence: number
  sample_size: number
  reasoning: string
}

// Import Job types
export interface ImportJob {
  id: string
  tenant_id: string
  source_type: string
  status: string
  created_at: string
  started_at?: string
  completed_at?: string
  error_message?: string
  records_processed: number
  records_failed: number
}

// Metrics types
export interface MetricsExport {
  format: string
  data: string
  timestamp: string
}

// Workflow Groups
export interface AutoDetectRule {
  type: 'workflow_name_pattern' | 'source' | 'complexity_level' | 'grade' | 'agent_count' | 'has_critical_issues'
  pattern?: string
  value?: string | number | boolean
  values?: string[]
  operator?: '>=' | '<=' | '=' | '>' | '<'
  case_sensitive?: boolean
}

export interface AutoDetectRules {
  rules: AutoDetectRule[]
  match_mode: 'all' | 'any'
}

export interface WorkflowGroup {
  id: string
  tenant_id: string
  name: string
  description?: string
  color?: string
  icon?: string
  is_default: boolean
  auto_detect_rules?: AutoDetectRules
  workflow_count?: number
  created_at: string
  updated_at: string
  // User customizations (if applicable)
  custom_name?: string
  is_hidden?: boolean
  sort_order?: number
}

export interface CreateGroupRequest {
  name: string
  description?: string
  color?: string
  icon?: string
  auto_detect_rules?: AutoDetectRules
}

export interface AssignWorkflowsRequest {
  workflow_ids: string[]
}

export interface AutoDetectResponse {
  assigned_count: number
  workflow_ids: string[]
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createTenantsApi(opts: FetchOptions) {
  return {
    // Feedback/Tuning endpoints
    async getFeedbackStats() {
      return fetchApi<FeedbackStats>(`/tenants/{tenant_id}/feedback/stats`, opts)
    },

    async getThresholdRecommendations() {
      return fetchApi<ThresholdRecommendation[]>(`/tenants/{tenant_id}/feedback/recommendations`, opts)
    },

    async submitFeedback(
      detectionId: string,
      isCorrect: boolean,
      options?: { reason?: string; severityRating?: number }
    ) {
      return fetchApi<{ id: string; status: string }>(`/tenants/{tenant_id}/feedback`, {
        ...opts,
        method: 'POST',
        body: {
          detection_id: detectionId,
          is_correct: isCorrect,
          reason: options?.reason,
          severity_rating: options?.severityRating,
        },
      })
    },

    async updateThresholds(config: {
      global_thresholds?: { structural_threshold?: number; semantic_threshold?: number };
      framework_thresholds?: Record<string, { structural_threshold?: number; semantic_threshold?: number }>;
    }) {
      return fetchApi<unknown>(`/tenants/{tenant_id}/settings/thresholds`, {
        ...opts,
        method: 'PUT',
        body: config,
      })
    },

    async resetThresholds(framework?: string) {
      const query = framework ? `?framework=${framework}` : ''
      return fetchApi<{ message: string }>(`/tenants/{tenant_id}/settings/thresholds${query}`, {
        ...opts,
        method: 'DELETE',
      })
    },

    // Workflow Groups endpoints
    async listWorkflowGroups() {
      return fetchApi<WorkflowGroup[]>(`/tenants/{tenant_id}/workflow-groups`, opts)
    },

    async createWorkflowGroup(data: CreateGroupRequest) {
      return fetchApi<WorkflowGroup>(`/tenants/{tenant_id}/workflow-groups`, {
        ...opts,
        method: 'POST',
        body: data,
      })
    },

    async updateWorkflowGroup(groupId: string, data: Partial<CreateGroupRequest>) {
      return fetchApi<WorkflowGroup>(`/tenants/{tenant_id}/workflow-groups/${groupId}`, {
        ...opts,
        method: 'PUT',
        body: data,
      })
    },

    async deleteWorkflowGroup(groupId: string) {
      return fetchApi<{ success: boolean; message: string }>(
        `/tenants/{tenant_id}/workflow-groups/${groupId}`,
        {
          ...opts,
          method: 'DELETE',
        }
      )
    },

    async assignWorkflowsToGroup(groupId: string, workflowIds: string[]) {
      return fetchApi<{ success: boolean; assigned_count: number; workflow_ids: string[] }>(
        `/tenants/{tenant_id}/workflow-groups/${groupId}/assign`,
        {
          ...opts,
          method: 'POST',
          body: { workflow_ids: workflowIds },
        }
      )
    },

    async runGroupAutoDetection(groupId: string) {
      return fetchApi<AutoDetectResponse>(
        `/tenants/{tenant_id}/workflow-groups/${groupId}/auto-detect`,
        {
          ...opts,
          method: 'POST',
        }
      )
    },

    async getGroupWorkflows(groupId: string) {
      return fetchApi<import('./quality').QualityAssessment[]>(
        `/tenants/{tenant_id}/workflow-groups/${groupId}/workflows`,
        opts
      )
    },

    // Import Jobs endpoints
    async listImportJobs(limit: number = 20, offset: number = 0) {
      return fetchApi<ImportJob[]>(`/tenants/{tenant_id}/import/jobs?limit=${limit}&offset=${offset}`, opts)
    },

    async getImportJob(jobId: string) {
      return fetchApi<ImportJob>(`/tenants/{tenant_id}/import/jobs/${jobId}`, opts)
    },

    async createImportJob(sourceType: string, config: Record<string, unknown>) {
      return fetchApi<ImportJob>(`/tenants/{tenant_id}/import/jobs`, {
        ...opts,
        method: 'POST',
        body: { source_type: sourceType, config },
      })
    },

    // Metrics endpoints
    async exportMetrics(format: string = 'prometheus') {
      return fetchApi<MetricsExport>(`/tenants/{tenant_id}/metrics/export?format=${format}`, opts)
    },

    // System Summary endpoint
    async getSystemSummary() {
      return fetchApi<Record<string, unknown>>(`/tenants/{tenant_id}/summary`, opts)
    },

    // Diagnostics endpoints (not tenant-scoped)
    async getDetectorStatus() {
      return fetchApi<{
        detectors: Array<{
          name: string
          readiness: 'production' | 'beta' | 'experimental' | 'failing' | 'untested'
          description: string
          enabled: boolean
          f1_score: number | null
          precision: number | null
          recall: number | null
          sample_count: number
          optimal_threshold: number | null
        }>
        summary: Record<string, number>
        calibrated_at: string
        readiness_criteria: Record<string, unknown>
      }>(`/diagnostics/detector-status`, opts)
    },

    // Onboarding
    async getOnboardingStatus() {
      return fetchApi<{
        has_traces: boolean
        trace_count: number
        first_trace_id: string | null
        first_trace_at: string | null
        has_detections: boolean
        detection_count: number
      }>(`/tenants/{tenant_id}/onboarding/status`, opts)
    },

    async loadDemoData() {
      return fetchApi<{ trace_id: string; trace_count: number; message: string }>(
        `/tenants/{tenant_id}/onboarding/load-demo`, { ...opts, method: 'POST' }
      )
    },

    async runOnboardingDetection(traceId: string) {
      return fetchApi<{
        detections: Array<{
          id: string
          detection_type: string
          confidence: number
          description: string | null
        }>
        total: number
        types: string[]
        highest_confidence: number
      }>(`/tenants/{tenant_id}/onboarding/run-detection`, {
        ...opts,
        method: 'POST',
        body: { trace_id: traceId },
      })
    },
  }
}
