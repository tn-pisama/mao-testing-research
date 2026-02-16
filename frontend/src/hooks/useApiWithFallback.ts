'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient } from '@/lib/api'
import {
  generateDemoLoopAnalytics,
  generateDemoCostAnalytics,
  generateDemoDetections,
  generateDemoTraces,
  generateDemoQualityAssessments,
  generateDemoHealingRecords,
  generateDemoN8nConnections,
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

export function useApiWithFallback() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [loopAnalytics, setLoopAnalytics] = useState<LoopAnalytics | undefined>()
  const [costAnalytics, setCostAnalytics] = useState<CostAnalytics | undefined>()
  const [detections, setDetections] = useState<Detection[]>([])
  const [traces, setTraces] = useState<Trace[]>([])
  const [qualityAssessments, setQualityAssessments] = useState<QualityAssessment[]>([])

  // Prevent double-loading on mount
  const hasLoadedRef = useRef(false)
  const isMountedRef = useRef(true)

  const loadDemoData = useCallback(() => {
    console.warn('🎭 API unavailable, loading demo mode data')
    console.log('🎭 isMountedRef.current:', isMountedRef.current)

    const demoLoop = generateDemoLoopAnalytics()
    const demoCost = generateDemoCostAnalytics()
    const demoDets = demoDataStore.getDetections().slice(0, 10)
    const demoTraces = demoDataStore.getTraces().slice(0, 10)
    const demoQuality = demoDataStore.getQualityAssessments().slice(0, 5)

    console.log('🎭 Demo data loaded:', {
      loops: !!demoLoop,
      cost: !!demoCost,
      detections: demoDets.length,
      traces: demoTraces.length,
      quality: demoQuality.length
    })

    setLoopAnalytics(demoLoop)
    setCostAnalytics(demoCost)
    setDetections(demoDets)
    setTraces(demoTraces)
    setQualityAssessments(demoQuality)
    setIsDemoMode(true)
    setError(null)
  }, [])

  const loadRealData = useCallback(async () => {
    try {
      console.log('🌐 Loading real data for tenantId:', tenantId)
      const token = await getToken()
      console.log('🔑 Token obtained:', !!token)

      const api = createApiClient(token, tenantId)

      // Add .catch() to ALL promises to handle partial failures gracefully
      const [loops, cost, dets, trc, qualityRes] = await Promise.all([
        api.getLoopAnalytics(30).catch((err) => {
          console.warn('Loop analytics failed:', err.message)
          return null
        }),
        api.getCostAnalytics(30).catch((err) => {
          console.warn('Cost analytics failed:', err.message)
          return null
        }),
        api.getDetections({ perPage: 10 }).catch((err) => {
          console.warn('Detections failed:', err.message)
          return null
        }),
        api.getTraces({ perPage: 10 }).catch((err) => {
          console.warn('Traces failed:', err.message)
          return null
        }),
        api.listQualityAssessments({ pageSize: 20 }).catch((err) => {
          console.warn('Quality assessments failed:', err.message)
          return null
        }),
      ])

      // Only update state if still mounted
      if (!isMountedRef.current) {
        console.log('⚠️ Component unmounted, skipping state update')
        return false
      }

      // Check if we got any real data
      // If at least one API call succeeded with non-empty data, consider it a success
      const hasAnyData = !!(
        loops ||
        cost ||
        (dets && dets.length > 0) ||
        (trc && trc.traces && trc.traces.length > 0) ||
        (qualityRes && qualityRes.assessments && qualityRes.assessments.length > 0)
      )

      console.log('📊 API data check:', {
        loops: !!loops,
        cost: !!cost,
        detections: dets?.length || 0,
        traces: trc?.traces?.length || 0,
        quality: qualityRes?.assessments?.length || 0,
        hasAnyData
      })

      if (!hasAnyData) {
        // All API calls failed or returned empty - trigger demo mode
        console.warn('⚠️ API returned no data, falling back to demo mode')
        if (isMountedRef.current) {
          setError('Unable to load data from API. Showing demo data.')
        }
        return false
      }

      // We have at least some real data - use it
      console.log('✅ Using real data from API')
      setLoopAnalytics(loops || undefined)
      setCostAnalytics(cost || undefined)
      setDetections(dets || [])
      setTraces(trc?.traces || [])
      setQualityAssessments(qualityRes?.assessments || [])
      setIsDemoMode(false)
      setError(null)
      return true
    } catch (err) {
      console.warn('❌ API unavailable, falling back to demo mode:', err)
      if (isMountedRef.current) {
        setError('Unable to connect to API. Showing demo data.')
      }
      return false
    }
  }, [getToken, tenantId])

  const refresh = useCallback(async () => {
    console.log('🔄 Refreshing data, tenantId:', tenantId, 'isDemoMode:', isDemoMode)
    setIsLoading(true)
    setError(null)

    const dataSuccess = await loadRealData()
    console.log('✅ loadRealData result:', dataSuccess)

    if (!dataSuccess && isMountedRef.current) {
      console.log('📦 Loading demo data...')
      loadDemoData()
    }

    if (isMountedRef.current) {
      setIsLoading(false)
    }
  }, [loadRealData, loadDemoData, tenantId, isDemoMode])

  // Load data on mount and when tenant changes
  useEffect(() => {
    console.log('🎬 useEffect triggered, tenantId:', tenantId)
    isMountedRef.current = true

    // Call refresh whenever tenantId changes
    refresh()

    // Cleanup on unmount
    return () => {
      isMountedRef.current = false
    }
  }, [refresh, tenantId]) // Re-run when refresh or tenantId changes

  const toggleDemoMode = useCallback(() => {
    if (isDemoMode) {
      refresh()
    } else {
      loadDemoData()
    }
  }, [isDemoMode, refresh, loadDemoData])

  return {
    isLoading,
    isDemoMode,
    error,
    loopAnalytics,
    costAnalytics,
    detections,
    traces,
    qualityAssessments,
    refresh,
    toggleDemoMode,
  }
}

