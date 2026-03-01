'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient } from '@/lib/api'
import { useUIStore } from '@/stores/uiStore'
import { useApiResource } from '@/hooks/useApiResource'
import {
  generateDemoLoopAnalytics,
  generateDemoCostAnalytics,
  generateDemoEvalResult,
  generateDemoQuickEvalResult,
  generateDemoLLMJudgeResult,
  QualityAssessment,
  HealingRecord,
  N8nConnection,
  EvalResult,
  QuickEvalResult,
  LLMJudgeResult,
} from '@/lib/demo-data'
import { demoDataStore } from '@/lib/demo-state'
import type { LoopAnalytics, CostAnalytics, Detection, Trace } from '@/lib/api'

// ============================================================================
// AGGREGATE DASHBOARD HOOK (complex, kept as-is)
// ============================================================================

export function useApiWithFallback() {
  const { getToken } = useAuth()
  const { tenantId, isLoaded: tenantLoaded } = useTenant()
  const { filterPreferences } = useUIStore()
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [loopAnalytics, setLoopAnalytics] = useState<LoopAnalytics | undefined>()
  const [costAnalytics, setCostAnalytics] = useState<CostAnalytics | undefined>()
  const [detections, setDetections] = useState<Detection[]>([])
  const [traces, setTraces] = useState<Trace[]>([])
  const [qualityAssessments, setQualityAssessments] = useState<QualityAssessment[]>([])

  const hasLoadedRef = useRef(false)
  const isMountedRef = useRef(true)

  const loadDemoData = useCallback(() => {
    console.warn('🎭 API unavailable, loading demo mode data')
    setLoopAnalytics(generateDemoLoopAnalytics())
    setCostAnalytics(generateDemoCostAnalytics())
    setDetections(demoDataStore.getDetections().slice(0, 10))
    setTraces(demoDataStore.getTraces().slice(0, 10))
    setQualityAssessments(demoDataStore.getQualityAssessments().slice(0, 5))
    setIsDemoMode(true)
    setError(null)
  }, [])

  const loadRealData = useCallback(async () => {
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      const [loops, cost, dets, trc, qualityRes] = await Promise.all([
        api.getLoopAnalytics(30).catch(() => null),
        api.getCostAnalytics(30).catch(() => null),
        api.getDetections({ perPage: 10 }).catch(() => null),
        api.getTraces({ perPage: 10 }).catch(() => null),
        api.listQualityAssessments({
          pageSize: 20,
          groupId: filterPreferences.workflowGroupId && filterPreferences.workflowGroupId !== 'all'
            ? filterPreferences.workflowGroupId
            : undefined,
        }).catch(() => null),
      ])

      if (!isMountedRef.current) return false

      const hasAnyData = !!(
        loops || cost ||
        (dets && dets.items && dets.items.length > 0) ||
        (trc && trc.traces && trc.traces.length > 0) ||
        (qualityRes && qualityRes.assessments && qualityRes.assessments.length > 0)
      )

      if (!hasAnyData) {
        if (isMountedRef.current) setError('Unable to load data from API. Showing demo data.')
        return false
      }

      setLoopAnalytics(loops || undefined)
      setCostAnalytics(cost || undefined)
      setDetections(dets?.items || [])
      setTraces(trc?.traces || [])
      setQualityAssessments(qualityRes?.assessments || [])
      setIsDemoMode(false)
      setError(null)
      return true
    } catch {
      if (isMountedRef.current) setError('Unable to connect to API. Showing demo data.')
      return false
    }
  }, [getToken, tenantId, filterPreferences.workflowGroupId])

  useEffect(() => {
    isMountedRef.current = true
    if (!tenantLoaded) return

    const loadData = async () => {
      setIsLoading(true)
      setError(null)
      const dataSuccess = await loadRealData()
      if (!dataSuccess && isMountedRef.current) loadDemoData()
      if (isMountedRef.current) setIsLoading(false)
    }
    loadData()

    return () => { isMountedRef.current = false }
  }, [tenantId, tenantLoaded, loadRealData, loadDemoData])

  const refresh = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    const dataSuccess = await loadRealData()
    if (!dataSuccess && isMountedRef.current) loadDemoData()
    if (isMountedRef.current) setIsLoading(false)
  }, [loadRealData, loadDemoData])

  const toggleDemoMode = useCallback(async () => {
    if (isDemoMode) {
      setIsLoading(true)
      setError(null)
      const dataSuccess = await loadRealData()
      if (!dataSuccess && isMountedRef.current) loadDemoData()
      if (isMountedRef.current) setIsLoading(false)
    } else {
      loadDemoData()
    }
  }, [isDemoMode, loadRealData, loadDemoData])

  return {
    isLoading, isDemoMode, error,
    loopAnalytics, costAnalytics, detections, traces, qualityAssessments,
    toggleDemoMode, refresh,
  }
}

