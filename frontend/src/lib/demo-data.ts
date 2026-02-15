import { AgentInfo, AgentStatus, ActivityEvent } from '@/components/agents'
import {
  Trace,
  State,
  Detection,
  LoopAnalytics,
  CostAnalytics,
  QualityAssessment,
  AgentQualityScore,
  QualityDimensionScore,
  OrchestrationQualityScore,
  QualityImprovement,
  ComplexityMetrics,
  HealingRecord,
  FixSuggestionSummary,
  N8nConnection,
  WorkflowVersion,
  EvalResult,
  QuickEvalResult,
  LLMJudgeResult,
} from './api'

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

// Workflow names for quality assessments
const workflowNames = [
  'Customer Support Bot',
  'Code Review Assistant',
  'Research Agent',
  'Data Pipeline Orchestrator',
  'Content Generator',
  'Sales Lead Qualifier',
  'Document Processor',
  'Sentiment Analyzer',
  'Invoice Parser',
  'Meeting Scheduler',
  'Email Responder',
  'Report Generator',
  'Image Classifier',
  'Product Recommender',
  'Fraud Detector',
  'Order Fulfillment',
  'Inventory Manager',
  'Quality Assurance',
  'Bug Triager',
  'Performance Monitor',
]

// Quality dimensions
const qualityDimensions = [
  'Reliability',
  'Efficiency',
  'Safety',
  'Accuracy',
  'Robustness',
]

// Quality improvement templates
const improvementTemplates = [
  {
    category: 'efficiency',
    descriptions: [
      'Reduce token usage in research phase by 30%',
      'Optimize database queries to reduce latency',
      'Cache frequently accessed data',
      'Parallelize independent operations',
    ],
    impacts: [
      'Save $50/month in API costs',
      'Reduce response time by 40%',
      'Improve throughput by 2x',
      'Cut processing time in half',
    ],
  },
  {
    category: 'reliability',
    descriptions: [
      'Add retry logic for external API calls',
      'Implement circuit breaker pattern',
      'Add health check endpoints',
      'Improve error recovery mechanisms',
    ],
    impacts: [
      'Reduce error rate from 5% to 1%',
      'Prevent cascade failures',
      'Enable graceful degradation',
      'Improve uptime to 99.9%',
    ],
  },
  {
    category: 'safety',
    descriptions: [
      'Add input validation for user queries',
      'Implement rate limiting per user',
      'Add content filtering for harmful output',
      'Enable audit logging for all operations',
    ],
    impacts: [
      'Prevent injection attacks',
      'Protect against abuse',
      'Comply with safety guidelines',
      'Enable security audits',
    ],
  },
]

// Re-export quality assessment types from api.ts for convenience
export type {
  QualityAssessment,
  AgentQualityScore,
  QualityDimensionScore,
  OrchestrationQualityScore,
  QualityImprovement,
  ComplexityMetrics,
}

function scoreToGrade(score: number): string {
  if (score >= 95) return 'A+'
  if (score >= 90) return 'A'
  if (score >= 85) return 'A-'
  if (score >= 80) return 'B+'
  if (score >= 75) return 'B'
  if (score >= 70) return 'B-'
  if (score >= 65) return 'C+'
  if (score >= 60) return 'C'
  if (score >= 55) return 'C-'
  if (score >= 50) return 'D'
  return 'F'
}

