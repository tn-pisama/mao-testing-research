import { useState, useEffect } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import type { QualityAssessment } from '@/lib/api'
import type { HandoffMetrics } from '@/lib/workflow-layout'
import { createApiClient } from '@/lib/api'
import { generateDemoHandoffAnalysis, generateHandoffMetrics } from '@/lib/demo-data'

export interface HandoffAnalysis {
  handoff_graph: Record<string, string[]>
  // Add other fields as needed from API response
}

interface UseHandoffAnalysisResult {
  handoffAnalysis: HandoffAnalysis | null
  handoffMetrics: Record<string, HandoffMetrics>
  isLoading: boolean
  isDemoMode: boolean
  error: string | null
}

export function useHandoffAnalysis(workflow?: QualityAssessment): UseHandoffAnalysisResult {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()

  const [handoffAnalysis, setHandoffAnalysis] = useState<HandoffAnalysis | null>(null)
  const [handoffMetrics, setHandoffMetrics] = useState<Record<string, HandoffMetrics>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [isDemoMode, setIsDemoMode] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!workflow) {
      setHandoffAnalysis(null)
      setHandoffMetrics({})
      setIsDemoMode(false)
      return
    }

    async function loadHandoffData() {
      setIsLoading(true)
      setError(null)

      try {
        // Try real API first
        const token = await getToken()
        const apiClient = createApiClient(token, tenantId || 'default')

        // Attempt to analyze handoffs via API
        // Note: This endpoint may need trace data, so we might need to handle 400/404 gracefully
        const analysis = await apiClient.analyzeHandoffs({
          workflow_id: workflow.workflow_id,
          // Future: Add trace_id, span_data, etc. when available
        })

        // Generate metrics from analysis
        const metrics = generateHandoffMetrics(
          analysis.handoff_graph,
          workflow.agent_scores || []
        )

        setHandoffAnalysis(analysis)
        setHandoffMetrics(metrics)
        setIsDemoMode(false)
      } catch (err: any) {
        // Graceful fallback to demo data
        console.warn('API failed, using demo data:', err?.message || err)
        const demoAnalysis = generateDemoHandoffAnalysis(workflow)
        const demoMetrics = generateHandoffMetrics(
          demoAnalysis.handoff_graph,
          workflow.agent_scores || []
        )

        setHandoffAnalysis(demoAnalysis)
        setHandoffMetrics(demoMetrics)
        setIsDemoMode(true)
        setError('Using demo data - API unavailable')
      } finally {
        setIsLoading(false)
      }
    }

    loadHandoffData()
  }, [workflow, getToken])

  return { handoffAnalysis, handoffMetrics, isLoading, isDemoMode, error }
}