// ============================================================================
// STANDARD LIST HOOKS (use factory)
// ============================================================================

export function useDetections(params?: {
  page?: number
  perPage?: number
  type?: string
  confidenceMin?: number
  confidenceMax?: number
  dateFrom?: string
  dateTo?: string
}) {
  const page = params?.page
  const perPage = params?.perPage
  const type = params?.type
  const confidenceMin = params?.confidenceMin
  const confidenceMax = params?.confidenceMax
  const dateFrom = params?.dateFrom
  const dateTo = params?.dateTo

  const { data, isLoading, isDemoMode } = useApiResource<{ items: Detection[]; total: number; page: number; per_page: number }>(
    (api) => api.getDetections({ page, perPage, type, confidenceMin, confidenceMax, dateFrom, dateTo }),
    () => {
      const all = demoDataStore.getDetections()
      return { items: all.slice(0, perPage || 20), total: all.length, page: page || 1, per_page: perPage || 20 }
    },
    [page, perPage, type, confidenceMin, confidenceMax, dateFrom, dateTo],
  )
  return { detections: data?.items ?? [], total: data?.total ?? 0, isLoading, isDemoMode }
}

export function useTraces(params?: { page?: number; perPage?: number; status?: string }) {
  const page = params?.page
  const perPage = params?.perPage
  const status = params?.status

  const { data, isLoading, isDemoMode } = useApiResource<{ traces: Trace[]; total: number }>(
    (api) => api.getTraces({ page, perPage, status }),
    () => {
      const allTraces = demoDataStore.getTraces()
      return { traces: allTraces.slice(0, perPage || 20), total: allTraces.length }
    },
    [page, perPage, status],
  )
  return { traces: data?.traces ?? [], total: data?.total ?? 0, isLoading, isDemoMode }
}

export function useQualityAssessments(params?: { page?: number; pageSize?: number; minGrade?: string }) {
  const page = params?.page
  const pageSize = params?.pageSize
  const minGrade = params?.minGrade

  const { data, isLoading, isDemoMode } = useApiResource<{ assessments: QualityAssessment[]; total: number }>(
    async (api) => {
      const res = await api.listQualityAssessments({ page, pageSize, minGrade })
      return { assessments: res.assessments, total: res.total || res.assessments.length }
    },
    () => {
      const all = demoDataStore.getQualityAssessments()
      return { assessments: all.slice(0, pageSize || 20), total: all.length }
    },
    [page, pageSize, minGrade],
  )
  return { assessments: data?.assessments ?? [], total: data?.total ?? 0, isLoading, isDemoMode }
}

export function useHealingRecords(params?: { page?: number; pageSize?: number; status?: string }) {
  const page = params?.page
  const pageSize = params?.pageSize
  const status = params?.status

  const { data, isLoading, isDemoMode } = useApiResource<{ records: HealingRecord[]; total: number }>(
    async (api) => {
      const res = await api.listHealingRecords({ page, perPage: pageSize, status })
      return { records: res.items, total: res.total || res.items.length }
    },
    () => {
      const allRecords = demoDataStore.getHealingRecords()
      let filtered = allRecords
      if (status) filtered = allRecords.filter((r) => r.status === status)
      const size = pageSize || 20
      return { records: filtered.slice(0, size), total: filtered.length }
    },
    [page, pageSize, status],
  )
  return { records: data?.records ?? [], total: data?.total ?? 0, isLoading, isDemoMode }
}

export function useN8nConnections() {
  const { data, isLoading, isDemoMode } = useApiResource<N8nConnection[]>(
    async (api) => {
      const res = await api.listN8nConnections()
      return res.items
    },
    () => demoDataStore.getN8nConnections(),
  )
  return { connections: data ?? [], isLoading, isDemoMode }
}

export function useN8nWorkflows() {
  const { data, isLoading, isDemoMode } = useApiResource<any[]>(
    (api) => api.listN8nWorkflows(),
    () => demoDataStore.getN8nWorkflows(),
  )
  return { workflows: data ?? [], isLoading, isDemoMode }
}

export function useReplayBundles() {
  const { data, isLoading, isDemoMode } = useApiResource<any[]>(
    (api) => api.getReplayBundles(),
    () => demoDataStore.getReplayBundles(),
  )
  return { bundles: data ?? [], isLoading, isDemoMode }
}

interface DetectorStatusData {
  detectors: Array<{
    name: string
    readiness: 'production' | 'beta' | 'experimental' | 'failing' | 'untested'
    description: string
    enabled: boolean
    f1_score: number | null
    precision: number | null
    recall: number | null
    sample_count: number
    optimal_threshold: number | null
  }>
  summary: Record<string, number>
  calibrated_at: string
  readiness_criteria: Record<string, any>
}

