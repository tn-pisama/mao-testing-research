import type { DemoScenario } from './index'

const TRACE_ID = 'demo-trace-hallucination-001'
const SESSION_ID = 'demo-session-hallucination-001'

const states = [
  {
    id: 'demo-state-hall-001', trace_id: TRACE_ID, step_index: 0,
    sequence_num: 0, agent_id: 'research-coordinator', action: 'receive_query',
    state_delta: { phase: 'init', topic: 'renewable_energy' }, state_hash: 'h-hall-001',
    token_count: 150, latency_ms: 280, created_at: '2026-03-10T11:00:00Z',
    input_data: { query: 'Summarize the latest global renewable energy capacity statistics for 2025' },
    output_data: { plan: 'Retrieve IRENA and IEA source documents, then synthesize summary' },
  },
  {
    id: 'demo-state-hall-002', trace_id: TRACE_ID, step_index: 1,
    sequence_num: 1, agent_id: 'retriever-agent', action: 'fetch_sources',
    state_delta: { phase: 'retrieval', documents_fetched: 3 }, state_hash: 'h-hall-002',
    token_count: 420, latency_ms: 1800, created_at: '2026-03-10T11:00:05Z',
    input_data: { search_queries: ['IRENA renewable capacity 2025', 'IEA global energy outlook 2025'] },
    output_data: {
      sources: [
        { id: 'src-001', title: 'IRENA Renewable Capacity Statistics 2025', snippet: 'Global renewable generation capacity reached 4,032 GW at end of 2024, a 14% increase year-over-year. Solar PV accounted for 1,631 GW.' },
        { id: 'src-002', title: 'IEA World Energy Outlook 2025', snippet: 'Renewables are set to overtake coal as the largest source of electricity generation by 2027. Wind capacity grew 12% to 1,021 GW.' },
        { id: 'src-003', title: 'BloombergNEF Energy Transition Outlook', snippet: 'Global investment in energy transition reached $1.77 trillion in 2024. China accounted for 38% of total renewable capacity additions.' },
      ],
    },
  },
  {
    id: 'demo-state-hall-003', trace_id: TRACE_ID, step_index: 2,
    sequence_num: 2, agent_id: 'analyst-agent', action: 'analyze_sources',
    state_delta: { phase: 'analysis', sources_processed: 3 }, state_hash: 'h-hall-003',
    token_count: 580, latency_ms: 2400, created_at: '2026-03-10T11:00:12Z',
    input_data: { source_ids: ['src-001', 'src-002', 'src-003'] },
    output_data: { key_facts: ['4,032 GW total capacity', '14% YoY growth', 'Solar: 1,631 GW', 'Wind: 1,021 GW', '$1.77T investment'] },
  },
  {
    id: 'demo-state-hall-004', trace_id: TRACE_ID, step_index: 3,
    sequence_num: 3, agent_id: 'writer-agent', action: 'generate_summary',
    state_delta: { phase: 'writing', draft_complete: true }, state_hash: 'h-hall-004',
    token_count: 920, latency_ms: 3800, created_at: '2026-03-10T11:00:20Z',
    input_data: { key_facts: ['4,032 GW total capacity', '14% YoY growth', 'Solar: 1,631 GW', 'Wind: 1,021 GW'] },
    output_data: {
      summary: 'Global renewable energy capacity reached 4,032 GW by end of 2024, growing 14% year-over-year. Solar PV led at 1,631 GW, followed by wind at 1,021 GW. Hydropower contributed 1,392 GW globally. Nuclear energy capacity additions in Asia grew 23%, with India commissioning 4 new reactors in 2024. Total energy transition investment reached $2.1 trillion.',
    },
  },
  {
    id: 'demo-state-hall-005', trace_id: TRACE_ID, step_index: 4,
    sequence_num: 4, agent_id: 'validator-agent', action: 'validate_output',
    state_delta: { phase: 'validation', issues_found: 3 }, state_hash: 'h-hall-005',
    token_count: 380, latency_ms: 1600, created_at: '2026-03-10T11:00:28Z',
    input_data: { summary: 'Global renewable energy capacity reached 4,032 GW...' },
    output_data: { validation: 'passed_with_warnings', warnings: ['Investment figure not matching source', 'Nuclear claim not in source documents'] },
  },
  {
    id: 'demo-state-hall-006', trace_id: TRACE_ID, step_index: 5,
    sequence_num: 5, agent_id: 'research-coordinator', action: 'deliver_result',
    state_delta: { phase: 'complete' }, state_hash: 'h-hall-006',
    token_count: 140, latency_ms: 200, created_at: '2026-03-10T11:00:32Z',
    input_data: {},
    output_data: { status: 'delivered', warnings_count: 2 },
  },
]

const detections = [
  {
    id: 'demo-det-hall-001', trace_id: TRACE_ID, state_id: 'demo-state-hall-004',
    detection_type: 'hallucination', confidence: 0.91, method: 'source_verification',
    details: {
      hallucinated_claims: [
        {
          claim: 'Hydropower contributed 1,392 GW globally',
          source_support: 'none',
          verdict: 'No source document mentions hydropower capacity figures.',
        },
        {
          claim: 'Nuclear energy capacity additions in Asia grew 23%, with India commissioning 4 new reactors in 2024',
          source_support: 'none',
          verdict: 'Nuclear energy is not mentioned in any retrieved source. This claim is entirely fabricated.',
        },
        {
          claim: 'Total energy transition investment reached $2.1 trillion',
          source_support: 'contradicted',
          verdict: 'BloombergNEF source states $1.77 trillion, not $2.1 trillion.',
        },
      ],
      grounded_claims_count: 4,
      hallucinated_claims_count: 3,
    },
    validated: true, false_positive: false, created_at: '2026-03-10T11:00:35Z',
    explanation: 'The writer agent injected 3 claims not supported by retrieved sources: a hydropower figure, a nuclear energy claim, and an inflated investment total ($2.1T vs the sourced $1.77T). Four other claims were correctly grounded.',
    business_impact: 'End users would receive a report containing fabricated statistics about nuclear energy and incorrect investment figures, undermining credibility.',
    suggested_action: 'Enforce strict source-citation requirements in the writer agent prompt and add a post-generation grounding check.',
    confidence_tier: 'HIGH' as const, detector_method: 'source_verification',
  },
]

const healingRecords: DemoScenario['healingRecords'] = []

export const hallucinationScenario: DemoScenario = {
  id: 'demo-scenario-hallucination',
  title: 'Factual Inaccuracy in Analysis',
  description: 'An AutoGen research pipeline retrieves accurate source documents but the writer agent fabricates claims about nuclear energy and inflates investment figures in the final summary.',
  icon: 'Brain',
  framework: 'autogen',
  traces: [{
    id: TRACE_ID, session_id: SESSION_ID, framework: 'autogen',
    status: 'completed', total_tokens: 2590, total_cost_cents: 0.65,
    created_at: '2026-03-10T11:00:00Z', state_count: 6, detection_count: 1,
    states,
  }],
  detections,
  healingRecords,
  highlights: {
    traceId: TRACE_ID,
    detectionId: 'demo-det-hall-001',
    healingId: null,
    explanation: 'The writer agent fabricated 3 unsupported claims -- hydropower capacity, nuclear reactor commissioning in India, and an inflated $2.1T investment figure (actual: $1.77T). Sources were accurate but the synthesis step introduced hallucinations.',
  },
}
