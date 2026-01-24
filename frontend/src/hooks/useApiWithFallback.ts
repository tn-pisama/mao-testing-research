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
} from '@/lib/demo-data'
import type { LoopAnalytics, CostAnalytics, Detection, Trace, QualityAssessment } from '@/lib/api'

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
    setLoopAnalytics(generateDemoLoopAnalytics())
    setCostAnalytics(generateDemoCostAnalytics())
    setDetections(generateDemoDetections(8))
    setTraces(generateDemoTraces(10))
    setQualityAssessments([])
    setIsDemoMode(true)
    setError(null)
  }, [])

  const loadRealData = useCallback(async () => {
    try {
      const token = await getToken()
      const api = createApiClient(token, tenantId)

      // Add .catch() to ALL promises to handle partial failures gracefully
      const [loops, cost, dets, trc, qualityRes] = await Promise.all([
        api.getLoopAnalytics(30).catch(() => undefined),
        api.getCostAnalytics(30).catch(() => undefined),
        api.getDetections({ perPage: 10 }).catch(() => []),
        api.getTraces({ perPage: 10 }).catch(() => ({ traces: [], total: 0 })),
        api.listQualityAssessments({ pageSize: 20 }).catch(() => ({ assessments: [] })),
      ])

      // Only update state if still mounted
      if (!isMountedRef.current) return false

      setLoopAnalytics(loops)
      setCostAnalytics(cost)
      setDetections(dets)
      setTraces(trc.traces)
      setQualityAssessments(qualityRes.assessments)
      setIsDemoMode(false)
      setError(null)
      return true
    } catch (err) {
      console.warn('API unavailable, falling back to demo mode:', err)
      if (isMountedRef.current) {
        setError('Unable to connect to API. Showing demo data.')
      }
      return false
    }
  }, [getToken, tenantId])

  const refresh = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    const dataSuccess = await loadRealData()
    if (!dataSuccess && isMountedRef.current) {
      loadDemoData()
    }

    if (isMountedRef.current) {
      setIsLoading(false)
    }
  }, [loadRealData, loadDemoData])

  // Initial load effect - runs once on mount
  useEffect(() => {
    isMountedRef.current = true

    if (!hasLoadedRef.current) {
      hasLoadedRef.current = true
      refresh()
    }

    // Cleanup on unmount
    return () => {
      isMountedRef.current = false
    }
  }, []) // Empty dependency - only run on mount

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
        setDetections(generateDemoDetections(params?.perPage || 20))
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
        const demoTraces = generateDemoTraces(params?.perPage || 20)
        setTraces(demoTraces)
        setTotal(demoTraces.length)
        setIsDemoMode(true)
      }
      setIsLoading(false)
    }
    load()
  }, [getToken, tenantId, params])

  return { traces, total, isLoading, isDemoMode }
}
