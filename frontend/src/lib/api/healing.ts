import { fetchApi } from './client'
import type { FetchOptions } from './client'
import type { FixSuggestionSummary, CodeChange } from './detections'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface HealingRecord {
  id: string
  detection_id: string
  status: 'pending' | 'in_progress' | 'applied' | 'failed' | 'rolled_back' | 'rejected' | 'staged'
  fix_type: string
  fix_id: string
  fix_suggestions: FixSuggestionSummary[]
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  applied_fixes: Record<string, any>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  original_state: Record<string, any>
  rollback_available: boolean
  validation_status: string | null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  validation_results: Record<string, any>
  approval_required: boolean
  approved_by: string | null
  approved_at: string | null
  started_at: string | null
  completed_at: string | null
  rolled_back_at: string | null
  created_at: string
  error_message: string | null
  // Per-detector progress tracking (Tier 1 capability)
  detector_progress?: Record<string, {
    before: number | null
    after: number | null
    status: 'pending' | 'fixing' | 'fixed' | 'failed' | 'rolled_back'
  }>
  // Staged deployment fields
  deployment_stage?: 'staged' | 'promoted' | 'rejected' | 'rolled_back' | null
  workflow_id?: string
  n8n_connection_id?: string
  staged_at?: string
  promoted_at?: string
}

export interface HealingListResponse {
  items: HealingRecord[]
  total: number
  page: number
  per_page: number
}

export interface TriggerHealingRequest {
  fix_id?: string
  approval_required?: boolean
}

export interface TriggerHealingResponse {
  healing_id: string
  detection_id: string
  status: string
  fix_type: string
  fix_id: string
  message: string
  approval_required: boolean
}

export interface ApproveHealingRequest {
  approved: boolean
  approver_id?: string
  notes?: string
}

export interface ApproveHealingResponse {
  healing_id: string
  approved: boolean
  status: string
  message: string
}

export interface RollbackResponse {
  healing_id: string
  rolled_back: boolean
  previous_status: string
  current_status: string
  message: string
}

