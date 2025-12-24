'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  generateDemoAgents,
  generateDemoMessages,
  generateDemoActivityEvents,
  generateDemoTraces,
  generateDemoDetections,
  generateDemoLoopAnalytics,
  generateDemoCostAnalytics,
  generateDemoAgentMetrics,
} from '@/lib/demo-data'
import { AgentInfo, ActivityEvent } from '@/components/agents'

interface DemoState {
  agents: AgentInfo[]
  messages: ReturnType<typeof generateDemoMessages>
  activityEvents: ActivityEvent[]
  traces: ReturnType<typeof generateDemoTraces>
  detections: ReturnType<typeof generateDemoDetections>
  loopAnalytics: ReturnType<typeof generateDemoLoopAnalytics>
  costAnalytics: ReturnType<typeof generateDemoCostAnalytics>
  agentMetrics: ReturnType<typeof generateDemoAgentMetrics>
}

interface UseDemoModeOptions {
  autoSimulate?: boolean
  simulationInterval?: number
}

const emptyState: DemoState = {
  agents: [],
  messages: [],
  activityEvents: [],
  traces: [],
  detections: [],
  loopAnalytics: {
    total_loops_detected: 0,
    loops_by_method: {},
    avg_loop_length: 0,
    top_agents_in_loops: [],
    time_series: [],
  },
  costAnalytics: {
    total_cost_cents: 0,
    total_tokens: 0,
    cost_by_framework: {},
    cost_by_day: [],
    top_expensive_traces: [],
  },
  agentMetrics: {
    totalAgents: 0,
    activeAgents: 0,
    totalTokens: 0,
    avgLatencyMs: 0,
    totalCostCents: 0,
    errorRate: 0,
    loopsDetected: 0,
    avgStepsPerTrace: 0,
  },
}

function createInitialState(): DemoState {
  const agents = generateDemoAgents(6)
  return {
    agents,
    messages: generateDemoMessages(agents, 8),
    activityEvents: generateDemoActivityEvents(agents, 15),
    traces: generateDemoTraces(10),
    detections: generateDemoDetections(8),
    loopAnalytics: generateDemoLoopAnalytics(),
    costAnalytics: generateDemoCostAnalytics(),
    agentMetrics: generateDemoAgentMetrics(),
  }
}

export function useDemoMode(options: UseDemoModeOptions = {}) {
  const { autoSimulate = false, simulationInterval = 2000 } = options
  const [isDemo, setIsDemo] = useState(true)
  const [isSimulating, setIsSimulating] = useState(autoSimulate)
  const [isLoaded, setIsLoaded] = useState(false)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const [demoState, setDemoState] = useState<DemoState>(emptyState)

  useEffect(() => {
    setDemoState(createInitialState())
    setIsLoaded(true)
  }, [])

  const refreshData = useCallback(() => {
    setDemoState(createInitialState())
  }, [])

  const simulateActivity = useCallback(() => {
    setDemoState((prev) => {
      if (prev.agents.length === 0) return prev
      
      const agents = prev.agents.map((agent) => {
        if (Math.random() > 0.7) {
          const statuses: AgentInfo['status'][] = ['idle', 'running', 'completed', 'waiting']
          return {
            ...agent,
            status: statuses[Math.floor(Math.random() * statuses.length)],
            tokensUsed: agent.tokensUsed + Math.floor(Math.random() * 500),
            stepCount: agent.status === 'running' ? agent.stepCount + 1 : agent.stepCount,
            latencyMs: Math.floor(Math.random() * 500) + 100,
          }
        }
        return agent
      })

      const randomAgent = agents[Math.floor(Math.random() * agents.length)]
      const newEvent: ActivityEvent = {
        id: Math.random().toString(36).substring(2),
        agentId: randomAgent.id,
        agentName: randomAgent.name,
        type: ['started', 'completed', 'message_sent', 'thinking', 'tool_call'][
          Math.floor(Math.random() * 5)
        ] as ActivityEvent['type'],
        content: [
          'Processing incoming request...',
          'Completed task successfully',
          'Sending results to coordinator',
          'Analyzing response patterns...',
          'Calling external API...',
        ][Math.floor(Math.random() * 5)],
        timestamp: new Date().toISOString(),
      }

      return {
        ...prev,
        agents,
        activityEvents: [...prev.activityEvents.slice(-19), newEvent],
        agentMetrics: {
          ...prev.agentMetrics,
          activeAgents: agents.filter((a) => a.status === 'running').length,
          totalTokens: prev.agentMetrics.totalTokens + Math.floor(Math.random() * 1000),
        },
      }
    })
  }, [])

  const startSimulation = useCallback(() => {
    setIsSimulating(true)
  }, [])

  const stopSimulation = useCallback(() => {
    setIsSimulating(false)
  }, [])

  const toggleSimulation = useCallback(() => {
    setIsSimulating((prev) => !prev)
  }, [])

  useEffect(() => {
    if (isSimulating && isLoaded) {
      intervalRef.current = setInterval(simulateActivity, simulationInterval)
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [isSimulating, isLoaded, simulationInterval, simulateActivity])

  return {
    isDemo,
    setIsDemo,
    isSimulating,
    isLoaded,
    startSimulation,
    stopSimulation,
    toggleSimulation,
    refreshData,
    ...demoState,
  }
}
