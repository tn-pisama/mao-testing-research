const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

interface FetchOptions {
  method?: string
  body?: any
  headers?: Record<string, string>
  token?: string | null
  tenantId?: string | null
}

async function fetchApi<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { token, tenantId } = options
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  }
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const url = endpoint.includes('{tenant_id}') && tenantId
    ? `${API_BASE}${endpoint.replace('{tenant_id}', tenantId)}`
    : `${API_BASE}${endpoint}`

  const response = await fetch(url, {
    method: options.method || 'GET',
    headers,
    credentials: 'include',
    body: options.body ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    let detail = `API Error: ${response.status}`
    try {
      const body = await response.json()
      if (body.detail) detail = body.detail
    } catch {
      // non-JSON response, keep status-only message
    }
    const err = new Error(detail) as Error & { status: number }
    err.status = response.status
    throw err
  }

  return response.json()
}

export interface Trace {
  id: string
  session_id: string
  framework: string
  status: string
  total_tokens: number
  total_cost_cents: number
  created_at: string
  completed_at?: string
  state_count: number
  detection_count: number
}

export interface State {
  id: string
  sequence_num: number
  agent_id: string
  state_delta: Record<string, any>
  state_hash: string
  token_count: number
  latency_ms: number
  created_at: string
  // Claude Code specific fields (in metadata)
  metadata?: {
    user_input?: string
    reasoning?: string
    ai_output?: string
    model?: string
    input_tokens?: number
    output_tokens?: number
    cache_read_tokens?: number
    cost_usd?: number
    trace_type?: string
    skill_name?: string
    working_dir?: string
  }
}

export interface Detection {
  id: string
  trace_id: string
  state_id?: string
  detection_type: string
  confidence: number
  method: string
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
}

export interface LoopAnalytics {
  total_loops_detected: number
  loops_by_method: Record<string, number>
  avg_loop_length: number
  top_agents_in_loops: Array<{ agent_id: string; count: number }>
  time_series: Array<{ date: string; count: number }>
}

export interface CostAnalytics {
  total_cost_cents: number
  total_tokens: number
  cost_by_framework: Record<string, number>
  cost_by_day: Array<{ date: string; cost_cents: number }>
  top_expensive_traces: Array<{
    trace_id: string
    session_id: string
    cost_cents: number
    tokens: number
  }>
}

// Testing types
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

// Replay types
export interface ReplayBundle {
  id: string
  name: string
  trace_id: string
  created_at: string
  event_count: number
  duration_ms: number
  status: string
  models_used: string[]
  tools_used: string[]
  agents_involved: string[]
  total_tokens: number
}

export interface ReplayResult {
  bundle_id: string
  status: string
  started_at: string
  completed_at?: string
  events_replayed: number
  events_total: number
  matches: number
  mismatches: number
  similarity_score: number
}

export interface ReplayDiff {
  step: number
  diff_type: string
  original: string
  replayed: string
  match: boolean
  similarity: number
  details: Record<string, any>
}

// Regression types
export interface Baseline {
  id: string
  name: string
  description: string
  entry_count: number
  model: string
  created_at: string
  updated_at: string
  last_tested?: string
}

export interface DriftAlert {
  id: string
  severity: string
  drift_type: string
  prompt: string
  similarity: number
  detected_at: string
  baseline_id: string
  details: Record<string, any>
}

export interface ModelFingerprint {
  model: string
  version: string
  provider: string
  fingerprint_hash: string
  last_seen: string
  status: string
  change_detected: boolean
}

// Agent Forensics Diagnose types
export interface DiagnoseDetection {
  category: string
  detected: boolean
  confidence: number
  severity: string
  title: string
  description: string
  evidence: Record<string, any>[]
  affected_spans: string[]
  suggested_fix?: string
}

export interface DiagnoseAutoFix {
  description: string
  confidence: number
  action: string
}

export interface DiagnoseResult {
  trace_id: string
  analyzed_at: string
  has_failures: boolean
  failure_count: number
  primary_failure?: DiagnoseDetection
  all_detections: DiagnoseDetection[]
  total_spans: number
  error_spans: number
  total_tokens: number
  duration_ms: number
  root_cause_explanation?: string
  self_healing_available: boolean
  auto_fix_preview?: DiagnoseAutoFix
  detection_time_ms: number
  detectors_run: string[]
}

export interface DiagnoseQuickCheckResult {
  has_failures: boolean
  failure_count: number
  primary_category?: string
  primary_severity?: string
  message: string
}

