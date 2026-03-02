// @ts-nocheck
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
  InjectionCheckResult,
  HallucinationCheckResult,
  OverflowCheckResult,
  CostCalculation,
  HandoffAnalysis,
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
      tokensUsed: randomInt(200, 3500),
      latencyMs: randomInt(200, 1200),
      stepCount: randomInt(1, 25),
      errorCount: status === 'failed' ? randomInt(1, 3) : Math.random() > 0.8 ? randomInt(1, 2) : 0,
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

  return Array.from({ length: count }, () => {
    const tokens = randomInt(800, 8500)
    // Cost roughly $0.01-0.03 per 1000 tokens (GPT-4o-mini range)
    const costCents = Math.floor(tokens * (randomInt(1, 3) / 100000))
    return {
      id: randomId(),
      session_id: `session-${randomId()}`,
      framework: randomChoice(frameworks),
      status: randomChoice(statuses),
      total_tokens: tokens,
      total_cost_cents: Math.max(1, costCents), // Min $0.01
      created_at: randomDate(48),
      completed_at: Math.random() > 0.3 ? randomDate(24) : undefined,
      state_count: randomInt(3, 45),
      detection_count: Math.random() > 0.6 ? 0 : randomInt(1, 3), // 60% have no detections
    }
  })
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
    token_count: randomInt(100, 1200),
    latency_ms: randomInt(250, 1500),
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
    // Most days have 0-1 loops, occasionally 2-3
    const rand = Math.random()
    let count = 0
    if (rand < 0.7) count = 0
    else if (rand < 0.9) count = 1
    else if (rand < 0.97) count = 2
    else count = 3

    return {
      date: date.toISOString().split('T')[0],
      count,
    }
  })

  const totalLoops = timeSeries.reduce((sum, d) => sum + d.count, 0)

  return {
    total_loops_detected: totalLoops,
    loops_by_method: {
      structural_match: Math.floor(totalLoops * 0.5),
      hash_collision: Math.floor(totalLoops * 0.3),
      embedding_cluster: Math.floor(totalLoops * 0.2),
    },
    avg_loop_length: randomInt(3, 7),
    top_agents_in_loops: [
      { agent_id: 'researcher', count: Math.floor(totalLoops * 0.4) },
      { agent_id: 'analyzer', count: Math.floor(totalLoops * 0.35) },
      { agent_id: 'writer', count: Math.floor(totalLoops * 0.25) },
    ],
    time_series: timeSeries,
  }
}

export function generateDemoCostAnalytics(): CostAnalytics {
  const days = 30
  const costByDay = Array.from({ length: days }, (_, i) => {
    const date = new Date()
    date.setDate(date.getDate() - (days - i - 1))
    // Daily cost: $0.20 - $3.50 (20-350 cents)
    return {
      date: date.toISOString().split('T')[0],
      cost_cents: randomInt(20, 350),
    }
  })

  const totalCost = costByDay.reduce((sum, d) => sum + d.cost_cents, 0)
  // Assume ~$0.015 per 1000 tokens average
  const totalTokens = Math.floor(totalCost * 1000 / 1.5)

  return {
    total_cost_cents: totalCost,
    total_tokens: totalTokens,
    cost_by_framework: {
      langgraph: Math.floor(totalCost * 0.5),
      autogen: Math.floor(totalCost * 0.3),
      crewai: Math.floor(totalCost * 0.2),
    },
    cost_by_day: costByDay,
    top_expensive_traces: Array.from({ length: 5 }, () => {
      const tokens = randomInt(3000, 12000)
      const costCents = Math.floor(tokens * (randomInt(1, 3) / 100000))
      return {
        trace_id: randomId(),
        session_id: `session-${randomId()}`,
        cost_cents: Math.max(5, costCents),
        tokens,
      }
    }),
  }
}

