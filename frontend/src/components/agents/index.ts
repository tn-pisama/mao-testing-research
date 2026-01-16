// Agent types used by demo-data and other components

export type AgentStatus = 'idle' | 'running' | 'completed' | 'failed' | 'waiting'

export interface AgentInfo {
  id: string
  name: string
  type: 'coordinator' | 'worker' | 'specialist' | 'validator'
  status: AgentStatus
  currentTask?: string
  tokensUsed: number
  latencyMs: number
  stepCount: number
  errorCount: number
  lastActiveAt: string
}

export interface ActivityEvent {
  id: string
  agentId: string
  agentName: string
  type: 'started' | 'completed' | 'failed' | 'message_sent' | 'message_received' | 'thinking' | 'tool_call'
  content: string
  timestamp: string
  metadata?: Record<string, unknown>
}

// Component exports
export { AgentDetailHeader } from './AgentDetailHeader'
export { AgentPerformanceChart } from './AgentPerformanceChart'
export { AgentStateTimeline } from './AgentStateTimeline'
export { AgentCommunicationLog } from './AgentCommunicationLog'
export { AgentToolUsage } from './AgentToolUsage'
export { AgentMemoryView } from './AgentMemoryView'
export { AgentCard } from './AgentCard'
export { AgentOrchestrationView } from './AgentOrchestrationView'
export { AgentActivityFeed } from './AgentActivityFeed'
export { AgentMetricsPanel } from './AgentMetricsPanel'
export { AgentComparisonView } from './AgentComparisonView'
export { AgentHealthDashboard } from './AgentHealthDashboard'
export { AgentMonitoringPanel } from './AgentMonitoringPanel'
