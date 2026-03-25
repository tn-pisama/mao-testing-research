import { fetchApi } from './client'
import type { FetchOptions } from './client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Detection {
  id: string
  trace_id: string
  state_id?: string
  detection_type: string
  confidence: number
  method: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  details: Record<string, any>
  validated: boolean
  false_positive?: boolean
  created_at: string
  // Plain-English explanation fields
  explanation?: string
  business_impact?: string
  suggested_action?: string
  // Detection transparency
  confidence_tier?: 'HIGH' | 'LIKELY' | 'POSSIBLE' | 'LOW'
  detector_method?: string
  // Quality scoring (Tier 1 capability)
  quality_score?: number
  quality_dimensions?: {
    correctness: number
    completeness: number
    safety: number
    efficiency: number
  }
}

export interface DetectionListResponse {
  items: Detection[]
  total: number
  page: number
  per_page: number
}

// Fix Suggestion types
export interface CodeChange {
  file_path: string
  language: string
  original_code?: string
  suggested_code: string
  start_line?: number
  end_line?: number
  description: string
  diff: string
}

export interface FixSuggestion {
  id: string
  detection_id: string
  detection_type: string
  fix_type: string
  confidence: string
  title: string
  description: string
  rationale: string
  code_changes: CodeChange[]
  estimated_impact: string
  breaking_changes: boolean
  requires_testing: boolean
  tags: string[]
  metadata: Record<string, unknown>
}

export interface FixSuggestionsResponse {
  detection_id: string
  suggestions: FixSuggestion[]
  total: number
}

export interface FixSuggestionSummary {
  id: string
  fix_type: string
  confidence: string
  description: string
  title: string
  code_changes?: CodeChange[]
}

export interface ApplyFixResult {
  success: boolean
  fix_id: string
  detection_id: string
  applied_at: string
  message: string
  rollback_available: boolean
}

// Source Fixes
export interface SourceFix {
  id: string
  detection_id: string
  file_path: string
  language: string
  original_code: string
  fixed_code: string
  unified_diff: string
  explanation: string
  root_cause?: string
  confidence: number
  breaking_risk: string
  status: string
  created_at: string
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createDetectionsApi(opts: FetchOptions) {
  return {
    async getDetections(params: {
      page?: number;
      perPage?: number;
      traceId?: string;
      type?: string;
      confidenceMin?: number;
      confidenceMax?: number;
      dateFrom?: string;
      dateTo?: string;
      validated?: boolean;
    }) {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.perPage) query.set('per_page', String(params.perPage))
      if (params.type) query.set('detection_type', params.type)
      if (params.traceId) query.set('trace_id', params.traceId)
      if (params.confidenceMin !== undefined) query.set('confidence_min', String(params.confidenceMin))
      if (params.confidenceMax !== undefined) query.set('confidence_max', String(params.confidenceMax))
      if (params.dateFrom) query.set('date_from', params.dateFrom)
      if (params.dateTo) query.set('date_to', params.dateTo)
      if (params.validated !== undefined) query.set('validated', String(params.validated))

      return fetchApi<DetectionListResponse>(`/tenants/{tenant_id}/detections?${query}`, opts)
    },

    async getDetection(id: string) {
      return fetchApi<Detection>(`/tenants/{tenant_id}/detections/${id}`, opts)
    },

    async validateDetection(id: string, params: { false_positive: boolean; notes?: string }) {
      return fetchApi<Detection>(`/tenants/{tenant_id}/detections/${id}/validate`, {
        ...opts,
        method: 'POST',
        body: params,
      })
    },

    // Fix suggestion endpoints
    async getFixSuggestions(detectionId: string) {
      return fetchApi<FixSuggestionsResponse>(`/tenants/{tenant_id}/detections/${detectionId}/fixes`, opts)
    },

    async applyFix(detectionId: string, fixId: string) {
      return fetchApi<ApplyFixResult>(`/tenants/{tenant_id}/detections/${detectionId}/fixes/${fixId}/apply`, {
        ...opts,
        method: 'POST',
      })
    },

    // Source Fixes
    async generateSourceFix(
      detectionId: string,
      input: { file_path: string; file_content: string; language: string; framework?: string }
    ) {
      return fetchApi<SourceFix>(
        `/tenants/{tenant_id}/source-fixes`,
        {
          ...opts,
          method: 'POST',
          body: { detection_id: detectionId, ...input },
        }
      )
    },

    async listSourceFixes(params?: { page?: number; per_page?: number; language?: string }) {
      const query = new URLSearchParams()
      if (params?.page) query.set('page', String(params.page))
      if (params?.per_page) query.set('per_page', String(params.per_page))
      if (params?.language) query.set('language', params.language)
      return fetchApi<{ fixes: SourceFix[]; total: number }>(
        `/tenants/{tenant_id}/source-fixes?${query}`,
        opts
      )
    },

    async applySourceFix(fixId: string) {
      return fetchApi<{ success: boolean; git_patch: string; instructions: string }>(
        `/tenants/{tenant_id}/source-fixes/${fixId}/apply`,
        { ...opts, method: 'POST' }
      )
    },
  }
}