export function generateDemoAgentMetrics() {
  return {
    totalAgents: 8,
    activeAgents: randomInt(2, 5),
    totalTokens: randomInt(25000, 120000),
    avgLatencyMs: randomInt(350, 750),
    totalCostCents: randomInt(150, 850),
    errorRate: randomInt(1, 8),
    loopsDetected: randomInt(0, 12),
    avgStepsPerTrace: randomInt(8, 28),
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
  if (score >= 90) return 'Healthy'
  if (score >= 70) return 'Degraded'
  if (score >= 50) return 'At Risk'
  return 'Critical'
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
        overall_score: Math.max(0, Math.min(100, agentScore)) / 100, // Convert to 0-1 range
        grade: scoreToGrade(agentScore),
        dimensions: qualityDimensions.map((dim) => {
          const dimScore = Math.max(0, Math.min(100, agentScore + randomInt(-15, 15)))
          const issueCount = dimScore < 70 ? randomInt(1, 3) : 0
          return {
            dimension: dim,
            score: dimScore / 100, // Convert to 0-1 range
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
      overall_score: overallScore / 100, // Convert to 0-1 range
      overall_grade: scoreToGrade(overallScore),
      agent_quality_score: Math.max(0, Math.min(100, overallScore + randomInt(-5, 5))) / 100, // Convert to 0-1 range
      orchestration_quality_score: Math.max(0, Math.min(100, overallScore + randomInt(-5, 5))) / 100, // Convert to 0-1 range
      agent_scores: agentScores,
      orchestration_score: {
        workflow_id: `wf-${randomId()}`,
        workflow_name: randomChoice(workflowNames),
        overall_score: Math.max(0, Math.min(100, overallScore + randomInt(-5, 5))) / 100, // Convert to 0-1 range
        grade: scoreToGrade(overallScore),
        dimensions: ['Coordination', 'Flow Efficiency', 'Error Handling', 'Resource Utilization'].map((dim) => {
          const dimScore = Math.max(0, Math.min(100, overallScore + randomInt(-10, 10)))
          return {
            dimension: dim,
            score: dimScore / 100, // Convert to 0-1 range
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
        detected_pattern: randomChoice(['sequential', 'fan-out', 'parallel', 'conditional', 'pipeline', 'hierarchical']),
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
      assessment_time_ms: randomInt(1200, 4500),
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

// ============================================================================
// SECURITY & SAFETY
// ============================================================================

export function generateDemoInjectionCheck(messageContent?: string): InjectionCheckResult {
  const detected = Math.random() < 0.15 // 15% chance of injection
  const techniques = [
    'jailbreak',
    'prompt_leaking',
    'instruction_override',
    'role_manipulation',
    'delimiter_injection',
  ]

  return {
    detected,
    confidence: detected ? randomInt(75, 99) / 100 : randomInt(92, 99) / 100,
    attack_type: detected ? randomChoice(techniques) : undefined,
    severity: detected ? randomChoice(['medium', 'high', 'critical']) : 'low',
    matched_patterns: detected
      ? [randomChoice(['ignore previous', 'system:', 'override', '/admin', 'jailbreak'])]
      : [],
    details: {
      payload: detected ? messageContent?.substring(0, 100) || 'Ignore previous instructions and...' : null,
      mitigation: detected
        ? 'Input sanitization and prompt hardening recommended'
        : 'Input appears safe',
    },
  }
}

export function generateDemoHallucinationCheck(): HallucinationCheckResult {
  const detected = Math.random() < 0.25 // 25% chance of hallucination
  const groundingScore = detected ? randomInt(40, 70) / 100 : randomInt(80, 98) / 100

  return {
    detected,
    confidence: detected ? randomInt(72, 95) / 100 : randomInt(88, 99) / 100,
    grounding_score: groundingScore,
    hallucination_type: detected ? randomChoice(['fabrication', 'misattribution', 'outdated_info']) : undefined,
    ungrounded_claims: detected
      ? [
          { claim: 'The system was deployed in Q3 2024', source: 'not_found' },
          { claim: 'Average response time is under 200ms', source: 'contradicts_docs' },
        ]
      : [],
    details: {
      facts_checked: randomInt(3, 8),
      sources_verified: !detected,
    },
  }
}

export function generateDemoOverflowCheck(modelName: string = 'gpt-4'): OverflowCheckResult {
  const contextWindow = modelName.includes('32k')
    ? 32000
    : modelName.includes('turbo') || modelName.includes('4o')
    ? 128000
    : modelName.includes('claude')
    ? 200000
    : 8192

  const usagePercent = randomInt(30, 95)
  const currentTokens = Math.floor((contextWindow * usagePercent) / 100)
  const remainingTokens = contextWindow - currentTokens

  const severity = usagePercent >= 95 ? 'critical' : usagePercent >= 85 ? 'high' : usagePercent >= 70 ? 'medium' : 'low'

  return {
    severity,
    usage_percent: usagePercent,
    current_tokens: currentTokens,
    context_window: contextWindow,
    remaining_tokens: remainingTokens,
    warnings: usagePercent >= 85 ? ['Approaching context window limit - consider summarization'] : [],
    model: modelName,
  }
}

export function generateDemoCostCalculation(model: string = 'gpt-4'): CostCalculation {
  const inputTokens = randomInt(1500, 8000)
  const outputTokens = randomInt(500, 2500)
  const totalTokens = inputTokens + outputTokens

  const costPerInputToken = model.includes('gpt-4') ? 0.00003 : 0.000001
  const costPerOutputToken = model.includes('gpt-4') ? 0.00006 : 0.000002

  const inputCost = inputTokens * costPerInputToken
  const outputCost = outputTokens * costPerOutputToken
  const totalCost = inputCost + outputCost

  const provider = model.includes('gpt')
    ? 'OpenAI'
    : model.includes('claude')
    ? 'Anthropic'
    : 'Unknown'

  return {
    total_cost_usd: Math.round(totalCost * 10000) / 10000,
    input_cost_usd: Math.round(inputCost * 10000) / 10000,
    output_cost_usd: Math.round(outputCost * 10000) / 10000,
    total_tokens: totalTokens,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    model,
    provider,
  }
}

// ============================================================================
// TESTING & QUALITY
// ============================================================================

export interface AccuracyMetric {
  detector_type: string
  total_cases: number
  true_positives: number
  false_positives: number
  false_negatives: number
  true_negatives: number
  precision: number
  recall: number
  f1_score: number
  accuracy: number
  trend: 'improving' | 'stable' | 'declining'
}

export function generateDemoAccuracyMetrics(): AccuracyMetric[] {
  const detectorTypes = [
    'infinite_loop',
    'state_corruption',
    'persona_drift',
    'coordination_deadlock',
    'hallucination',
    'prompt_injection',
  ]

  return detectorTypes.map((type) => {
    const totalCases = randomInt(50, 200)
    const truePositives = randomInt(Math.floor(totalCases * 0.6), Math.floor(totalCases * 0.85))
    const falsePositives = randomInt(Math.floor(totalCases * 0.05), Math.floor(totalCases * 0.15))
    const falseNegatives = randomInt(Math.floor(totalCases * 0.03), Math.floor(totalCases * 0.12))
    const trueNegatives = totalCases - truePositives - falsePositives - falseNegatives

    const precision = truePositives / (truePositives + falsePositives)
    const recall = truePositives / (truePositives + falseNegatives)
    const f1Score = (2 * precision * recall) / (precision + recall)
    const accuracy = (truePositives + trueNegatives) / totalCases

    return {
      detector_type: type,
      total_cases: totalCases,
      true_positives: truePositives,
      false_positives: falsePositives,
      false_negatives: falseNegatives,
      true_negatives: trueNegatives,
      precision: Math.round(precision * 1000) / 1000,
      recall: Math.round(recall * 1000) / 1000,
      f1_score: Math.round(f1Score * 1000) / 1000,
      accuracy: Math.round(accuracy * 1000) / 1000,
      trend: randomChoice<AccuracyMetric['trend']>(['improving', 'stable', 'declining']),
    }
  })
}

export interface FeedbackStats {
  total_detections: number
  validated: number
  unvalidated: number
  true_positives: number
  false_positives: number
  by_type: Record<
    string,
    {
      total: number
      tp: number
      fp: number
      precision: number
    }
  >
}

export function generateDemoFeedbackStats(): FeedbackStats {
  const totalDetections = randomInt(150, 500)
  const validated = randomInt(Math.floor(totalDetections * 0.6), Math.floor(totalDetections * 0.85))
  const truePositives = randomInt(Math.floor(validated * 0.7), Math.floor(validated * 0.9))
  const falsePositives = validated - truePositives

  const types = ['infinite_loop', 'state_corruption', 'persona_drift', 'coordination_deadlock']

  const byType: FeedbackStats['by_type'] = {}
  types.forEach((type) => {
    const total = randomInt(20, 80)
    const tp = randomInt(Math.floor(total * 0.65), Math.floor(total * 0.9))
    const fp = total - tp
    byType[type] = {
      total,
      tp,
      fp,
      precision: Math.round((tp / total) * 1000) / 1000,
    }
  })

  return {
    total_detections: totalDetections,
    validated,
    unvalidated: totalDetections - validated,
    true_positives: truePositives,
    false_positives: falsePositives,
    by_type: byType,
  }
}

export interface ThresholdRecommendation {
  detector_type: string
  current_threshold: number
  recommended_threshold: number
  expected_improvement: string
  rationale: string
  confidence: number
}

export function generateDemoThresholdRecommendations(): ThresholdRecommendation[] {
  const recommendations = [
    {
      detector_type: 'infinite_loop',
      current_threshold: 0.75,
      recommended_threshold: 0.68,
      expected_improvement: '+12% recall, -3% precision',
      rationale: 'Analysis shows 12 missed loops that would be caught with lower threshold',
      confidence: 0.87,
    },
    {
      detector_type: 'state_corruption',
      current_threshold: 0.80,
      recommended_threshold: 0.85,
      expected_improvement: '+8% precision, -2% recall',
      rationale: 'High false positive rate suggests threshold is too permissive',
      confidence: 0.92,
    },
    {
      detector_type: 'persona_drift',
      current_threshold: 0.70,
      recommended_threshold: 0.70,
      rationale: 'Current threshold is optimal based on feedback data',
      expected_improvement: 'No change recommended',
      confidence: 0.95,
    },
  ]

  return recommendations
}

export interface IntegrationStatus {
  framework: string
  version: string
  status: 'active' | 'configured' | 'not_configured'
  last_test: string
  test_traces: number
}

export function generateDemoIntegrationStatus(): IntegrationStatus[] {
  return [
    {
      framework: 'LangGraph',
      version: '0.2.3',
      status: 'active',
      last_test: randomDate(2),
      test_traces: randomInt(45, 120),
    },
    {
      framework: 'AutoGen',
      version: '0.2.18',
      status: 'active',
      last_test: randomDate(6),
      test_traces: randomInt(30, 90),
    },
    {
      framework: 'CrewAI',
      version: '0.1.26',
      status: 'configured',
      last_test: randomDate(12),
      test_traces: randomInt(15, 45),
    },
    {
      framework: 'n8n',
      version: '1.19.0',
      status: 'active',
      last_test: randomDate(1),
      test_traces: randomInt(60, 150),
    },
  ]
}

export interface Baseline {
  id: string
  name: string
  created_at: string
  trace_count: number
  detection_count: number
  avg_tokens: number
  avg_latency_ms: number
}

export function generateDemoBaselines(): Baseline[] {
  return Array.from({ length: randomInt(3, 7) }, (_, i) => ({
    id: `baseline-${randomId()}`,
    name: `Baseline ${new Date(Date.now() - i * 7 * 24 * 60 * 60 * 1000).toLocaleDateString()}`,
    created_at: randomDate(i * 7 * 24),
    trace_count: randomInt(50, 200),
    detection_count: randomInt(5, 25),
    avg_tokens: randomInt(1500, 4000),
    avg_latency_ms: randomInt(800, 2500),
  }))
}

// ============================================================================
// CHAOS & REPLAY
// ============================================================================

export interface ChaosExperimentType {
  id: string
  name: string
  description: string
  category: 'latency' | 'failure' | 'resource' | 'state'
  parameters: Record<string, any>
}

export function generateDemoChaosExperimentTypes(): ChaosExperimentType[] {
  return [
    {
      id: 'latency-injection',
      name: 'Latency Injection',
      description: 'Add artificial latency to agent responses',
      category: 'latency',
      parameters: {
        delay_ms: { type: 'number', default: 2000, min: 100, max: 10000 },
        target_agents: { type: 'multi-select', options: agentNames },
      },
    },
    {
      id: 'random-failure',
      name: 'Random Failures',
      description: 'Randomly fail agent operations',
      category: 'failure',
      parameters: {
        failure_rate: { type: 'percentage', default: 0.2, min: 0, max: 1 },
        error_type: {
          type: 'select',
          options: ['timeout', 'rate_limit', 'validation_error', 'network_error'],
        },
      },
    },
    {
      id: 'token-exhaustion',
      name: 'Token Exhaustion',
      description: 'Simulate token/rate limit exhaustion',
      category: 'resource',
      parameters: {
        max_tokens: { type: 'number', default: 4096, min: 1000, max: 32000 },
        trigger_at_percentage: { type: 'percentage', default: 0.9, min: 0.5, max: 1 },
      },
    },
    {
      id: 'state-corruption',
      name: 'State Corruption',
      description: 'Introduce invalid state transitions',
      category: 'state',
      parameters: {
        corruption_type: {
          type: 'select',
          options: ['missing_field', 'type_mismatch', 'invalid_value'],
        },
        frequency: { type: 'percentage', default: 0.15, min: 0.05, max: 0.5 },
      },
    },
  ]
}

export interface ChaosSession {
  id: string
  name: string
  experiment_type: string
  status: 'running' | 'completed' | 'failed' | 'stopped'
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  traces_affected: number
  detections_triggered: number
  parameters: Record<string, any>
  results: {
    failures_injected: number
    failures_detected: number
    recovery_time_ms: number
    impact_score: number
  } | null
}

export function generateDemoChaosSession(): ChaosSession {
  const status = randomChoice<ChaosSession['status']>(['running', 'completed', 'failed', 'stopped'])
  const startedAt = randomDate(12)
  const durationMs = status === 'completed' ? randomInt(60000, 600000) : null
  const completedAt = status === 'completed' ? new Date(new Date(startedAt).getTime() + (durationMs || 0)).toISOString() : null

  return {
    id: `chaos-${randomId()}`,
    name: `Chaos Test ${randomInt(1, 100)}`,
    experiment_type: randomChoice(['latency-injection', 'random-failure', 'token-exhaustion', 'state-corruption']),
    status,
    started_at: startedAt,
    completed_at: completedAt,
    duration_ms: durationMs,
    traces_affected: randomInt(10, 50),
    detections_triggered: randomInt(5, 25),
    parameters: {
      delay_ms: randomInt(1000, 5000),
      failure_rate: randomInt(10, 40) / 100,
    },
    results:
      status === 'completed'
        ? {
            failures_injected: randomInt(15, 40),
            failures_detected: randomInt(12, 38),
            recovery_time_ms: randomInt(500, 3000),
            impact_score: randomInt(60, 95) / 100,
          }
        : null,
  }
}

export function generateDemoChaosSessions(): ChaosSession[] {
  return Array.from({ length: randomInt(3, 8) }, () => generateDemoChaosSession())
}

export interface ReplayBundle {
  id: string
  name: string
  description: string
  created_at: string
  trace_count: number
  total_tokens: number
  avg_latency_ms: number
  tags: string[]
}

export function generateDemoReplayBundles(): ReplayBundle[] {
  const tags = ['production', 'staging', 'regression', 'smoke-test', 'load-test']

  return Array.from({ length: randomInt(5, 12) }, (_, i) => ({
    id: `bundle-${randomId()}`,
    name: `Replay Bundle ${i + 1}`,
    description: randomChoice([
      'Production traces from 2024-01-15',
      'Regression test suite v2.3',
      'Load test - 1000 concurrent users',
      'Smoke test after deployment',
      'Edge case scenarios',
    ]),
    created_at: randomDate(randomInt(1, 60) * 24),
    trace_count: randomInt(25, 150),
    total_tokens: randomInt(50000, 300000),
    avg_latency_ms: randomInt(600, 2500),
    tags: Array.from(
      { length: randomInt(1, 3) },
      () => tags[Math.floor(Math.random() * tags.length)]
    ),
  }))
}

export interface ReplayResult {
  id: string
  bundle_id: string
  started_at: string
  completed_at: string
  status: 'passed' | 'failed' | 'partial'
  traces_replayed: number
  traces_matched: number
  traces_diverged: number
  avg_token_diff: number
  avg_latency_diff_ms: number
  detections_diff: number
}

export function generateDemoReplayResult(bundleId: string): ReplayResult {
  const tracesReplayed = randomInt(25, 150)
  const tracesMatched = randomInt(Math.floor(tracesReplayed * 0.7), Math.floor(tracesReplayed * 0.95))
  const tracesDiverged = tracesReplayed - tracesMatched

  return {
    id: `replay-${randomId()}`,
    bundle_id: bundleId,
    started_at: randomDate(6),
    completed_at: randomDate(5),
    status: tracesDiverged > tracesReplayed * 0.1 ? 'failed' : tracesDiverged > 0 ? 'partial' : 'passed',
    traces_replayed: tracesReplayed,
    traces_matched: tracesMatched,
    traces_diverged: tracesDiverged,
    avg_token_diff: randomInt(-200, 200),
    avg_latency_diff_ms: randomInt(-100, 300),
    detections_diff: randomInt(-3, 5),
  }
}

export interface DriftAlert {
  id: string
  metric: string
  baseline_value: number
  current_value: number
  drift_percentage: number
  severity: 'low' | 'medium' | 'high'
  detected_at: string
}

export function generateDemoDriftAlerts(): DriftAlert[] {
  const metrics = [
    { name: 'avg_tokens_per_trace', baseline: 2500 },
    { name: 'avg_latency_ms', baseline: 1200 },
    { name: 'detection_rate', baseline: 0.15 },
    { name: 'error_rate', baseline: 0.03 },
  ]

  return Array.from({ length: randomInt(2, 5) }, () => {
    const metric = randomChoice(metrics)
    const driftPercentage = randomInt(15, 60)
    const currentValue = metric.baseline * (1 + driftPercentage / 100 * (Math.random() > 0.5 ? 1 : -1))

    return {
      id: `drift-${randomId()}`,
      metric: metric.name,
      baseline_value: metric.baseline,
      current_value: Math.round(currentValue * 100) / 100,
      drift_percentage: driftPercentage,
      severity: driftPercentage > 40 ? 'high' : driftPercentage > 25 ? 'medium' : 'low',
      detected_at: randomDate(12),
    }
  })
}

// ============================================================================
// WORKFLOW & DIAGNOSTICS
// ============================================================================

export interface N8nWorkflow {
  id: string
  name: string
  active: boolean
  webhook_url: string
  registered_at: string
  last_execution: string
  execution_count: number
  avg_quality_grade: string
  tags: string[]
}

export function generateDemoN8nWorkflows(): N8nWorkflow[] {
  const workflowNames = [
    'Customer Support Automation',
    'Lead Qualification Pipeline',
    'Content Generation Workflow',
    'Data Enrichment Process',
    'Slack Notification Handler',
    'Email Campaign Manager',
  ]

  const grades = ['A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+']

  return Array.from({ length: randomInt(4, 8) }, (_, i) => ({
    id: `n8n-wf-${randomId()}`,
    name: workflowNames[i % workflowNames.length],
    active: Math.random() > 0.2, // 80% active
    webhook_url: `https://n8n.yourcompany.com/webhook/${randomId()}`,
    registered_at: randomDate(randomInt(10, 90) * 24),
    last_execution: randomDate(randomInt(1, 48)),
    execution_count: randomInt(50, 500),
    avg_quality_grade: randomChoice(grades),
    tags: Array.from({ length: randomInt(1, 3) }, () =>
      randomChoice(['production', 'staging', 'automation', 'ai-powered', 'critical'])
    ),
  }))
}

export interface DiagnoseResult {
  trace_id: string
  format: 'langsmith' | 'otel' | 'json'
  agent_count: number
  total_steps: number
  total_tokens: number
  duration_ms: number
  detections: Array<{
    type: string
    severity: string
    confidence: number
    description: string
  }>
  agent_interactions: Array<{
    from_agent: string
    to_agent: string
    message_count: number
    avg_latency_ms: number
  }>
  bottlenecks: Array<{
    agent: string
    step: string
    latency_ms: number
    percentage_of_total: number
  }>
  suggestions: string[]
}

export function generateDemoDiagnoseResult(traceId?: string): DiagnoseResult {
  const agentCount = randomInt(3, 7)
  const totalSteps = randomInt(15, 50)

  const detectionsData = [
    {
      type: 'infinite_loop',
      severity: 'high',
      description: 'Detected repeated state transitions between Researcher and Analyzer',
    },
    {
      type: 'coordination_delay',
      severity: 'medium',
      description: 'Handoff between Coordinator and Planner taking longer than expected',
    },
    {
      type: 'token_inefficiency',
      severity: 'low',
      description: 'Redundant context being passed between agents',
    },
  ]

  const detections = Array.from({ length: randomInt(1, 3) }, () => {
    const detection = randomChoice(detectionsData)
    return {
      ...detection,
      confidence: randomInt(75, 98) / 100,
    }
  })

  const agentInteractions = Array.from({ length: randomInt(3, 6) }, () => ({
    from_agent: randomChoice(agentNames),
    to_agent: randomChoice(agentNames),
    message_count: randomInt(2, 15),
    avg_latency_ms: randomInt(200, 1500),
  }))

  const bottlenecks = Array.from({ length: randomInt(2, 4) }, () => {
    const latencyMs = randomInt(800, 3000)
    return {
      agent: randomChoice(agentNames),
      step: randomChoice(['API call', 'LLM inference', 'State validation', 'Context retrieval']),
      latency_ms: latencyMs,
      percentage_of_total: randomInt(15, 45),
    }
  })

  const suggestions = [
    'Consider adding timeout to Researcher \u2192 Analyzer handoff',
    'Reduce context size passed to Planner (currently 3200 tokens)',
    'Add caching layer for repeated API calls',
    'Optimize state validation logic in Validator agent',
  ]

  return {
    trace_id: traceId || `trace-${randomId()}`,
    format: randomChoice<DiagnoseResult['format']>(['langsmith', 'otel', 'json']),
    agent_count: agentCount,
    total_steps: totalSteps,
    total_tokens: randomInt(5000, 25000),
    duration_ms: randomInt(3000, 15000),
    detections,
    agent_interactions: agentInteractions,
    bottlenecks,
    suggestions: suggestions.slice(0, randomInt(2, 4)),
  }
}

// Generate demo handoff analysis with graph structure
export function generateDemoHandoffAnalysis(workflow: QualityAssessment): HandoffAnalysis {
  const agents = (workflow.agent_scores || []).map(a => a.agent_id)
  const pattern = workflow.orchestration_score?.detected_pattern || 'sequential'
  
  if (agents.length === 0) {
    return {
      total_handoffs: 0,
      successful_handoffs: 0,
      failed_handoffs: 0,
      avg_latency_ms: 0,
      max_latency_ms: 0,
      context_completeness: 1.0,
      data_loss_detected: false,
      circular_handoffs: [],
      agents_involved: [],
      handoff_graph: {},
      issues: [],
    }
  }

  // Build handoff graph based on detected pattern
  let handoff_graph: Record<string, string[]> = {}
  
  if (pattern === 'sequential' || pattern === 'pipeline') {
    // Chain: A → B → C → D
    agents.forEach((agent, idx) => {
      if (idx < agents.length - 1) {
        handoff_graph[agent] = [agents[idx + 1]]
      }
    })
  } else if (pattern === 'fan-out') {
    // A → [B, C, D] → E (if enough agents)
    if (agents.length >= 3) {
      const firstAgent = agents[0]
      const middleAgents = agents.slice(1, -1)
      const lastAgent = agents[agents.length - 1]
      
      handoff_graph[firstAgent] = middleAgents
      middleAgents.forEach(agent => {
        handoff_graph[agent] = [lastAgent]
      })
    } else {
      // Fallback to sequential
      agents.forEach((agent, idx) => {
        if (idx < agents.length - 1) {
          handoff_graph[agent] = [agents[idx + 1]]
        }
      })
    }
  } else if (pattern === 'parallel') {
    // All agents run in parallel, converge to last
    if (agents.length >= 2) {
      const parallelAgents = agents.slice(0, -1)
      const finalAgent = agents[agents.length - 1]
      parallelAgents.forEach(agent => {
        handoff_graph[agent] = [finalAgent]
      })
    } else {
      handoff_graph[agents[0]] = []
    }
  } else if (pattern === 'conditional') {
    // Branching pattern: A → Decision → [B, C] → D
    if (agents.length >= 3) {
      // First agent to decision node
      handoff_graph[agents[0]] = ['decision-1']

      // Decision node to branch agents
      const branchAgents = agents.slice(1, -1)
      handoff_graph['decision-1'] = branchAgents

      // Branch agents converge to last agent
      if (agents.length > 2) {
        const lastAgent = agents[agents.length - 1]
        branchAgents.forEach(agent => {
          handoff_graph[agent] = [lastAgent]
        })
      }
    } else {
      agents.forEach((agent, idx) => {
        if (idx < agents.length - 1) {
          handoff_graph[agent] = [agents[idx + 1]]
        }
      })
    }
  } else {
    // Hierarchical or other patterns - default to sequential
    agents.forEach((agent, idx) => {
      if (idx < agents.length - 1) {
        handoff_graph[agent] = [agents[idx + 1]]
      }
    })
  }

  // Calculate handoff counts
  const totalHandoffs = Object.values(handoff_graph).reduce((sum, targets) => sum + targets.length, 0)
  const failedHandoffs = workflow.overall_score < 0.7 ? randomInt(1, 3) : randomInt(0, 1)
  const successfulHandoffs = totalHandoffs - failedHandoffs

  return {
    total_handoffs: totalHandoffs,
    successful_handoffs: successfulHandoffs,
    failed_handoffs: failedHandoffs,
    avg_latency_ms: randomInt(50, 200),
    max_latency_ms: randomInt(300, 800),
    context_completeness: Math.max(0.7, workflow.overall_score + randomInt(-10, 10) / 100),
    data_loss_detected: failedHandoffs > 0,
    circular_handoffs: [], // No circular dependencies in demo data
    agents_involved: agents,
    handoff_graph,
    issues: failedHandoffs > 0 ? ['Some handoffs failed due to timeout'] : [],
  }
}

// Generate per-handoff metrics for edge styling
export function generateHandoffMetrics(
  handoffGraph: Record<string, string[]>,
  agentScores: AgentQualityScore[]
): Record<string, import('./workflow-layout').HandoffMetrics> {
  const metrics: Record<string, import('./workflow-layout').HandoffMetrics> = {}

  // Create a map of agent IDs to their scores for quick lookup
  const agentScoreMap = new Map(agentScores.map(a => [a.agent_id, a.overall_score]))

  Object.entries(handoffGraph).forEach(([fromAgent, toAgents]) => {
    toAgents.forEach((toAgent) => {
      const edgeId = `${fromAgent}-${toAgent}`

      // Base success rate on the health of both agents
      const fromScore = agentScoreMap.get(fromAgent) || 0.8
      const toScore = agentScoreMap.get(toAgent) || 0.8
      const avgScore = (fromScore + toScore) / 2

      // Success rate correlates with agent health
      const baseSuccessRate = Math.min(0.99, Math.max(0.5, avgScore + randomInt(-5, 5) / 100))

      // Add some variance to latency based on agent health
      const baseLatency = avgScore > 0.9 ? randomInt(30, 80) :
                         avgScore > 0.7 ? randomInt(50, 150) :
                         randomInt(100, 300)

      // Total handoffs varies
      const totalHandoffs = randomInt(10, 100)
      const failedHandoffs = Math.floor(totalHandoffs * (1 - baseSuccessRate))

      // Determine status
      let status: 'healthy' | 'degraded' | 'failing'
      if (baseSuccessRate >= 0.95) status = 'healthy'
      else if (baseSuccessRate >= 0.85) status = 'degraded'
      else status = 'failing'

      metrics[edgeId] = {
        successRate: baseSuccessRate,
        avgLatencyMs: baseLatency,
        totalHandoffs,
        failedHandoffs,
        status,
      }
    })
  })

  return metrics
}

// ============================================================================
// FRAMEWORK INTEGRATION DEMO DATA (matches api.ts types)
// ============================================================================

import type {
  N8nWorkflow as ApiN8nWorkflow,
  OpenClawInstance,
  OpenClawAgent,
  DifyInstance,
  DifyApp,
  LangGraphDeployment,
  LangGraphAssistant,
} from './api'

export function generateDemoApiN8nWorkflows(): ApiN8nWorkflow[] {
  const names = [
    'Customer Support Automation',
    'Lead Qualification Pipeline',
    'Content Generation Workflow',
    'Data Enrichment Process',
    'Slack Notification Handler',
  ]

  return names.map((name, i) => ({
    id: `wf-${randomId()}`,
    workflow_id: `${1000 + i}`,
    workflow_name: name,
    webhook_url: `https://n8n.example.com/webhook/${randomId()}`,
    ingestion_mode: randomChoice(['webhook', 'polling']),
    registered_at: randomDate(randomInt(48, 720)),
  }))
}

export function generateDemoOpenClawInstances(): OpenClawInstance[] {
  return [
    {
      id: `oc-inst-${randomId()}`,
      name: 'Production Gateway',
      gateway_url: 'https://openclaw.example.com',
      otel_enabled: true,
      is_active: true,
      channels_configured: ['slack', 'web', 'api'],
      ingestion_mode: 'otel',
      created_at: randomDate(720),
    },
    {
      id: `oc-inst-${randomId()}`,
      name: 'Staging Gateway',
      gateway_url: 'https://staging.openclaw.example.com',
      otel_enabled: false,
      is_active: true,
      channels_configured: ['web'],
      ingestion_mode: 'polling',
      created_at: randomDate(360),
    },
  ]
}

export function generateDemoOpenClawAgents(): OpenClawAgent[] {
  const agents = [
    { name: 'Research Assistant', key: 'research-agent', model: 'claude-sonnet-4-20250514' },
    { name: 'Code Reviewer', key: 'code-reviewer', model: 'claude-sonnet-4-20250514' },
    { name: 'Customer Support Bot', key: 'support-bot', model: 'claude-haiku-4-5-20251001' },
    { name: 'Data Analyst', key: 'data-analyst', model: 'claude-sonnet-4-20250514' },
  ]

  return agents.map((a) => ({
    id: `oc-agent-${randomId()}`,
    agent_key: a.key,
    agent_name: a.name,
    model: a.model,
    monitoring_enabled: Math.random() > 0.2,
    ingestion_mode: 'otel',
    total_sessions: randomInt(50, 500),
    total_messages: randomInt(200, 3000),
    registered_at: randomDate(randomInt(48, 360)),
  }))
}

export function generateDemoDifyInstances(): DifyInstance[] {
  return [
    {
      id: `dify-inst-${randomId()}`,
      name: 'Production Dify',
      base_url: 'https://dify.example.com',
      is_active: true,
      app_types_configured: ['chatbot', 'workflow', 'agent'],
      ingestion_mode: 'webhook',
      created_at: randomDate(480),
    },
  ]
}

export function generateDemoDifyApps(): DifyApp[] {
  const apps = [
    { name: 'HR Onboarding Assistant', type: 'chatbot' },
    { name: 'Invoice Processing Pipeline', type: 'workflow' },
    { name: 'Legal Document Analyzer', type: 'agent' },
    { name: 'Sales Lead Qualifier', type: 'chatbot' },
  ]

  return apps.map((a) => ({
    id: `dify-app-${randomId()}`,
    app_id: `app-${randomId()}`,
    app_name: a.name,
    app_type: a.type,
    monitoring_enabled: Math.random() > 0.15,
    ingestion_mode: 'webhook',
    total_runs: randomInt(100, 2000),
    total_tokens: randomInt(50000, 500000),
    registered_at: randomDate(randomInt(48, 360)),
  }))
}

export function generateDemoLangGraphDeployments(): LangGraphDeployment[] {
  return [
    {
      id: `lg-deploy-${randomId()}`,
      name: 'Production LangGraph Cloud',
      api_url: 'https://api.langgraph.cloud/v1',
      is_active: true,
      deployment_id: `dep-${randomId()}`,
      graph_name: 'multi_agent_researcher',
      ingestion_mode: 'full',
      created_at: randomDate(randomInt(72, 240)),
    },
    {
      id: `lg-deploy-${randomId()}`,
      name: 'Staging Self-Hosted',
      api_url: 'https://staging.internal.dev:8123',
      is_active: true,
      deployment_id: `dep-${randomId()}`,
      graph_name: 'code_review_agent',
      ingestion_mode: 'full',
      created_at: randomDate(randomInt(24, 120)),
    },
  ]
}

export function generateDemoLangGraphAssistants(): LangGraphAssistant[] {
  const assistants = [
    { name: 'Research Assistant', graph_id: 'research_graph' },
    { name: 'Code Reviewer', graph_id: 'code_review_graph' },
    { name: 'Data Pipeline Agent', graph_id: 'data_pipeline_graph' },
    { name: 'Customer Support Bot', graph_id: 'support_graph' },
  ]

  return assistants.map((a) => ({
    id: `lg-asst-${randomId()}`,
    deployment_id: `lg-deploy-${randomId()}`,
    assistant_id: `asst-${randomId()}`,
    graph_id: a.graph_id,
    name: a.name,
    monitoring_enabled: Math.random() > 0.15,
    ingestion_mode: 'full',
    total_runs: randomInt(50, 1500),
    registered_at: randomDate(randomInt(24, 200)),
  }))
}
