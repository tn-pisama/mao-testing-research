'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

export type OnboardingStep = 1 | 2 | 3

export interface OnboardingState {
  currentStep: OnboardingStep
  selectedFramework: string | null
  traceReceived: boolean
  firstTraceId: string | null
  detectionsRun: boolean
  completedAt: string | null
}

const STORAGE_KEY = 'pisama_onboarding'
const COMPLETED_KEY = 'pisama_onboarding_completed'

function loadState(): OnboardingState {
  if (typeof window === 'undefined') {
    return defaultState()
  }
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return JSON.parse(stored)
  } catch {}
  return defaultState()
}

function defaultState(): OnboardingState {
  return {
    currentStep: 1,
    selectedFramework: null,
    traceReceived: false,
    firstTraceId: null,
    detectionsRun: false,
    completedAt: null,
  }
}

export function useOnboarding() {
  const [state, setState] = useState<OnboardingState>(loadState)

  // Persist state changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    }
  }, [state])

  const setStep = useCallback((step: OnboardingStep) => {
    setState(prev => ({ ...prev, currentStep: step }))
  }, [])

  const selectFramework = useCallback((framework: string) => {
    setState(prev => ({ ...prev, selectedFramework: framework }))
  }, [])

  const markTraceReceived = useCallback((traceId: string) => {
    setState(prev => ({
      ...prev,
      traceReceived: true,
      firstTraceId: traceId,
      currentStep: 3,
    }))
  }, [])

  const markDetectionsRun = useCallback(() => {
    setState(prev => ({ ...prev, detectionsRun: true }))
  }, [])

  const completeOnboarding = useCallback(() => {
    const completedAt = new Date().toISOString()
    setState(prev => ({ ...prev, completedAt }))
    if (typeof window !== 'undefined') {
      localStorage.setItem(COMPLETED_KEY, completedAt)
    }
  }, [])

  const resetOnboarding = useCallback(() => {
    setState(defaultState())
    if (typeof window !== 'undefined') {
      localStorage.removeItem(COMPLETED_KEY)
    }
  }, [])

  const isCompleted = typeof window !== 'undefined'
    ? !!localStorage.getItem(COMPLETED_KEY)
    : false

  return {
    ...state,
    setStep,
    selectFramework,
    markTraceReceived,
    markDetectionsRun,
    completeOnboarding,
    resetOnboarding,
    isCompleted,
  }
}

// Framework setup snippets
export interface FrameworkSetup {
  id: string
  name: string
  icon: string
  description: string
  isVisual: boolean
  pipInstall: string
  codeSnippet: string
  docsUrl: string
}

export const FRAMEWORKS: FrameworkSetup[] = [
  {
    id: 'langgraph',
    name: 'LangGraph',
    icon: 'GitBranch',
    description: 'State machine-based agent orchestration',
    isVisual: false,
    pipInstall: 'pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp',
    codeSnippet: `from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# Configure OTEL to send traces to PISAMA
provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="https://api.pisama.ai/v1/traces")
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# Your LangGraph code runs as normal - OTEL captures the traces
from langgraph.graph import StateGraph
graph = StateGraph(...)`,
    docsUrl: '/guides/integrations/langgraph',
  },
  {
    id: 'crewai',
    name: 'CrewAI',
    icon: 'Users',
    description: 'Role-based multi-agent collaboration',
    isVisual: false,
    pipInstall: 'pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp',
    codeSnippet: `from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="https://api.pisama.ai/v1/traces")
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# Your CrewAI code runs as normal
from crewai import Agent, Task, Crew
crew = Crew(agents=[...], tasks=[...])`,
    docsUrl: '/guides/integrations/crewai',
  },
  {
    id: 'autogen',
    name: 'AutoGen',
    icon: 'Zap',
    description: 'Multi-agent conversation framework',
    isVisual: false,
    pipInstall: 'pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp',
    codeSnippet: `from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
exporter = OTLPSpanExporter(endpoint="https://api.pisama.ai/v1/traces")
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

# Your AutoGen code runs as normal
import autogen
assistant = autogen.AssistantAgent(...)`,
    docsUrl: '/guides/integrations/autogen',
  },
  {
    id: 'n8n',
    name: 'n8n',
    icon: 'Workflow',
    description: 'Visual workflow automation with AI agents',
    isVisual: true,
    pipInstall: '',
    codeSnippet: `// In your n8n workflow, add an HTTP Request node after your AI agent:
//
// Method: POST
// URL: https://api.pisama.ai/v1/n8n/webhook
// Headers:
//   Authorization: Bearer YOUR_API_KEY
//   Content-Type: application/json
// Body:
//   {{ JSON.stringify($json) }}
//
// Or use the PISAMA n8n community node (recommended):
// npm install n8n-nodes-pisama`,
    docsUrl: '/guides/integrations/n8n',
  },
  {
    id: 'dify',
    name: 'Dify',
    icon: 'Blocks',
    description: 'Visual LLM app development platform',
    isVisual: true,
    pipInstall: '',
    codeSnippet: `// Configure Dify webhook in your app settings:
//
// 1. Go to your Dify app > Monitoring > Webhooks
// 2. Add webhook URL: https://api.pisama.ai/v1/dify/webhook
// 3. Add header: Authorization: Bearer YOUR_API_KEY
// 4. Select events: workflow.completed, workflow.failed
//
// PISAMA will automatically analyze your Dify workflow executions`,
    docsUrl: '/guides/integrations/dify',
  },
  {
    id: 'openclaw',
    name: 'OpenClaw',
    icon: 'Bot',
    description: 'Multi-agent session orchestration',
    isVisual: false,
    pipInstall: 'pip install pisama-moltbot-adapter',
    codeSnippet: `from pisama_moltbot_adapter import PISAMAAdapter

# Initialize the adapter with your API key
adapter = PISAMAAdapter(
    api_key="YOUR_API_KEY",
    endpoint="https://api.pisama.ai/v1/openclaw/webhook"
)

# Wrap your OpenClaw session
adapter.instrument_session(session)`,
    docsUrl: '/guides/integrations/openclaw',
  },
]