export function useDetections(params?: { page?: number; perPage?: number; type?: string }) {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [detections, setDetections] = useState<Detection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token, tenantId)
        const data = await api.getDetections(params || {})
        setDetections(data)
        setIsDemoMode(false)
      } catch {
        const allDetections = demoDataStore.getDetections()
        setDetections(allDetections.slice(0, params?.perPage || 20))
        setIsDemoMode(true)
      }
      setIsLoading(false)
    }
    load()
  }, [getToken, tenantId, params])

  return { detections, isLoading, isDemoMode }
}

export function useTraces(params?: { page?: number; perPage?: number; status?: string }) {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [traces, setTraces] = useState<Trace[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token, tenantId)
        const data = await api.getTraces(params || {})
        setTraces(data.traces)
        setTotal(data.total)
        setIsDemoMode(false)
      } catch {
        const allTraces = demoDataStore.getTraces()
        const demoTraces = allTraces.slice(0, params?.perPage || 20)
        setTraces(demoTraces)
        setTotal(allTraces.length)
        setIsDemoMode(true)
      }
      setIsLoading(false)
    }
    load()
  }, [getToken, tenantId, params])

  return { traces, total, isLoading, isDemoMode }
}

/**
 * Hook for quality assessments with demo fallback
 */
export function useQualityAssessments(params?: { page?: number; pageSize?: number; minGrade?: string }) {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [assessments, setAssessments] = useState<QualityAssessment[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token, tenantId)
        const data = await api.listQualityAssessments(params || {})
        setAssessments(data.assessments)
        setTotal(data.total || data.assessments.length)
        setIsDemoMode(false)
      } catch {
        const allAssessments = demoDataStore.getQualityAssessments()
        const pageSize = params?.pageSize || 20
        setAssessments(allAssessments.slice(0, pageSize))
        setTotal(allAssessments.length)
        setIsDemoMode(true)
      }
      setIsLoading(false)
    }
    load()
  }, [getToken, tenantId, params])

  return { assessments, total, isLoading, isDemoMode }
}

/**
 * Hook for healing records with demo fallback
 */
export function useHealingRecords(params?: { page?: number; pageSize?: number; status?: string }) {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [records, setRecords] = useState<HealingRecord[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token, tenantId)
        const data = await api.listHealingRecords(params || {})
        setRecords(data.items)
        setTotal(data.total || data.items.length)
        setIsDemoMode(false)
      } catch {
        const allRecords = demoDataStore.getHealingRecords()
        let filteredRecords = allRecords

        // Apply status filter if provided
        if (params?.status) {
          filteredRecords = allRecords.filter((r) => r.status === params.status)
        }

        const pageSize = params?.pageSize || 20
        setRecords(filteredRecords.slice(0, pageSize))
        setTotal(filteredRecords.length)
        setIsDemoMode(true)
      }
      setIsLoading(false)
    }
    load()
  }, [getToken, tenantId, params])

  return { records, total, isLoading, isDemoMode }
}

/**
 * Hook for N8n connections with demo fallback
 */
export function useN8nConnections() {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  const [connections, setConnections] = useState<N8nConnection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token, tenantId)
        const data = await api.listN8nConnections()
        setConnections(data.items)
        setIsDemoMode(false)
      } catch {
        setConnections(demoDataStore.getN8nConnections())
        setIsDemoMode(true)
      }
      setIsLoading(false)
    }
    load()
  }, [getToken, tenantId])

  return { connections, isLoading, isDemoMode }
}

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
      // Generate demo result based on mode
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
        const [traceData, statesData, detectionsData] = await Promise.all([
          api.getTrace(traceId),
          api.getTraceStates(traceId),
          api.getDetections({ traceId }),
        ])
        setTrace(traceData)
        setStates(statesData)
        setDetections(detectionsData)
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

        // Try to load healing record if it exists
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