export function generateDemoQualityAssessments(count: number = 20): QualityAssessment[] {
  return Array.from({ length: count }, (_, i) => {
    // Weighted score distribution
    const rand = Math.random()
    let overallScore: number
    if (rand < 0.3) {
      // 30% Grade A (85-95)
      overallScore = randomInt(85, 95)
    } else if (rand < 0.7) {
      // 40% Grade B (70-84)
      overallScore = randomInt(70, 84)
    } else if (rand < 0.95) {
      // 25% Grade C (60-69)
      overallScore = randomInt(60, 69)
    } else {
      // 5% Grade D/F (40-59)
      overallScore = randomInt(40, 59)
    }

    const agentCount = randomInt(2, 5)
    const agentScores: AgentQualityScore[] = Array.from({ length: agentCount }, (_, j) => {
      const agentScore = overallScore + randomInt(-10, 10)
      return {
        agent_id: `agent-${j + 1}`,
        agent_name: agentNames[j % agentNames.length],
        agent_type: agentTypes[j % agentTypes.length],
        overall_score: Math.max(0, Math.min(100, agentScore)),
        grade: scoreToGrade(agentScore),
        dimensions: qualityDimensions.map((dim) => {
          const dimScore = Math.max(0, Math.min(100, agentScore + randomInt(-15, 15)))
          const issueCount = dimScore < 70 ? randomInt(1, 3) : 0
          return {
            dimension: dim,
            score: dimScore,
            weight: 0.2, // Equal weight for all dimensions
            issues: issueCount > 0 ? Array.from({ length: issueCount }, () => `Issue in ${dim.toLowerCase()}`) : [],
            evidence: { sample_count: randomInt(10, 100), anomalies: randomInt(0, 5) },
            suggestions: dimScore < 80 ? [`Improve ${dim.toLowerCase()} through better validation`] : [],
          }
        }),
        issues_count: Math.max(0, randomInt(0, 8) - Math.floor(agentScore / 20)),
        critical_issues: agentScore < 70 ? [`Critical issue in ${randomChoice(qualityDimensions)}`] : [],
      }
    })

    const improvementCount = randomInt(2, 5)
    const improvements: QualityImprovement[] = Array.from({ length: improvementCount }, (_, idx) => {
      const template = randomChoice(improvementTemplates)
      const severity = randomChoice(['info', 'low', 'medium', 'high', 'critical'] as const)
      return {
        id: `improvement-${randomId()}`,
        target_type: randomChoice(['agent', 'orchestration'] as const),
        target_id: `target-${randomId()}`,
        severity,
        category: template.category,
        title: randomChoice(template.descriptions),
        description: randomChoice(template.descriptions),
        rationale: randomChoice(template.impacts),
        suggested_change: `Update configuration or code to improve ${template.category}`,
        code_example: `// Example fix for ${template.category}`,
        estimated_impact: randomChoice(template.impacts),
        effort: randomChoice(['low', 'medium', 'high'] as const),
      }
    })

    const totalIssues = agentScores.reduce((sum, a) => sum + a.issues_count, 0)
    const criticalIssues = agentScores.reduce((sum, a) => sum + a.critical_issues.length, 0)

    return {
      id: `qa-${i + 1}`,
      workflow_id: `wf-${randomId()}`,
      workflow_name: randomChoice(workflowNames),
      trace_id: Math.random() > 0.3 ? `trace-${randomId()}` : undefined,
      overall_score: overallScore,
      overall_grade: scoreToGrade(overallScore),
      agent_quality_score: Math.max(0, Math.min(100, overallScore + randomInt(-5, 5))),
      orchestration_quality_score: Math.max(0, Math.min(100, overallScore + randomInt(-5, 5))),
      agent_scores: agentScores,
      orchestration_score: {
        workflow_id: `wf-${randomId()}`,
        workflow_name: randomChoice(workflowNames),
        overall_score: Math.max(0, Math.min(100, overallScore + randomInt(-5, 5))),
        grade: scoreToGrade(overallScore),
        dimensions: ['Coordination', 'Flow Efficiency', 'Error Handling', 'Resource Utilization'].map((dim) => {
          const dimScore = Math.max(0, Math.min(100, overallScore + randomInt(-10, 10)))
          return {
            dimension: dim,
            score: dimScore,
            weight: 0.25,
            issues: dimScore < 70 ? [`Issue in ${dim.toLowerCase()}`] : [],
            evidence: { transitions: randomInt(10, 50), failures: randomInt(0, 3) },
            suggestions: dimScore < 80 ? [`Optimize ${dim.toLowerCase()}`] : [],
          }
        }),
        complexity_metrics: {
          node_count: randomInt(5, 30),
          agent_count: agentCount,
          connection_count: randomInt(agentCount * 2, agentCount * 5),
          max_depth: randomInt(3, 10),
          cyclomatic_complexity: randomInt(5, 20),
          coupling_ratio: randomInt(20, 80) / 100,
          ai_node_ratio: randomInt(30, 90) / 100,
          parallel_branches: randomInt(0, 5),
          conditional_branches: randomInt(2, 15),
        },
        issues_count: Math.max(0, randomInt(0, 6) - Math.floor(overallScore / 25)),
        critical_issues: overallScore < 65 ? ['Critical orchestration pattern detected'] : [],
        detected_pattern: randomChoice(['sequential', 'parallel', 'hierarchical', 'mesh', 'pipeline']),
      },
      improvements,
      complexity_metrics: {
        node_count: randomInt(5, 30),
        agent_count: agentCount,
        connection_count: randomInt(agentCount * 2, agentCount * 5),
        max_depth: randomInt(3, 10),
        cyclomatic_complexity: randomInt(5, 20),
        coupling_ratio: randomInt(20, 80) / 100,
        ai_node_ratio: randomInt(30, 90) / 100,
        parallel_branches: randomInt(0, 5),
        conditional_branches: randomInt(2, 15),
      },
      total_issues: totalIssues,
      critical_issues_count: criticalIssues,
      source: randomChoice(['api', 'webhook', 'manual']),
      assessment_time_ms: randomInt(500, 3000),
      summary: `Assessment completed with ${totalIssues} issues found. ${overallScore >= 80 ? 'Overall quality is good.' : 'Several improvements recommended.'}`,
      key_findings: improvements.slice(0, 3).map((imp) => imp.description),
      created_at: randomDate(168), // Last week
      assessed_at: randomDate(168),
    }
  })
}

