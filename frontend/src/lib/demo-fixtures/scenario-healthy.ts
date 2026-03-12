import type { DemoScenario } from './index'

const TRACE_ID = 'demo-trace-healthy-001'
const SESSION_ID = 'demo-session-healthy-001'

const states = [
  {
    id: 'demo-state-healthy-001', trace_id: TRACE_ID, step_index: 0,
    sequence_num: 0, agent_id: 'trigger-node', action: 'webhook_received',
    state_delta: { phase: 'trigger', workflow: 'customer-onboarding' }, state_hash: 'h-healthy-001',
    token_count: 0, latency_ms: 45, created_at: '2026-03-10T12:00:00Z',
    input_data: { webhook_payload: { customer_id: 'cust-8842', email: 'jane@acme.com', plan: 'enterprise' } },
    output_data: { status: 'triggered', next_node: 'enrich-customer' },
  },
  {
    id: 'demo-state-healthy-002', trace_id: TRACE_ID, step_index: 1,
    sequence_num: 1, agent_id: 'enrich-node', action: 'enrich_customer',
    state_delta: { phase: 'enrichment', customer_enriched: true }, state_hash: 'h-healthy-002',
    token_count: 320, latency_ms: 1200, created_at: '2026-03-10T12:00:02Z',
    input_data: { customer_id: 'cust-8842', email: 'jane@acme.com' },
    output_data: { company: 'Acme Corp', industry: 'SaaS', employee_count: 250, enrichment_source: 'clearbit' },
  },
  {
    id: 'demo-state-healthy-003', trace_id: TRACE_ID, step_index: 2,
    sequence_num: 2, agent_id: 'ai-node', action: 'generate_welcome',
    state_delta: { phase: 'content_generation', template: 'enterprise_welcome' }, state_hash: 'h-healthy-003',
    token_count: 580, latency_ms: 2800, created_at: '2026-03-10T12:00:05Z',
    input_data: { customer_name: 'Jane', company: 'Acme Corp', plan: 'enterprise' },
    output_data: { subject: 'Welcome to the Enterprise Plan, Jane', body: 'Hi Jane, welcome aboard! As an enterprise customer at Acme Corp, you have access to dedicated support and custom integrations...', tone_check: 'professional' },
  },
  {
    id: 'demo-state-healthy-004', trace_id: TRACE_ID, step_index: 3,
    sequence_num: 3, agent_id: 'email-node', action: 'send_email',
    state_delta: { phase: 'delivery', email_sent: true }, state_hash: 'h-healthy-004',
    token_count: 0, latency_ms: 650, created_at: '2026-03-10T12:00:09Z',
    input_data: { to: 'jane@acme.com', subject: 'Welcome to the Enterprise Plan, Jane', body: '...' },
    output_data: { message_id: 'msg-29481', delivery_status: 'sent', provider: 'sendgrid' },
  },
  {
    id: 'demo-state-healthy-005', trace_id: TRACE_ID, step_index: 4,
    sequence_num: 4, agent_id: 'crm-node', action: 'update_crm',
    state_delta: { phase: 'complete', crm_updated: true }, state_hash: 'h-healthy-005',
    token_count: 0, latency_ms: 380, created_at: '2026-03-10T12:00:11Z',
    input_data: { customer_id: 'cust-8842', status: 'onboarded', welcome_email_id: 'msg-29481' },
    output_data: { crm_record_id: 'sf-opp-11294', status: 'updated', pipeline_stage: 'onboarded' },
  },
]

export const healthyScenario: DemoScenario = {
  id: 'demo-scenario-healthy',
  title: 'Healthy Workflow Baseline',
  description: 'An n8n customer onboarding workflow runs correctly end-to-end: webhook trigger, customer enrichment, AI-generated welcome email, delivery, and CRM update with zero detections.',
  icon: 'CheckCircle',
  framework: 'n8n',
  traces: [{
    id: TRACE_ID, session_id: SESSION_ID, framework: 'n8n',
    status: 'completed', total_tokens: 900, total_cost_cents: 0.23,
    created_at: '2026-03-10T12:00:00Z', state_count: 5, detection_count: 0,
    states,
  }],
  detections: [],
  healingRecords: [],
  highlights: {
    traceId: TRACE_ID,
    detectionId: null,
    healingId: null,
    explanation: 'This workflow completed all 5 steps in 11 seconds with no anomalies detected. It serves as a healthy baseline showing what normal execution looks like -- useful for comparison against failure scenarios.',
  },
}