// Testing additional types
export interface AssertionResult {
  assertion_type: string
  passed: boolean
  message: string
  details: Record<string, any>
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

// Chaos types
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

// Evals types
export interface EvalResult {
  overall_score: number
  passed: boolean
  scores: Record<string, number>
  results: Array<Record<string, any>>
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

// N8n types
export interface N8nWorkflow {
  id: string
  workflow_id: string
  workflow_name?: string
  webhook_url: string
  ingestion_mode?: string
  registered_at: string
}

// OpenClaw types
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

// Dify types
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

// LangGraph types
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

// Security types
export interface InjectionCheckResult {
  detected: boolean
  confidence: number
  attack_type?: string
  severity: string
  matched_patterns: string[]
  details: Record<string, any>
}

export interface HallucinationCheckResult {
  detected: boolean
  confidence: number
  hallucination_type?: string
  grounding_score: number
  evidence: string[]
  details: Record<string, any>
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
  details: Record<string, any>
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
  metadata: Record<string, any>
}

export interface FixSuggestionsResponse {
  detection_id: string
  suggestions: FixSuggestion[]
  total: number
}

export interface ApplyFixResult {
  success: boolean
  fix_id: string
  detection_id: string
  applied_at: string
  message: string
  rollback_available: boolean
}

// ============================================================================
// Healing Types
// ============================================================================

export interface HealingRecord {
  id: string
  detection_id: string
  status: 'pending' | 'in_progress' | 'applied' | 'failed' | 'rolled_back' | 'rejected' | 'staged'
  fix_type: string
  fix_id: string
  fix_suggestions: FixSuggestionSummary[]
  applied_fixes: Record<string, any>
  original_state: Record<string, any>
  rollback_available: boolean
  validation_status: string | null
  validation_results: Record<string, any>
  approval_required: boolean
  approved_by: string | null
  approved_at: string | null
  started_at: string | null
  completed_at: string | null
  rolled_back_at: string | null
  created_at: string
  error_message: string | null
  // Staged deployment fields
  deployment_stage?: 'staged' | 'promoted' | 'rejected' | 'rolled_back' | null
  workflow_id?: string
  n8n_connection_id?: string
  staged_at?: string
  promoted_at?: string
}

export interface FixSuggestionSummary {
  id: string
  fix_type: string
  confidence: string
  description: string
  title: string
  code_changes?: CodeChange[]
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
  settings_changes: Record<string, any>
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
    details: Record<string, any>
    error_message: string | null
  }>
  execution_result: Record<string, any> | null
  details: Record<string, any>
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
  workflow_snapshot: Record<string, any>
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

// ============================================================================
// Quality Assessment Types
// ============================================================================

export interface QualityDimensionScore {
  dimension: string
  score: number
  weight: number
  issues: string[]
  evidence: Record<string, any>
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
  metadata?: Record<string, any>
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

// ============================================================================
// Quality Healing Types
// ============================================================================

export interface QualityHealingRecord {
  id: string
  assessment_id?: string
  status: string
  before_score: number
  after_score: number | null
  dimensions_targeted: string[]
  fix_suggestions_count: number
  fix_suggestions?: FixSuggestionSummary[]
  applied_fixes: any[]
  validation_results: any[]
  validation_status?: string | null
  rollback_available?: boolean
  is_successful: boolean
  score_improvement: number | null
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

export interface QualityDimensionInfo {
  name: string
  description: string
  weight: number
  checks: string[]
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

export interface QualityDimensionsResponse {
  agent_dimensions: QualityDimensionInfo[]
  orchestration_dimensions: QualityDimensionInfo[]
}

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

export function createApiClient(token?: string | null, tenantId?: string | null) {
  const opts = { token, tenantId }
  
  return {
    async getTraces(params: { page?: number; perPage?: number; status?: string }) {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.perPage) query.set('per_page', String(params.perPage))
      if (params.status) query.set('status_filter', params.status)
      
      return fetchApi<{ traces: Trace[]; total: number; page: number; per_page: number }>(
        `/tenants/{tenant_id}/traces?${query}`,
        opts
      )
    },

    async getTrace(id: string) {
      return fetchApi<Trace>(`/tenants/{tenant_id}/traces/${id}`, opts)
    },

    async getTraceStates(traceId: string) {
      return fetchApi<State[]>(`/tenants/{tenant_id}/traces/${traceId}/states`, opts)
    },

    async analyzeTrace(traceId: string) {
      return fetchApi(`/tenants/{tenant_id}/traces/${traceId}/analyze`, { ...opts, method: 'POST' })
    },

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

      return fetchApi<{ items: Detection[]; total: number; page: number; per_page: number }>(`/tenants/{tenant_id}/detections?${query}`, opts)
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

    // ============================================================================
    // Agents API Methods
    // ============================================================================

    async listAgents() {
      return fetchApi<{ agents: import('@/components/agents').AgentInfo[], total: number }>(
        `/tenants/{tenant_id}/agents`,
        opts
      )
    },

    // ============================================================================
    // Healing API Methods
    // ============================================================================

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

    async getLoopAnalytics(days: number = 30) {
      return fetchApi<LoopAnalytics>(`/tenants/{tenant_id}/analytics/loops?days=${days}`, opts)
    },

    async getCostAnalytics(days: number = 30) {
      return fetchApi<CostAnalytics>(`/tenants/{tenant_id}/analytics/cost?days=${days}`, opts)
    },

    // Testing endpoints
    async getAccuracyMetrics(days: number = 30) {
      return fetchApi<AccuracyMetric[]>(`/tenants/{tenant_id}/testing/accuracy?days=${days}`, opts)
    },

    async getIntegrationStatus() {
      return fetchApi<IntegrationStatus[]>(`/tenants/{tenant_id}/testing/integrations`, opts)
    },

    async getHandoffs(limit: number = 10) {
      return fetchApi<Handoff[]>(`/tenants/{tenant_id}/testing/handoffs?limit=${limit}`, opts)
    },

    async analyzeHandoffs(traceData: Record<string, any>) {
      return fetchApi<HandoffAnalysis>(`/tenants/{tenant_id}/testing/analyze`, {
        ...opts,
        method: 'POST',
        body: { trace_data: traceData, include_graph: true },
      })
    },

    // Replay endpoints
    async getReplayBundles(limit: number = 20, offset: number = 0) {
      return fetchApi<ReplayBundle[]>(`/tenants/{tenant_id}/replay/bundles?limit=${limit}&offset=${offset}`, opts)
    },

    async getReplayBundle(bundleId: string) {
      return fetchApi<ReplayBundle>(`/tenants/{tenant_id}/replay/bundles/${bundleId}`, opts)
    },

    async createReplayBundle(traceId: string, name: string) {
      return fetchApi<ReplayBundle>(`/tenants/{tenant_id}/replay/bundles`, {
        ...opts,
        method: 'POST',
        body: { trace_id: traceId, name },
      })
    },

    async startReplay(bundleId: string, mode: string = 'deterministic') {
      return fetchApi<ReplayResult>(`/tenants/{tenant_id}/replay/bundles/${bundleId}/start`, {
        ...opts,
        method: 'POST',
        body: { bundle_id: bundleId, mode },
      })
    },

    async stopReplay(bundleId: string) {
      return fetchApi<ReplayResult>(`/tenants/{tenant_id}/replay/bundles/${bundleId}/stop`, {
        ...opts,
        method: 'POST',
      })
    },

    async getReplayStatus(bundleId: string) {
      return fetchApi<ReplayResult>(`/tenants/{tenant_id}/replay/bundles/${bundleId}/status`, opts)
    },

    async compareReplay(bundleId: string, newTraceData: Record<string, any>) {
      return fetchApi<{ bundle_id: string; overall_similarity: number; total_steps: number; matching_steps: number; diffs: ReplayDiff[] }>(
        `/tenants/{tenant_id}/replay/bundles/${bundleId}/compare`,
        { ...opts, method: 'POST', body: { bundle_id: bundleId, new_trace_data: newTraceData } }
      )
    },

    // Regression endpoints
    async getBaselines(limit: number = 20, offset: number = 0) {
      return fetchApi<Baseline[]>(`/tenants/{tenant_id}/regression/baselines?limit=${limit}&offset=${offset}`, opts)
    },

    async getBaseline(baselineId: string) {
      return fetchApi<Baseline>(`/tenants/{tenant_id}/regression/baselines/${baselineId}`, opts)
    },

    async createBaseline(name: string, description: string, model: string) {
      return fetchApi<Baseline>(`/tenants/{tenant_id}/regression/baselines`, {
        ...opts,
        method: 'POST',
        body: { name, description, model },
      })
    },

    async deleteBaseline(baselineId: string) {
      return fetchApi<void>(`/tenants/{tenant_id}/regression/baselines/${baselineId}`, {
        ...opts,
        method: 'DELETE',
      })
    },

    async testBaseline(baselineId: string, currentOutputs: Array<{ prompt_hash: string; output: string }>) {
      return fetchApi<{ total_alerts: number; critical_count: number; high_count: number; medium_count: number; low_count: number; models_affected: string[]; recent_alerts: DriftAlert[] }>(
        `/tenants/{tenant_id}/regression/baselines/${baselineId}/test`,
        { ...opts, method: 'POST', body: { baseline_id: baselineId, current_outputs: currentOutputs } }
      )
    },

    async getDriftAlerts(severity?: string, limit: number = 20) {
      const query = new URLSearchParams()
      if (severity) query.set('severity', severity)
      query.set('limit', String(limit))
      return fetchApi<DriftAlert[]>(`/tenants/{tenant_id}/regression/alerts?${query}`, opts)
    },

    async getModelFingerprints() {
      return fetchApi<ModelFingerprint[]>(`/tenants/{tenant_id}/regression/fingerprints`, opts)
    },

    async refreshFingerprints() {
      return fetchApi<{ status: string; models_queued: string[]; estimated_time_seconds: number }>(
        `/tenants/{tenant_id}/regression/fingerprints/refresh`,
        { ...opts, method: 'POST' }
      )
    },

    // Testing additional endpoints
    async runAssertions(traceData: Record<string, any>) {
      return fetchApi<AssertionResult[]>(`/tenants/{tenant_id}/testing/assertions`, {
        ...opts,
        method: 'POST',
        body: { trace_data: traceData },
      })
    },

    async generateTests(traceData: Record<string, any>, testTypes: string[] = ['handoff', 'context', 'sla']) {
      return fetchApi<GeneratedTestSuite>(`/tenants/{tenant_id}/testing/generate`, {
        ...opts,
        method: 'POST',
        body: { trace_data: traceData, test_types: testTypes },
      })
    },

    // Chaos endpoints
    async getChaosExperimentTypes() {
      return fetchApi<ChaosExperimentType[]>(`/tenants/{tenant_id}/chaos/experiment-types`, opts)
    },

    async listChaosSessions() {
      return fetchApi<ChaosSession[]>(`/tenants/{tenant_id}/chaos/sessions`, opts)
    },

    async getChaosSession(sessionId: string) {
      return fetchApi<Record<string, any>>(`/tenants/{tenant_id}/chaos/sessions/${sessionId}`, opts)
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

    // Evals endpoints
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

    // Security endpoints
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
      toolResults?: Record<string, any>[]
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
      messages?: Record<string, any>[],
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

    // Import Jobs endpoints (placeholder - need to check actual backend routes)
    async listImportJobs(limit: number = 20, offset: number = 0) {
      return fetchApi<ImportJob[]>(`/tenants/{tenant_id}/import/jobs?limit=${limit}&offset=${offset}`, opts)
    },

    async getImportJob(jobId: string) {
      return fetchApi<ImportJob>(`/tenants/{tenant_id}/import/jobs/${jobId}`, opts)
    },

    async createImportJob(sourceType: string, config: Record<string, any>) {
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

    // Agent Forensics Diagnose endpoints (no tenant required)
    async diagnoseTrace(content: string, format: string = 'auto', includeFixes: boolean = true) {
      return fetchApi<DiagnoseResult>('/diagnose/why-failed', {
        method: 'POST',
        body: { content, format, include_fixes: includeFixes, run_all_detections: true },
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      })
    },

    async diagnoseQuickCheck(content: string, format: string = 'auto') {
      return fetchApi<DiagnoseQuickCheckResult>('/diagnose/quick-check', {
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

    // ========================================================================
    // Quality Assessment endpoints
    // ========================================================================

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

    async assessWorkflowQuality(workflow: Record<string, any>, maxSuggestions: number = 10) {
      return fetchApi<QualityAssessment>(`/enterprise/quality/workflow`, {
        ...opts,
        method: 'POST',
        body: { workflow, max_suggestions: maxSuggestions },
      })
    },

    async assessAndSaveQuality(
      workflow: Record<string, any>,
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

    // ========================================================================
    // Quality Healing endpoints
    // ========================================================================

    async triggerQualityHealing(
      workflow: Record<string, any>,
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
      return fetchApi<Record<string, any>>(
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
      return fetchApi(`/tenants/{tenant_id}/settings/thresholds`, {
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
      return fetchApi<QualityAssessment[]>(
        `/tenants/{tenant_id}/workflow-groups/${groupId}/workflows`,
        opts
      )
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
        readiness_criteria: Record<string, any>
      }>(`/diagnostics/detector-status`, opts)
    },
  }
}

export const api = createApiClient()
