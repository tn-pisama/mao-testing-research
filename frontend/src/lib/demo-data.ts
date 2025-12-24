import { AgentInfo, AgentStatus, ActivityEvent } from '@/components/agents'
import { Trace, State, Detection, LoopAnalytics, CostAnalytics } from './api'

const agentNames = [
  'Coordinator',
  'Researcher',
  'Analyzer',
  'Writer',
  'Validator',
  'Planner',
  'Executor',
  'Monitor',
]

const agentTypes: AgentInfo['type'][] = ['coordinator', 'worker', 'specialist', 'validator']

const taskTemplates = [
  'Analyzing user query for intent classification',
  'Searching knowledge base for relevant documents',
  'Generating response based on context',
  'Validating output against safety guidelines',
  'Coordinating sub-tasks between workers',
  'Executing API calls to external services',
  'Monitoring agent health and performance',
  'Planning optimal execution strategy',
]

const messageTemplates = [
  { type: 'task', content: 'Process user query: "{{query}}"' },
  { type: 'result', content: 'Found {{count}} relevant documents' },
  { type: 'delegation', content: 'Delegating research task to {{agent}}' },
  { type: 'error', content: 'Rate limit exceeded, retrying in {{seconds}}s' },
  { type: 'task', content: 'Generate summary for {{topic}}' },
  { type: 'result', content: 'Completed analysis with confidence {{confidence}}%' },
]

function randomId(): string {
  return Math.random().toString(36).substring(2, 15)
}

function randomChoice<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function randomDate(hoursAgo: number = 24): string {
  const date = new Date()
  date.setHours(date.getHours() - Math.random() * hoursAgo)
  return date.toISOString()
}

export function generateDemoAgents(count: number = 6): AgentInfo[] {
  const statuses: AgentStatus[] = ['idle', 'running', 'completed', 'failed', 'waiting']
  const statusWeights = [0.2, 0.4, 0.25, 0.05, 0.1]

  return Array.from({ length: count }, (_, i) => {
    const rand = Math.random()
    let cumulative = 0
    let status: AgentStatus = 'idle'
    for (let j = 0; j < statuses.length; j++) {
      cumulative += statusWeights[j]
      if (rand <= cumulative) {
        status = statuses[j]
        break
      }
    }

    return {
      id: `agent-${i + 1}`,
      name: agentNames[i % agentNames.length],
      type: agentTypes[i % agentTypes.length],
      status,
      currentTask: status === 'running' ? randomChoice(taskTemplates) : undefined,
      tokensUsed: randomInt(100, 50000),
      latencyMs: randomInt(50, 2000),
      stepCount: randomInt(1, 50),
      errorCount: status === 'failed' ? randomInt(1, 5) : Math.random() > 0.8 ? randomInt(1, 2) : 0,
      lastActiveAt: randomDate(2),
    }
  })
}

export function generateDemoMessages(agents: AgentInfo[], count: number = 10): Array<{
  id: string
  from: string
  to: string
  type: 'task' | 'result' | 'error' | 'delegation'
  content: string
  timestamp: string
}> {
  return Array.from({ length: count }, () => {
    const fromAgent = randomChoice(agents)
    let toAgent = randomChoice(agents)
    while (toAgent.id === fromAgent.id && agents.length > 1) {
      toAgent = randomChoice(agents)
    }

    const template = randomChoice(messageTemplates)
    let content = template.content
      .replace('{{query}}', randomChoice(['What is AI?', 'Explain quantum computing', 'Summarize this article']))
      .replace('{{count}}', String(randomInt(1, 50)))
      .replace('{{agent}}', toAgent.name)
      .replace('{{seconds}}', String(randomInt(1, 30)))
      .replace('{{topic}}', randomChoice(['machine learning', 'data analysis', 'API response']))
      .replace('{{confidence}}', String(randomInt(70, 99)))

    return {
      id: randomId(),
      from: fromAgent.id,
      to: toAgent.id,
      type: template.type as 'task' | 'result' | 'error' | 'delegation',
      content,
      timestamp: randomDate(1),
    }
  })
}

export function generateDemoActivityEvents(agents: AgentInfo[], count: number = 20): ActivityEvent[] {
  const eventTypes: ActivityEvent['type'][] = [
    'started',
    'completed',
    'failed',
    'message_sent',
    'message_received',
    'thinking',
    'tool_call',
  ]

  const contentTemplates: Record<ActivityEvent['type'], string[]> = {
    started: ['Initialized with task parameters', 'Beginning execution phase', 'Starting new workflow'],
    completed: ['Successfully processed request', 'Finished analysis with 98% confidence', 'Task completed'],
    failed: ['Connection timeout after 30s', 'Rate limit exceeded', 'Invalid response format'],
    message_sent: ['Sending results to Coordinator', 'Forwarding query to Researcher', 'Dispatching subtask'],
    message_received: ['Received task from Coordinator', 'Got response from API', 'Incoming delegation request'],
    thinking: ['Analyzing input parameters...', 'Processing context window...', 'Evaluating options...'],
    tool_call: ['Calling search_documents()', 'Invoking generate_response()', 'Executing validate()'],
  }

  const events: ActivityEvent[] = []
  let timestamp = new Date()

  for (let i = 0; i < count; i++) {
    const agent = randomChoice(agents)
    const type = randomChoice(eventTypes)
    timestamp = new Date(timestamp.getTime() - randomInt(1000, 60000))

    events.push({
      id: randomId(),
      agentId: agent.id,
      agentName: agent.name,
      type,
      content: randomChoice(contentTemplates[type]),
      timestamp: timestamp.toISOString(),
      metadata: type === 'tool_call' ? { function: 'search', args: { query: 'test' } } : undefined,
    })
  }

  return events.reverse()
}