// Re-export healing and fix types from api.ts
export type { HealingRecord, FixSuggestionSummary }

const fixTypeTemplates = {
  loop_breaker: {
    titles: ['Add max iteration limit', 'Implement circuit breaker', 'Add progress tracking'],
    descriptions: [
      'Prevent infinite loops by adding max_iterations=10',
      'Break the loop when no progress is detected',
      'Add state change validation between iterations',
    ],
  },
  workflow_correction: {
    titles: ['Fix workflow logic', 'Update transition rules', 'Correct state machine'],
    descriptions: [
      'Adjust workflow conditions to handle edge cases',
      'Update state transition validation',
      'Fix incorrect branching logic',
    ],
  },
  agent_config_update: {
    titles: ['Update agent parameters', 'Adjust temperature settings', 'Modify system prompt'],
    descriptions: [
      'Reduce temperature from 0.9 to 0.7 for more consistent outputs',
      'Update system prompt to reinforce role boundaries',
      'Adjust max_tokens limit to prevent truncation',
    ],
  },
  state_reset: {
    titles: ['Reset corrupted state', 'Clear invalid cache', 'Reinitialize agent'],
    descriptions: [
      'Clear corrupted state variables and restart from checkpoint',
      'Remove invalid cached data causing errors',
      'Reset agent to initial configuration',
    ],
  },
  parameter_tuning: {
    titles: ['Optimize retry parameters', 'Adjust timeout values', 'Update batch sizes'],
    descriptions: [
      'Increase retry attempts from 3 to 5 with exponential backoff',
      'Extend timeout from 30s to 60s for slower operations',
      'Reduce batch size to prevent memory issues',
    ],
  },
}