// n8n Connection types
export interface N8nConnection {
  id: string
  name: string
  instance_url: string
  is_active: boolean
  last_verified_at: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

export interface N8nConnectionListResponse {
  items: N8nConnection[]
  total: number
}

export interface CreateN8nConnectionRequest {
  name: string
  instance_url: string
  api_key: string
}

// Apply fix to n8n types
export interface ApplyFixToN8nRequest {
  connection_id: string
  dry_run?: boolean
  stage?: boolean
}

export interface ApplyFixToN8nResponse {
  status: 'preview' | 'applied' | 'staged' | 'failed'
  healing_id?: string
  fix?: {
    type: string
    description: string
    confidence: string
  }
  diff?: WorkflowDiff
  backup_commit?: string
  workflow_version?: number
  deployment_stage?: string
  error?: string
}

export interface WorkflowDiff {
  added_nodes: string[]
  removed_nodes: string[]
  modified_nodes: string[]
  settings_changes: Record<string, unknown>
  summary: string
}

// Promote/Reject responses
export interface PromoteResponse {
  healing_id: string
  status: string
  deployment_stage: string
  workflow_id: string
  message: string
}

export interface RejectResponse {
  healing_id: string
  status: string
  deployment_stage: string
  workflow_id: string
  rolled_back: boolean
  message: string
}

// Verification types
export interface VerifyRequest {
  level: number // 1 = config, 2 = execution
}

export interface VerifyResponse {
  healing_id: string
  passed: boolean
  level: number
  before_confidence: number
  after_confidence: number
  confidence_reduction: number
  config_checks: Array<{
    success: boolean
    validation_type: string
    details: Record<string, unknown>
    error_message: string | null
  }>
  execution_result: Record<string, unknown> | null
  details: Record<string, unknown>
  error: string | null
}

export interface VerificationMetrics {
  total_verifications: number
  passed: number
  failed: number
  pass_rate: number
  average_confidence_reduction: number
  by_detection_type: Record<string, {
    total: number
    passed: number
    pass_rate: number
    avg_confidence_reduction: number
  }>
}

// Version history types
export interface WorkflowVersion {
  id: string
  tenant_id: string
  workflow_id: string
  connection_id: string
  version_number: number
  workflow_snapshot: Record<string, unknown>
  healing_id: string | null
  change_type: 'fix_applied' | 'staged' | 'promoted' | 'rejected' | 'rollback' | 'restored'
  change_description: string | null
  created_at: string
}

export interface VersionHistoryResponse {
  workflow_id: string
  connection_id: string
  versions: WorkflowVersion[]
  total: number
}

export interface RestoreVersionResponse {
  version_id: string
  workflow_id: string
  restored_from_version: number
  new_version_number: number
  message: string
}

// Healing progress types
export interface DetectorProgressItem {
  before: number | null
  after: number | null
  status: 'pending' | 'fixing' | 'fixed' | 'failed' | 'rolled_back'
}

export interface HealingProgressResponse {
  healing_id: string
  overall_status: string
  detector_progress: Record<string, DetectorProgressItem>
  total_detectors: number
  fixed_count: number
  failed_count: number
  pending_count: number
}

export interface HealingProgressSummary {
  total_healings: number
  active_healings: number
  total_detectors_healed: number
  total_detectors_failed: number
  total_detectors_pending: number
  success_rate: number
  by_detection_type: Record<string, { healed: number; failed: number; pending: number }>
}

// Re-export for convenience
export type { FixSuggestionSummary, CodeChange }

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export function createHealingApi(opts: FetchOptions) {
  const token = opts.token

  return {
    // Healing record management
    async listHealingRecords(params: {
      page?: number
      perPage?: number
      status?: string
      detectionId?: string
    } = {}) {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.perPage) query.set('per_page', String(params.perPage))
      if (params.status) query.set('status', params.status)
      if (params.detectionId) query.set('detection_id', params.detectionId)

      return fetchApi<HealingListResponse>(
        `/tenants/{tenant_id}/healing?${query}`,
        opts
      )
    },

    async getHealingStatus(healingId: string) {
      return fetchApi<HealingRecord>(
        `/tenants/{tenant_id}/healing/${healingId}/status`,
        opts
      )
    },

    async triggerHealing(detectionId: string, request: TriggerHealingRequest = {}) {
      return fetchApi<TriggerHealingResponse>(
        `/tenants/{tenant_id}/healing/trigger/${detectionId}`,
        { ...opts, method: 'POST', body: request }
      )
    },

    async approveHealing(healingId: string, request: ApproveHealingRequest) {
      return fetchApi<ApproveHealingResponse>(
        `/tenants/{tenant_id}/healing/${healingId}/approve`,
        { ...opts, method: 'POST', body: request }
      )
    },

    async rollbackHealing(healingId: string) {
      return fetchApi<RollbackResponse>(
        `/tenants/{tenant_id}/healing/${healingId}/rollback`,
        { ...opts, method: 'POST' }
      )
    },

    async completeHealing(healingId: string, validationPassed: boolean = true) {
      return fetchApi<HealingRecord>(
        `/tenants/{tenant_id}/healing/${healingId}/complete?validation_passed=${validationPassed}`,
        { ...opts, method: 'POST' }
      )
    },

    // n8n Connection management
    async listN8nConnections() {
      return fetchApi<N8nConnectionListResponse>(
        `/tenants/{tenant_id}/healing/n8n/connections`,
        opts
      )
    },

    async createN8nConnection(request: CreateN8nConnectionRequest) {
      return fetchApi<N8nConnection>(
        `/tenants/{tenant_id}/healing/n8n/connections`,
        { ...opts, method: 'POST', body: request }
      )
    },

    async deleteN8nConnection(connectionId: string) {
      return fetchApi<{ message: string }>(
        `/tenants/{tenant_id}/healing/n8n/connections/${connectionId}`,
        { ...opts, method: 'DELETE' }
      )
    },

    async testN8nConnection(connectionId: string) {
      return fetchApi<{ success: boolean; message: string }>(
        `/tenants/{tenant_id}/healing/n8n/connections/${connectionId}/test`,
        { ...opts, method: 'POST' }
      )
    },

    // Apply fix to n8n
    async applyFixToN8n(detectionId: string, request: ApplyFixToN8nRequest) {
      return fetchApi<ApplyFixToN8nResponse>(
        `/tenants/{tenant_id}/healing/apply-to-n8n/${detectionId}`,
        { ...opts, method: 'POST', body: request }
      )
    },

    // Staged deployment actions
    async promoteHealing(healingId: string) {
      return fetchApi<PromoteResponse>(
        `/tenants/{tenant_id}/healing/${healingId}/promote`,
        { ...opts, method: 'POST' }
      )
    },

    async rejectHealing(healingId: string) {
      return fetchApi<RejectResponse>(
        `/tenants/{tenant_id}/healing/${healingId}/reject`,
        { ...opts, method: 'POST' }
      )
    },

    // Verification
    async verifyHealing(healingId: string, level: number = 1) {
      return fetchApi<VerifyResponse>(
        `/tenants/{tenant_id}/healing/${healingId}/verify`,
        { ...opts, method: 'POST', body: { level } }
      )
    },

    async getVerificationMetrics() {
      return fetchApi<VerificationMetrics>(
        `/tenants/{tenant_id}/healing/verification-metrics`,
        opts
      )
    },

    // Version history
    async getWorkflowVersions(workflowId: string, connectionId: string, limit: number = 20) {
      return fetchApi<VersionHistoryResponse>(
        `/tenants/{tenant_id}/healing/versions/${workflowId}?connection_id=${connectionId}&limit=${limit}`,
        opts
      )
    },

    async restoreVersion(versionId: string) {
      return fetchApi<RestoreVersionResponse>(
        `/tenants/{tenant_id}/healing/versions/${versionId}/restore`,
        { ...opts, method: 'POST' }
      )
    },

    // Diagnose endpoints (no tenant required)
    async diagnoseTrace(content: string, format: string = 'auto', includeFixes: boolean = true) {
      return fetchApi<import('./diagnose').DiagnoseResult>('/diagnose/why-failed', {
        method: 'POST',
        body: { content, format, include_fixes: includeFixes, run_all_detections: true },
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      })
    },

    async diagnoseQuickCheck(content: string, format: string = 'auto') {
      return fetchApi<import('./diagnose').DiagnoseQuickCheckResult>('/diagnose/quick-check', {
        method: 'POST',
        body: { content, format },
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      })
    },

    async getDiagnoseFormats() {
      return fetchApi<{ formats: Array<{ name: string; description: string; default?: boolean; example_marker?: string }> }>(
        '/diagnose/formats',
        {}
      )
    },

    // Healing progress tracking
    async getHealingProgress(healingId: string) {
      return fetchApi<HealingProgressResponse>(
        `/tenants/{tenant_id}/healing/${healingId}/progress`,
        opts
      )
    },

    async getHealingProgressSummary() {
      return fetchApi<HealingProgressSummary>(
        `/tenants/{tenant_id}/healing/progress-summary`,
        opts
      )
    },
  }
}