export function useDetectorStatus() {
  const { data, isLoading, isDemoMode } = useApiResource<DetectorStatusData>(
    (api) => api.getDetectorStatus(),
    () => ({
      detectors: [],
      summary: {},
      calibrated_at: new Date().toISOString(),
      readiness_criteria: {},
    }),
  )
  return { data, isLoading, isDemoMode }
}

export function useCalibrationMonitor() {
  const { data, isLoading, isDemoMode } = useApiResource<{
    summary: {
      total_detectors_observed: number
      total_observations: number
      total_diagnose_runs: number
      detectors_with_alerts: number
      monitoring_since: string
      alert_count: number
    }
    detectors: Record<string, {
      total_observations: number
      detected_count: number
      detection_rate: number
      avg_confidence: number
      confidence_distribution: { high: number; likely: number; possible: number; low: number }
      severity_distribution: Record<string, number>
      avg_detection_time_ms: number
      alerts: Array<{ type: string; message: string; severity: string }>
    }>
    alerts: Array<{ type: string; message: string; severity: string; detector?: string }>
  }>(
    (api) => api.getCalibrationMonitor(),
    () => ({
      summary: {
        total_detectors_observed: 0,
        total_observations: 0,
        total_diagnose_runs: 0,
        detectors_with_alerts: 0,
        monitoring_since: new Date().toISOString(),
        alert_count: 0,
      },
      detectors: {},
      alerts: [],
    }),
  )
  return { data, isLoading, isDemoMode }
}

export function useICPDetectors() {
  const { data, isLoading, isDemoMode } = useApiResource<{
    tier: string
    total_detectors: number
    failure_modes_covered: number
    detectors: Array<{
      name: string
      module: string
      failure_mode: string | null
      failure_mode_title: string | null
      tier: string
    }>
  }>(
    (api) => api.getICPDetectors(),
    () => ({
      tier: 'icp',
      total_detectors: 0,
      failure_modes_covered: 0,
      detectors: [],
    }),
  )
  return { data, isLoading, isDemoMode }
}

// ============================================================================
// MULTI-FETCH HOOKS (use factory with composite return)
// ============================================================================

export function useThresholdTuning() {
  const { data, isLoading, isDemoMode } = useApiResource<{ feedbackStats: any; recommendations: any[] }>(
    async (api) => {
      const [stats, recs] = await Promise.all([
        api.getFeedbackStats(),
        api.getThresholdRecommendations(),
      ])
      return { feedbackStats: stats, recommendations: recs }
    },
    () => ({
      feedbackStats: demoDataStore.getFeedbackStats(),
      recommendations: demoDataStore.getThresholdRecommendations(),
    }),
  )
  return {
    feedbackStats: data?.feedbackStats ?? null,
    recommendations: data?.recommendations ?? [],
    isLoading,
    isDemoMode,
  }
}

export function useChaosExperiments() {
  const { data, isLoading, isDemoMode } = useApiResource<{ sessions: any[]; experimentTypes: any[] }>(
    async (api) => {
      const [sessionData, types] = await Promise.all([
        api.listChaosSessions(),
        api.getChaosExperimentTypes(),
      ])
      return { sessions: sessionData, experimentTypes: types }
    },
    () => ({
      sessions: demoDataStore.getChaosSessions(),
      experimentTypes: demoDataStore.getChaosExperimentTypes(),
    }),
  )
  return {
    sessions: data?.sessions ?? [],
    experimentTypes: data?.experimentTypes ?? [],
    isLoading,
    isDemoMode,
  }
}

export function useTestingDashboard() {
  const { data, isLoading, isDemoMode } = useApiResource<{ accuracyMetrics: any[]; integrationStatus: any[] }>(
    async (api) => {
      const [metrics, status] = await Promise.all([
        api.getAccuracyMetrics(),
        api.getIntegrationStatus(),
      ])
      return { accuracyMetrics: metrics, integrationStatus: status }
    },
    () => ({
      accuracyMetrics: demoDataStore.getAccuracyMetrics(),
      integrationStatus: demoDataStore.getIntegrationStatus(),
    }),
  )
  return {
    accuracyMetrics: data?.accuracyMetrics ?? [],
    integrationStatus: data?.integrationStatus ?? [],
    isLoading,
    isDemoMode,
  }
}

// ============================================================================
// ACTION-BASED HOOKS (unique patterns, kept as-is)
// ============================================================================

/**
 * Hook for evaluation results with demo fallback
 */