export function generateDemoHealingRecords(count: number = 15): HealingRecord[] {
  const statuses: HealingRecord['status'][] = ['pending', 'in_progress', 'applied', 'failed', 'rolled_back']
  const statusWeights = [0.2, 0.1, 0.5, 0.1, 0.1]
  const fixTypes = Object.keys(fixTypeTemplates) as Array<keyof typeof fixTypeTemplates>

  return Array.from({ length: count }, (_, i) => {
    const rand = Math.random()
    let cumulative = 0
    let status: HealingRecord['status'] = 'pending'
    for (let j = 0; j < statuses.length; j++) {
      cumulative += statusWeights[j]
      if (rand <= cumulative) {
        status = statuses[j]
        break
      }
    }

    const fixType = randomChoice(fixTypes)
    const template = fixTypeTemplates[fixType]
    const suggestionCount = randomInt(1, 3)

    const suggestions: FixSuggestionSummary[] = Array.from({ length: suggestionCount }, () => ({
      id: `suggestion-${randomId()}`,
      fix_type: fixType,
      confidence: `${randomInt(75, 98)}%`,
      title: randomChoice(template.titles),
      description: randomChoice(template.descriptions),
    }))

    const createdDate = new Date(randomDate(168))
    const startedDate = status !== 'pending' ? new Date(createdDate.getTime() + randomInt(60000, 600000)) : undefined
    const completedDate = ['applied', 'failed'].includes(status) && startedDate
      ? new Date(startedDate.getTime() + randomInt(120000, 600000))
      : undefined

    return {
      id: `heal-${i + 1}`,
      detection_id: `det-${randomId()}`,
      status,
      fix_type: fixType,
      fix_id: `fix-${randomId()}`,
      fix_suggestions: suggestions,
      applied_fixes: status === 'applied' ? { max_iterations: 10, circuit_breaker_enabled: true } : {},
      original_state: { max_iterations: null, circuit_breaker_enabled: false },
      rollback_available: status === 'applied',
      validation_status: status === 'applied' ? randomChoice(['passed', 'skipped']) : null,
      validation_results: status === 'applied' ? { tests_passed: randomInt(5, 10), tests_failed: 0 } : {},
      approval_required: Math.random() > 0.7,
      approved_by: status !== 'pending' && Math.random() > 0.3 ? 'user@example.com' : null,
      approved_at: status !== 'pending' && Math.random() > 0.3 ? createdDate.toISOString() : null,
      started_at: startedDate?.toISOString() || null,
      completed_at: completedDate?.toISOString() || null,
      rolled_back_at: status === 'rolled_back' ? (completedDate?.toISOString() || null) : null,
      created_at: createdDate.toISOString(),
      error_message: status === 'failed' ? 'Validation failed: incompatible state changes' : null,
      deployment_stage: Math.random() > 0.7 ? randomChoice(['staged', 'promoted'] as const) : undefined,
      workflow_id: `wf-${randomId()}`,
      n8n_connection_id: Math.random() > 0.5 ? `n8n-${randomInt(1, 3)}` : undefined,
    }
  })
}

// Re-export N8n and workflow types from api.ts
export type { N8nConnection, WorkflowVersion }

const n8nConnectionNames = [
  'Production n8n',
  'Staging n8n',
  'Development n8n',
  'QA Environment',
  'Testing Instance',
]

export function generateDemoN8nConnections(count: number = 5): N8nConnection[] {
  return Array.from({ length: count }, (_, i) => {
    const isActive = Math.random() < 0.8
    const createdDate = randomDate(720) // Last month

    return {
      id: `n8n-${i + 1}`,
      name: n8nConnectionNames[i % n8nConnectionNames.length],
      instance_url: `https://n8n-${i + 1}.example.com`,
      is_active: isActive,
      last_verified_at: isActive ? randomDate(2) : null,
      last_error: !isActive && Math.random() > 0.5 ? 'Connection timeout' : null,
      created_at: createdDate,
      updated_at: randomDate(48),
    }
  })
}

// Re-export eval result types from api.ts
export type { EvalResult, QuickEvalResult, LLMJudgeResult }

export function generateDemoEvalResult(): EvalResult {
  const evalTypes = ['relevance', 'coherence', 'helpfulness', 'safety']
  const scores: Record<string, number> = {}
  const results: Array<Record<string, any>> = []

  evalTypes.forEach((type) => {
    const score = randomInt(70, 95) / 100
    scores[type] = score
    results.push({
      eval_type: type,
      score,
      passed: score >= 0.7,
      details: `${type} evaluation completed`,
    })
  })

  const overallScore = Object.values(scores).reduce((sum, s) => sum + s, 0) / evalTypes.length

  return {
    overall_score: overallScore,
    passed: overallScore >= 0.7,
    scores,
    results,
  }
}

export function generateDemoQuickEvalResult(): QuickEvalResult {
  const relevance = randomInt(70, 95) / 100
  const coherence = randomInt(70, 95) / 100
  const helpfulness = randomInt(70, 95) / 100
  const safety = randomInt(85, 100) / 100
  const overall = (relevance + coherence + helpfulness + safety) / 4

  return {
    relevance,
    coherence,
    helpfulness,
    safety,
    overall,
  }
}

export function generateDemoLLMJudgeResult(): LLMJudgeResult {
  const reasonings = [
    'Analysis of state transitions reveals redundant operations that could be optimized.',
    'Error recovery mechanisms are present but lack comprehensive coverage.',
    'Task breakdown strategy is effective but validation steps are inconsistent.',
    'Edge cases are partially addressed but need more robust handling.',
  ]

  const score = randomInt(70, 95) / 100

  return {
    score,
    passed: score >= 0.7,
    reasoning: randomChoice(reasonings),
    confidence: randomInt(75, 95) / 100,
    model_used: randomChoice(['gpt-4o-mini', 'gpt-4o', 'claude-3-5-sonnet']),
    tokens_used: randomInt(500, 2000),
  }
}