export function generateDemoTraces(count: number = 10): Trace[] {
  const frameworks = ['langgraph', 'autogen', 'crewai', 'custom']
  const statuses = ['completed', 'running', 'failed']

  return Array.from({ length: count }, () => ({
    id: randomId(),
    session_id: `session-${randomId()}`,
    framework: randomChoice(frameworks),
    status: randomChoice(statuses),
    total_tokens: randomInt(1000, 100000),
    total_cost_cents: randomInt(10, 500),
    created_at: randomDate(48),
    completed_at: Math.random() > 0.3 ? randomDate(24) : undefined,
    state_count: randomInt(5, 100),
    detection_count: randomInt(0, 5),
  }))
}

export function generateDemoStates(traceId: string, count: number = 20): State[] {
  const agentIds = ['coordinator', 'researcher', 'analyzer', 'writer']

  return Array.from({ length: count }, (_, i) => ({
    id: randomId(),
    sequence_num: i + 1,
    agent_id: randomChoice(agentIds),
    state_delta: {
      action: randomChoice(['query', 'search', 'analyze', 'generate', 'validate']),
      result: randomChoice(['success', 'partial', 'pending']),
    },
    state_hash: randomId(),
    token_count: randomInt(50, 2000),
    latency_ms: randomInt(100, 3000),
    created_at: randomDate(2),
  }))
}

export function generateDemoDetections(count: number = 8): Detection[] {
  const types = ['infinite_loop', 'state_corruption', 'persona_drift', 'coordination_deadlock']
  const methods = ['structural_match', 'hash_collision', 'embedding_cluster', 'semantic_analysis']

  return Array.from({ length: count }, () => ({
    id: randomId(),
    trace_id: randomId(),
    state_id: Math.random() > 0.3 ? randomId() : undefined,
    detection_type: randomChoice(types),
    confidence: randomInt(60, 99) / 100,
    method: randomChoice(methods),
    details: {
      loop_length: randomInt(2, 10),
      affected_agents: randomInt(1, 4),
      severity: randomChoice(['low', 'medium', 'high', 'critical']),
    },
    validated: Math.random() > 0.5,
    false_positive: Math.random() > 0.8,
    created_at: randomDate(48),
  }))
}

export function generateDemoLoopAnalytics(): LoopAnalytics {
  const days = 30
  const timeSeries = Array.from({ length: days }, (_, i) => {
    const date = new Date()
    date.setDate(date.getDate() - (days - i - 1))
    return {
      date: date.toISOString().split('T')[0],
      count: randomInt(0, 15),
    }
  })

  return {
    total_loops_detected: timeSeries.reduce((sum, d) => sum + d.count, 0),
    loops_by_method: {
      structural_match: randomInt(20, 50),
      hash_collision: randomInt(10, 30),
      embedding_cluster: randomInt(5, 20),
    },
    avg_loop_length: randomInt(3, 8),
    top_agents_in_loops: [
      { agent_id: 'researcher', count: randomInt(10, 30) },
      { agent_id: 'analyzer', count: randomInt(5, 20) },
      { agent_id: 'writer', count: randomInt(2, 15) },
    ],
    time_series: timeSeries,
  }
}

export function generateDemoCostAnalytics(): CostAnalytics {
  const days = 30
  const costByDay = Array.from({ length: days }, (_, i) => {
    const date = new Date()
    date.setDate(date.getDate() - (days - i - 1))
    return {
      date: date.toISOString().split('T')[0],
      cost_cents: randomInt(50, 500),
    }
  })

  return {
    total_cost_cents: costByDay.reduce((sum, d) => sum + d.cost_cents, 0),
    total_tokens: randomInt(500000, 2000000),
    cost_by_framework: {
      langgraph: randomInt(1000, 5000),
      autogen: randomInt(500, 3000),
      crewai: randomInt(200, 1500),
    },
    cost_by_day: costByDay,
    top_expensive_traces: Array.from({ length: 5 }, () => ({
      trace_id: randomId(),
      session_id: `session-${randomId()}`,
      cost_cents: randomInt(100, 800),
      tokens: randomInt(10000, 80000),
    })),
  }
}

export function generateDemoAgentMetrics() {
  return {
    totalAgents: 8,
    activeAgents: randomInt(2, 6),
    totalTokens: randomInt(100000, 500000),
    avgLatencyMs: randomInt(200, 800),
    totalCostCents: randomInt(500, 2000),
    errorRate: randomInt(1, 10),
    loopsDetected: randomInt(0, 20),
    avgStepsPerTrace: randomInt(10, 40),
  }
}
