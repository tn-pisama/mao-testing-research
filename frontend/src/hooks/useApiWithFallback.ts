'use client'

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@clerk/nextjs'
import { createApiClient } from '@/lib/api'
import {
  generateDemoLoopAnalytics,
  generateDemoCostAnalytics,
  generateDemoDetections,
  generateDemoTraces,
} from '@/lib/demo-data'
import type { LoopAnalytics, CostAnalytics, Detection, Trace } from '@/lib/api'

export function useApiWithFallback() {
  const { getToken } = useAuth()
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [loopAnalytics, setLoopAnalytics] = useState<LoopAnalytics | undefined>()
  const [costAnalytics, setCostAnalytics] = useState<CostAnalytics | undefined>()
  const [detections, setDetections] = useState<Detection[]>([])
  const [traces, setTraces] = useState<Trace[]>([])

  const loadRealData = useCallback(async () => {
    try {
      const token = await getToken()
      const api = createApiClient(token)
      
      const [loops, cost, dets, trc] = await Promise.all([
        api.getLoopAnalytics(30),
        api.getCostAnalytics(30),
        api.getDetections({ perPage: 10 }),
        api.getTraces({ perPage: 10 }),
      ])
      
      setLoopAnalytics(loops)
      setCostAnalytics(cost)
      setDetections(dets)
      setTraces(trc.traces)
      setIsDemoMode(false)
      setError(null)
      return true
    } catch (err) {
      console.warn('API unavailable, falling back to demo mode:', err)
      return false
    }
  }, [getToken])

  const loadDemoData = useCallback(() => {
    setLoopAnalytics(generateDemoLoopAnalytics())
    setCostAnalytics(generateDemoCostAnalytics())
    setDetections(generateDemoDetections(8))
    setTraces(generateDemoTraces(10))
    setIsDemoMode(true)
  }, [])

  const refresh = useCallback(async () => {
    setIsLoading(true)
    
    const dataSuccess = await loadRealData()
    if (!dataSuccess) {
      loadDemoData()
    }
    
    setIsLoading(false)
  }, [loadRealData, loadDemoData])

  useEffect(() => {
    refresh()
  }, [refresh])

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
    refresh,
    toggleDemoMode,
  }
}

export function useDetections(params?: { page?: number; perPage?: number; type?: string }) {
  const { getToken } = useAuth()
  const [detections, setDetections] = useState<Detection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token)
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
  }, [getToken, params])

  return { detections, isLoading, isDemoMode }
}

export function useTraces(params?: { page?: number; perPage?: number; status?: string }) {
  const { getToken } = useAuth()
  const [traces, setTraces] = useState<Trace[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)

  useEffect(() => {
    async function load() {
      setIsLoading(true)
      try {
        const token = await getToken()
        const api = createApiClient(token)
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
  }, [getToken, params])

  return { traces, total, isLoading, isDemoMode }
}
