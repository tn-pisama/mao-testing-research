import type { DemoScenario } from './index'

const TRACE_ID = 'demo-trace-loop-001'
const SESSION_ID = 'demo-session-loop-001'

const states = [
  {
    id: 'demo-state-loop-001', trace_id: TRACE_ID, step_index: 0,
    sequence_num: 0, agent_id: 'research-agent', action: 'initialize',
    state_delta: { phase: 'init' }, state_hash: 'h-loop-001',
    token_count: 120, latency_ms: 340, created_at: '2026-03-10T09:00:00Z',
    input_data: { query: 'Find all configuration files for the microservices deployment' },
    output_data: { plan: 'Search project root, then service directories' },
  },
  {
    id: 'demo-state-loop-002', trace_id: TRACE_ID, step_index: 1,
    sequence_num: 1, agent_id: 'research-agent', action: 'search_files',
    state_delta: { phase: 'searching', directory: '/services' }, state_hash: 'h-loop-002',
    token_count: 210, latency_ms: 1200, created_at: '2026-03-10T09:00:05Z',
    input_data: { directory: '/services', pattern: '*.yaml' },
    output_data: { files_found: 3, result: 'Found docker-compose.yaml, values.yaml, config.yaml' },
  },
  {
    id: 'demo-state-loop-003', trace_id: TRACE_ID, step_index: 2,
    sequence_num: 2, agent_id: 'research-agent', action: 'search_files',
    state_delta: { phase: 'searching', directory: '/services/api' }, state_hash: 'h-loop-003',
    token_count: 195, latency_ms: 980, created_at: '2026-03-10T09:00:12Z',
    input_data: { directory: '/services/api', pattern: '*.yaml' },
    output_data: { files_found: 1, result: 'Found api-config.yaml' },
  },
  {
    id: 'demo-state-loop-004', trace_id: TRACE_ID, step_index: 3,
    sequence_num: 3, agent_id: 'research-agent', action: 'search_files',
    state_delta: { phase: 'searching', directory: '/services' }, state_hash: 'h-loop-002',
    token_count: 210, latency_ms: 1180, created_at: '2026-03-10T09:00:20Z',
    input_data: { directory: '/services', pattern: '*.yaml' },
    output_data: { files_found: 3, result: 'Found docker-compose.yaml, values.yaml, config.yaml' },
  },
  {
    id: 'demo-state-loop-005', trace_id: TRACE_ID, step_index: 4,
    sequence_num: 4, agent_id: 'research-agent', action: 'search_files',
    state_delta: { phase: 'searching', directory: '/services/api' }, state_hash: 'h-loop-003',
    token_count: 195, latency_ms: 950, created_at: '2026-03-10T09:00:28Z',
    input_data: { directory: '/services/api', pattern: '*.yaml' },
    output_data: { files_found: 1, result: 'Found api-config.yaml' },
  },
  {
    id: 'demo-state-loop-006', trace_id: TRACE_ID, step_index: 5,
    sequence_num: 5, agent_id: 'research-agent', action: 'search_files',
    state_delta: { phase: 'searching', directory: '/services' }, state_hash: 'h-loop-002',
    token_count: 210, latency_ms: 1210, created_at: '2026-03-10T09:00:35Z',
    input_data: { directory: '/services', pattern: '*.yaml' },
    output_data: { files_found: 3, result: 'Found docker-compose.yaml, values.yaml, config.yaml' },
  },
  {
    id: 'demo-state-loop-007', trace_id: TRACE_ID, step_index: 6,
    sequence_num: 6, agent_id: 'research-agent', action: 'search_files',
    state_delta: { phase: 'searching', directory: '/services/api' }, state_hash: 'h-loop-003',
    token_count: 195, latency_ms: 970, created_at: '2026-03-10T09:00:42Z',
    input_data: { directory: '/services/api', pattern: '*.yaml' },
    output_data: { files_found: 1, result: 'Found api-config.yaml' },
  },
  {
    id: 'demo-state-loop-008', trace_id: TRACE_ID, step_index: 7,
    sequence_num: 7, agent_id: 'research-agent', action: 'search_files',
    state_delta: { phase: 'searching', directory: '/services' }, state_hash: 'h-loop-002',
    token_count: 210, latency_ms: 1190, created_at: '2026-03-10T09:00:50Z',
    input_data: { directory: '/services', pattern: '*.yaml' },
    output_data: { files_found: 3, result: 'Found docker-compose.yaml, values.yaml, config.yaml' },
  },
  {
    id: 'demo-state-loop-009', trace_id: TRACE_ID, step_index: 8,
    sequence_num: 8, agent_id: 'research-agent', action: 'terminated',
    state_delta: { phase: 'terminated', reason: 'max_iterations' }, state_hash: 'h-loop-009',
    token_count: 85, latency_ms: 120, created_at: '2026-03-10T09:00:55Z',
    input_data: {},
    output_data: { error: 'Maximum iteration count (20) exceeded' },
  },
]

