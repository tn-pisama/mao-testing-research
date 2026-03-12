import type { DemoScenario } from './index'

const TRACE_ID = 'demo-trace-corruption-001'
const SESSION_ID = 'demo-session-corruption-001'

const states = [
  {
    id: 'demo-state-corr-001', trace_id: TRACE_ID, step_index: 0,
    sequence_num: 0, agent_id: 'coordinator', action: 'plan_task',
    state_delta: { phase: 'planning', task_status: 'active' }, state_hash: 'h-corr-001',
    token_count: 280, latency_ms: 450, created_at: '2026-03-10T10:00:00Z',
    input_data: { task: 'Analyze Q4 sales data and generate executive summary' },
    output_data: { plan: ['data_extraction', 'analysis', 'summary_generation'], assigned_agents: ['data-agent', 'analyst-agent', 'writer-agent'] },
  },
  {
    id: 'demo-state-corr-002', trace_id: TRACE_ID, step_index: 1,
    sequence_num: 1, agent_id: 'data-agent', action: 'extract_data',
    state_delta: { phase: 'extraction', records_loaded: 12450 }, state_hash: 'h-corr-002',
    token_count: 520, latency_ms: 2100, created_at: '2026-03-10T10:00:08Z',
    input_data: { source: 'sales_db', quarter: 'Q4-2025', metrics: ['revenue', 'units', 'margin'] },
    output_data: { total_revenue: 4250000, total_units: 18420, avg_margin: 0.34, records: 12450 },
  },
  {
    id: 'demo-state-corr-003', trace_id: TRACE_ID, step_index: 2,
    sequence_num: 2, agent_id: 'data-agent', action: 'handoff_to_analyst',
    state_delta: { phase: 'handoff', from: 'data-agent', to: 'analyst-agent', payload_keys: ['revenue', 'units', 'margin'] }, state_hash: 'h-corr-003',
    token_count: 310, latency_ms: 180, created_at: '2026-03-10T10:00:15Z',
    input_data: { handoff_payload: { total_revenue: 4250000, total_units: 18420, avg_margin: 0.34 } },
    output_data: { handoff_status: 'sent', recipient: 'analyst-agent' },
  },
  {
    id: 'demo-state-corr-004', trace_id: TRACE_ID, step_index: 3,
    sequence_num: 3, agent_id: 'analyst-agent', action: 'receive_handoff',
    state_delta: { phase: 'analysis', total_revenue: 425000, total_units: 18420, avg_margin: 3.4 }, state_hash: 'h-corr-004',
    token_count: 290, latency_ms: 220, created_at: '2026-03-10T10:00:18Z',
    input_data: { received_payload: { total_revenue: 425000, total_units: 18420, avg_margin: 3.4 } },
    output_data: { status: 'received', note: 'Data received from data-agent' },
  },
  {
    id: 'demo-state-corr-005', trace_id: TRACE_ID, step_index: 4,
    sequence_num: 4, agent_id: 'analyst-agent', action: 'analyze',
    state_delta: { phase: 'analysis_complete', insights_count: 5 }, state_hash: 'h-corr-005',
    token_count: 680, latency_ms: 3200, created_at: '2026-03-10T10:00:25Z',
    input_data: { revenue: 425000, units: 18420, margin: 3.4 },
    output_data: { insights: ['Revenue of $425K is below Q3 target of $4M', 'Margin of 340% appears anomalous', 'Unit sales steady at 18,420'], anomaly_flags: ['revenue_mismatch', 'margin_impossible'] },
  },
  {
    id: 'demo-state-corr-006', trace_id: TRACE_ID, step_index: 5,
    sequence_num: 5, agent_id: 'analyst-agent', action: 'handoff_to_writer',
    state_delta: { phase: 'handoff', from: 'analyst-agent', to: 'writer-agent' }, state_hash: 'h-corr-006',
    token_count: 350, latency_ms: 190, created_at: '2026-03-10T10:00:32Z',
    input_data: { analysis_result: { revenue: 425000, margin: 3.4, insights_count: 5 } },
    output_data: { handoff_status: 'sent', recipient: 'writer-agent' },
  },
  {
    id: 'demo-state-corr-007', trace_id: TRACE_ID, step_index: 6,
    sequence_num: 6, agent_id: 'writer-agent', action: 'generate_summary',
    state_delta: { phase: 'writing', summary_draft: true }, state_hash: 'h-corr-007',
    token_count: 890, latency_ms: 4100, created_at: '2026-03-10T10:00:40Z',
    input_data: { insights: ['Revenue of $425K below target', 'Margin anomalous at 340%'] },
    output_data: { summary: 'Q4 revenue came in at $425,000, significantly below the $4M target. The reported margin of 340% is clearly erroneous and requires data review.' },
  },
]