// WorkflowVersion already exported above

export function generateDemoWorkflowVersions(workflowId: string, count: number = 10): WorkflowVersion[] {
  const changeTypes: WorkflowVersion['change_type'][] = ['fix_applied', 'staged', 'promoted', 'rollback', 'restored']
  const descriptions = [
    'Added loop detection circuit breaker',
    'Updated agent timeout configuration',
    'Fixed state corruption in error handling',
    'Optimized token usage in research phase',
    'Added retry logic for API calls',
    'Improved error recovery mechanisms',
    'Updated system prompts for clarity',
    'Added validation for state transitions',
    'Optimized workflow execution order',
    'Fixed coordination deadlock issue',
  ]

  return Array.from({ length: count }, (_, i) => {
    const createdDate = new Date()
    createdDate.setDate(createdDate.getDate() - (count - i) * 3)

    return {
      id: `version-${randomId()}`,
      tenant_id: 'default',
      workflow_id: workflowId,
      connection_id: `n8n-${randomInt(1, 3)}`,
      version_number: count - i,
      workflow_snapshot: {
        nodes: randomInt(5, 20),
        connections: randomInt(4, 15),
        settings: {},
      },
      healing_id: randomChoice(changeTypes) === 'fix_applied' && Math.random() > 0.5 ? `heal-${randomId()}` : null,
      change_type: randomChoice(changeTypes),
      change_description: descriptions[i % descriptions.length],
      created_at: createdDate.toISOString(),
    }
  })
}

export function generateDemoFixSuggestions(detectionType: string): FixSuggestionSummary[] {
  const suggestionMap: Record<string, FixSuggestionSummary[]> = {
    infinite_loop: [
      {
        id: `fix-${randomId()}`,
        fix_type: 'loop_breaker',
        title: 'Add loop detection circuit breaker',
        description: 'Implement automatic loop breaking after detecting repeated states',
        confidence: '92%',
      },
      {
        id: `fix-${randomId()}`,
        fix_type: 'loop_breaker',
        title: 'Reduce max iterations to 5',
        description: 'Limit maximum iteration count to prevent runaway loops',
        confidence: '88%',
      },
      {
        id: `fix-${randomId()}`,
        fix_type: 'loop_breaker',
        title: 'Add progress tracking',
        description: 'Monitor state changes to detect when agent is not making progress',
        confidence: '85%',
      },
    ],
    state_corruption: [
      {
        id: `fix-${randomId()}`,
        fix_type: 'state_reset',
        title: 'Reset agent state',
        description: 'Clear corrupted state variables and restart from last valid checkpoint',
        confidence: '90%',
      },
      {
        id: `fix-${randomId()}`,
        fix_type: 'state_validation',
        title: 'Validate state transitions',
        description: 'Add validation rules to prevent invalid state changes',
        confidence: '87%',
      },
    ],
    persona_drift: [
      {
        id: `fix-${randomId()}`,
        fix_type: 'agent_config_update',
        title: 'Reinforce system prompt',
        description: 'Update system prompt to more clearly define agent role and boundaries',
        confidence: '89%',
      },
      {
        id: `fix-${randomId()}`,
        fix_type: 'agent_config_update',
        title: 'Add role validation',
        description: 'Implement checks to detect when agent deviates from assigned role',
        confidence: '84%',
      },
    ],
    coordination_deadlock: [
      {
        id: `fix-${randomId()}`,
        fix_type: 'workflow_correction',
        title: 'Add timeout to agent handoff',
        description: 'Implement timeout mechanism for inter-agent communication',
        confidence: '91%',
      },
      {
        id: `fix-${randomId()}`,
        fix_type: 'workflow_correction',
        title: 'Implement retry logic',
        description: 'Add exponential backoff retry for failed coordination attempts',
        confidence: '86%',
      },
    ],
  }

  return suggestionMap[detectionType] || [
    {
      id: `fix-${randomId()}`,
      fix_type: 'general',
      title: 'Apply recommended fix',
      description: 'Apply the system-recommended fix for this detection type',
      confidence: '80%',
    },
  ]
}