export function useEvaluation(mode: 'standard' | 'quick' | 'llm-judge' = 'standard') {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [result, setResult] = useState<EvalResult | QuickEvalResult | LLMJudgeResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isDemoMode, setIsDemoMode] = useState(false)

  const runEvaluation = useCallback(async () => {
    setIsLoading(true)
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      let data
      const demoOutput = 'Sample agent output for evaluation'
      const demoContext = 'Sample context for evaluation'

      if (mode === 'quick') {
        data = await api.quickEval(demoOutput, demoContext)
      } else if (mode === 'llm-judge') {
        data = await api.llmJudgeEval(demoOutput, 'relevance', 'gpt-4o-mini', demoContext)
      } else {
        data = await api.evaluate(demoOutput, ['relevance', 'coherence', 'helpfulness', 'safety'], demoContext)
      }

      setResult(data)
      setIsDemoMode(false)
    } catch {
      let demoResult
      if (mode === 'quick') {
        demoResult = generateDemoQuickEvalResult()
      } else if (mode === 'llm-judge') {
        demoResult = generateDemoLLMJudgeResult()
      } else {
        demoResult = generateDemoEvalResult()
      }
      setResult(demoResult)
      setIsDemoMode(true)
    }
    setIsLoading(false)
  }, [getToken, tenantId, mode])

  return { result, isLoading, isDemoMode, runEvaluation }
}

/**
 * Hook for security checks with demo fallback
 */
export function useSecurityChecks(messageInput?: string) {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [injectionCheck, setInjectionCheck] = useState<any | null>(null)
  const [hallucinationCheck, setHallucinationCheck] = useState<any | null>(null)
  const [overflowCheck, setOverflowCheck] = useState<any | null>(null)
  const [costCalc, setCostCalc] = useState<any | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isDemoMode, setIsDemoMode] = useState(false)

  const runChecks = useCallback(
    async (message: string, model: string = 'gpt-4') => {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token, tenantId)

        const [injection, hallucination, overflow, cost] = await Promise.all([
          api.checkInjection(message),
          api.checkHallucination(message),
          api.checkOverflow(message.length, model),
          api.calculateCost(model, message.length, 0),
        ])

        setInjectionCheck(injection)
        setHallucinationCheck(hallucination)
        setOverflowCheck(overflow)
        setCostCalc(cost)
        setIsDemoMode(false)
      } catch {
        const { generateDemoInjectionCheck, generateDemoHallucinationCheck, generateDemoOverflowCheck, generateDemoCostCalculation } = require('@/lib/demo-data')
        setInjectionCheck(generateDemoInjectionCheck(message))
        setHallucinationCheck(generateDemoHallucinationCheck())
        setOverflowCheck(generateDemoOverflowCheck(model))
        setCostCalc(generateDemoCostCalculation(model))
        setIsDemoMode(true)
      }
      setIsLoading(false)
    },
    [getToken, tenantId]
  )

  return { injectionCheck, hallucinationCheck, overflowCheck, costCalc, isLoading, isDemoMode, runChecks }
}

// ============================================================================
// DETAIL HOOKS (unique patterns, kept as-is)
// ============================================================================

/**
 * Hook for single trace detail with states
 */
export function useTraceDetail(traceId: string) {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [trace, setTrace] = useState<Trace | null>(null)
  const [states, setStates] = useState<any[]>([])
  const [detections, setDetections] = useState<Detection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token, tenantId)
        const [traceData, statesData, detectionsResponse] = await Promise.all([
          api.getTrace(traceId),
          api.getTraceStates(traceId),
          api.getDetections({ traceId }),
        ])
        setTrace(traceData)
        setStates(statesData)
        setDetections(detectionsResponse.items)
        setIsDemoMode(false)
      } catch {
        const demoTrace = demoDataStore.getTrace(traceId)
        if (demoTrace) {
          setTrace(demoTrace)
          setStates(demoDataStore.getStatesForTrace(traceId))
          setDetections(demoDataStore.getDetectionsForTrace(traceId))
          setIsDemoMode(true)
        }
      }
      setIsLoading(false)
    }
    load()
  }, [getToken, tenantId, traceId])

  return { trace, states, detections, isLoading, isDemoMode }
}

/**
 * Hook for single detection detail with fix suggestions
 */
export function useDetectionDetail(detectionId: string) {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [detection, setDetection] = useState<Detection | null>(null)
  const [healingRecord, setHealingRecord] = useState<HealingRecord | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token, tenantId)
        const detectionData = await api.getDetection(detectionId)
        setDetection(detectionData)

        try {
          const healingRecords = await api.listHealingRecords({ detectionId })
          setHealingRecord(healingRecords.items.length > 0 ? healingRecords.items[0] : null)
        } catch {
          setHealingRecord(null)
        }

        setIsDemoMode(false)
      } catch {
        const demoDetection = demoDataStore.getDetection(detectionId)
        if (demoDetection) {
          setDetection(demoDetection)
          setHealingRecord(demoDataStore.getHealingForDetection(detectionId) || null)
          setIsDemoMode(true)
        }
      }
      setIsLoading(false)
    }
    load()
  }, [getToken, tenantId, detectionId])

  return { detection, healingRecord, isLoading, isDemoMode }
}