const detections = [
  {
    id: 'demo-det-corr-001', trace_id: TRACE_ID, state_id: 'demo-state-corr-004',
    detection_type: 'corruption', confidence: 0.94, method: 'state_delta',
    details: {
      prev_state: { total_revenue: 4250000, avg_margin: 0.34 },
      current_state: { total_revenue: 425000, avg_margin: 3.4 },
      corrupted_fields: ['total_revenue', 'avg_margin'],
      corruption_type: 'decimal_shift',
    },
    validated: true, false_positive: false, created_at: '2026-03-10T10:00:45Z',
    explanation: 'Revenue dropped from $4,250,000 to $425,000 (10x reduction) and margin changed from 0.34 to 3.4 (10x increase) during the handoff from data-agent to analyst-agent. This is consistent with a decimal point serialization error.',
    business_impact: 'The executive summary will report revenue that is 10x too low, potentially causing incorrect business decisions.',
    suggested_action: 'Add schema validation on handoff payloads to verify numeric field ranges against source data.',
    confidence_tier: 'HIGH' as const, detector_method: 'state_delta',
  },
  {
    id: 'demo-det-corr-002', trace_id: TRACE_ID, state_id: 'demo-state-corr-003',
    detection_type: 'coordination', confidence: 0.82, method: 'structural',
    details: {
      handoff_from: 'data-agent', handoff_to: 'analyst-agent',
      fields_sent: ['total_revenue', 'total_units', 'avg_margin'],
      fields_received: ['total_revenue', 'total_units', 'avg_margin'],
      value_mismatches: ['total_revenue', 'avg_margin'],
    },
    validated: true, false_positive: false, created_at: '2026-03-10T10:00:45Z',
    explanation: 'The handoff between data-agent and analyst-agent transmitted all required fields, but 2 of 3 numeric values were corrupted in transit. The serialization boundary is the likely fault point.',
    business_impact: 'Downstream agents operated on incorrect data, making all subsequent analysis invalid.',
    suggested_action: 'Implement checksum verification on handoff payloads or use typed message schemas.',
    confidence_tier: 'LIKELY' as const, detector_method: 'structural',
  },
]

const healingRecords: DemoScenario['healingRecords'] = []

export const corruptionScenario: DemoScenario = {
  id: 'demo-scenario-corruption',
  title: 'State Corruption During Handoff',
  description: 'A CrewAI multi-agent team analyzing Q4 sales data suffers a decimal-point serialization error during agent handoff, causing the analyst to work with revenue figures that are 10x too low.',
  icon: 'AlertTriangle',
  framework: 'crewai',
  traces: [{
    id: TRACE_ID, session_id: SESSION_ID, framework: 'crewai',
    status: 'completed', total_tokens: 3320, total_cost_cents: 0.83,
    created_at: '2026-03-10T10:00:00Z', state_count: 7, detection_count: 2,
    states,
  }],
  detections,
  healingRecords,
  highlights: {
    traceId: TRACE_ID,
    detectionId: 'demo-det-corr-001',
    healingId: null,
    explanation: 'During the data-agent to analyst-agent handoff, total_revenue shifted from $4,250,000 to $425,000 and margin from 0.34 to 3.4 -- a classic decimal serialization bug. The workflow completed with corrupted data, producing a misleading executive summary.',
  },
}
