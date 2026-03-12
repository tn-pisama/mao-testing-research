'use client'

import { useQuery, useMutation, useQueryClient, type UseQueryOptions } from '@tanstack/react-query'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient } from '@/lib/api'
import type {
  Trace,
  Detection,
  LoopAnalytics,
  CostAnalytics,
  HealingRecord,
  QualityAssessment,
  N8nConnection,
} from '@/lib/api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type ApiClient = ReturnType<typeof createApiClient>

/** Returns a memoisation-safe API client builder */
function useApiClient(): () => Promise<ApiClient> {
  const { getToken } = useAuth()
  const { tenantId } = useTenant()
  return async () => {
    const token = await getToken()
    return createApiClient(token, tenantId)
  }
}

// ---------------------------------------------------------------------------
// Query keys – centralised so invalidation is straightforward
// ---------------------------------------------------------------------------

export const queryKeys = {
  traces: (params?: Record<string, unknown>) => ['traces', params] as const,
  trace: (id: string) => ['trace', id] as const,
  traceStates: (traceId: string) => ['traceStates', traceId] as const,
  detections: (params?: Record<string, unknown>) => ['detections', params] as const,
  detection: (id: string) => ['detection', id] as const,
  loopAnalytics: (days: number) => ['loopAnalytics', days] as const,
  costAnalytics: (days: number) => ['costAnalytics', days] as const,
  healingRecords: (params?: Record<string, unknown>) => ['healingRecords', params] as const,
  qualityAssessments: (params?: Record<string, unknown>) => ['qualityAssessments', params] as const,
  n8nConnections: () => ['n8nConnections'] as const,
  detectorStatus: () => ['detectorStatus'] as const,
  feedbackStats: () => ['feedbackStats'] as const,
  thresholdRecommendations: () => ['thresholdRecommendations'] as const,
} as const

// ---------------------------------------------------------------------------
// Query hooks
// ---------------------------------------------------------------------------

export function useTracesQuery(params?: {
  page?: number
  perPage?: number
  status?: string
}) {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.traces(params as Record<string, unknown>),
    queryFn: async () => {
      const api = await getApi()
      return api.getTraces(params ?? {})
    },
  })
}

export function useTraceQuery(traceId: string) {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.trace(traceId),
    queryFn: async () => {
      const api = await getApi()
      return api.getTrace(traceId)
    },
    enabled: !!traceId,
  })
}

export function useTraceStatesQuery(traceId: string) {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.traceStates(traceId),
    queryFn: async () => {
      const api = await getApi()
      return api.getTraceStates(traceId)
    },
    enabled: !!traceId,
  })
}

export function useDetectionsQuery(params?: {
  page?: number
  perPage?: number
  type?: string
  traceId?: string
  confidenceMin?: number
  confidenceMax?: number
  dateFrom?: string
  dateTo?: string
}) {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.detections(params as Record<string, unknown>),
    queryFn: async () => {
      const api = await getApi()
      return api.getDetections(params ?? {})
    },
  })
}

export function useDetectionQuery(detectionId: string) {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.detection(detectionId),
    queryFn: async () => {
      const api = await getApi()
      return api.getDetection(detectionId)
    },
    enabled: !!detectionId,
  })
}

export function useLoopAnalyticsQuery(days: number = 30) {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.loopAnalytics(days),
    queryFn: async () => {
      const api = await getApi()
      return api.getLoopAnalytics(days)
    },
  })
}

export function useCostAnalyticsQuery(days: number = 30) {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.costAnalytics(days),
    queryFn: async () => {
      const api = await getApi()
      return api.getCostAnalytics(days)
    },
  })
}

export function useHealingRecordsQuery(params?: {
  page?: number
  perPage?: number
  status?: string
  detectionId?: string
}) {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.healingRecords(params as Record<string, unknown>),
    queryFn: async () => {
      const api = await getApi()
      return api.listHealingRecords(params)
    },
  })
}

export function useQualityAssessmentsQuery(params?: {
  page?: number
  pageSize?: number
  minGrade?: string
  groupId?: string
}) {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.qualityAssessments(params as Record<string, unknown>),
    queryFn: async () => {
      const api = await getApi()
      return api.listQualityAssessments(params)
    },
  })
}

export function useN8nConnectionsQuery() {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.n8nConnections(),
    queryFn: async () => {
      const api = await getApi()
      const res = await api.listN8nConnections()
      return res.items
    },
  })
}

export function useDetectorStatusQuery() {
  const getApi = useApiClient()
  return useQuery({
    queryKey: queryKeys.detectorStatus(),
    queryFn: async () => {
      const api = await getApi()
      return api.getDetectorStatus()
    },
  })
}

// ---------------------------------------------------------------------------
// Mutation hooks
// ---------------------------------------------------------------------------

export function usePromoteHealingMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (healingId: string) => {
      const api = await getApi()
      return api.promoteHealing(healingId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['healingRecords'] })
    },
  })
}

export function useRejectHealingMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (healingId: string) => {
      const api = await getApi()
      return api.rejectHealing(healingId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['healingRecords'] })
    },
  })
}

export function useRollbackHealingMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (healingId: string) => {
      const api = await getApi()
      return api.rollbackHealing(healingId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['healingRecords'] })
    },
  })
}

export function useVerifyHealingMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ healingId, level }: { healingId: string; level?: number }) => {
      const api = await getApi()
      return api.verifyHealing(healingId, level ?? 1)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['healingRecords'] })
    },
  })
}
