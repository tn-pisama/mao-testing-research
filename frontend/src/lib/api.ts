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
    throw new Error(`API Error: ${response.status}`)
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

    async getDetections(params: { page?: number; perPage?: number; traceId?: string; type?: string }) {
      const query = new URLSearchParams()
      if (params.page) query.set('page', String(params.page))
      if (params.perPage) query.set('per_page', String(params.perPage))
      if (params.type) query.set('detection_type', params.type)
      
      return fetchApi<Detection[]>(`/tenants/{tenant_id}/detections?${query}`, opts)
    },

    async validateDetection(id: string, falsePositive: boolean, notes?: string) {
      return fetchApi<Detection>(`/tenants/{tenant_id}/detections/${id}/validate`, {
        ...opts,
        method: 'POST',
        body: { false_positive: falsePositive, notes },
      })
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
      return fetchApi<N8nWorkflow>(`/tenants/{tenant_id}/n8n/workflows`, {
        ...opts,
        method: 'POST',
        body: { workflow_id: workflowId, workflow_name: workflowName },
      })
    },

    async listN8nWorkflows() {
      return fetchApi<N8nWorkflow[]>(`/tenants/{tenant_id}/n8n/workflows`, opts)
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
  }
}

export const api = createApiClient()