const detections = [
  {
    id: 'demo-det-loop-001', trace_id: TRACE_ID, state_id: 'demo-state-loop-004',
    detection_type: 'loop', confidence: 0.97, method: 'hash',
    details: { loop_length: 2, repeated_hashes: ['h-loop-002', 'h-loop-003'], iterations: 3 },
    validated: true, false_positive: false, created_at: '2026-03-10T09:00:56Z',
    explanation: 'The research agent repeated the same two-step file search cycle 3 times, visiting /services and /services/api with identical results each time.',
    business_impact: 'Wasted 1,230 tokens and 50 seconds of execution time on redundant searches.',
    suggested_action: 'Add visited-directory deduplication or a result cache to the search tool.',
    confidence_tier: 'HIGH' as const, detector_method: 'hash',
  },
  {
    id: 'demo-det-loop-002', trace_id: TRACE_ID, state_id: 'demo-state-loop-006',
    detection_type: 'loop', confidence: 0.92, method: 'structural',
    details: { pattern: 'search_files -> search_files', repetitions: 4 },
    validated: true, false_positive: false, created_at: '2026-03-10T09:00:56Z',
    explanation: 'Structural analysis confirms the agent called search_files 7 consecutive times without making progress toward aggregation or output.',
    business_impact: 'The agent hit its max-iteration guard before producing a useful result.',
    suggested_action: 'Introduce a progress check after each search step to verify new information was gained.',
    confidence_tier: 'HIGH' as const, detector_method: 'structural',
  },
]

const healingRecords = [
  {
    id: 'demo-heal-loop-001', detection_id: 'demo-det-loop-001',
    status: 'applied' as const, fix_type: 'loop_break',
    fix_id: 'fix-loop-break-001',
    fix_suggestions: [{
      id: 'fix-sug-loop-001', title: 'Add search result deduplication',
      description: 'Cache previously searched directories and skip re-searching them.',
      confidence: '0.88', fix_type: 'loop_prevention',
    }],
    applied_fixes: { strategy: 'deduplicate_search_targets', max_revisits: 1 },
    original_state: { directory: '/services', pattern: '*.yaml' },
    rollback_available: true,
    validation_status: 'passed', validation_results: { loop_eliminated: true, results_preserved: true },
    approval_required: false, approved_by: null, approved_at: null,
    started_at: '2026-03-10T09:01:00Z', completed_at: '2026-03-10T09:01:02Z',
    rolled_back_at: null, created_at: '2026-03-10T09:00:58Z', error_message: null,
  },
]

export const loopScenario: DemoScenario = {
  id: 'demo-scenario-loop',
  title: 'Research Agent Stuck in Loop',
  description: 'A LangGraph research agent gets stuck repeatedly searching the same directories for configuration files, wasting tokens before hitting its iteration limit.',
  icon: 'RefreshCw',
  framework: 'langgraph',
  traces: [{
    id: TRACE_ID, session_id: SESSION_ID, framework: 'langgraph',
    status: 'failed', total_tokens: 1630, total_cost_cents: 0.41,
    created_at: '2026-03-10T09:00:00Z', state_count: 9, detection_count: 2,
    states,
  }],
  detections,
  healingRecords,
  highlights: {
    traceId: TRACE_ID,
    detectionId: 'demo-det-loop-001',
    healingId: 'demo-heal-loop-001',
    explanation: 'The research agent entered a 2-step loop, alternating between /services and /services/api searches. PISAMA detected the repeated hash pattern after 3 cycles and suggested adding search deduplication.',
  },
}
