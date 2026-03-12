'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSafeAuth as useAuth } from '@/hooks/useSafeAuth'
import { useTenant } from '@/hooks/useTenant'
import { createApiClient } from '@/lib/api'
import type {
  Trace,
  Detection,
  HealingRecord,
  N8nConnection,
  VerificationMetrics,
  WorkflowVersion,
  LoopAnalytics,
  CostAnalytics,
  QualityAssessment,
  QualityHealingRecord,
  QualityHealingListResponse,
  FixSuggestionSummary,
  FeedbackStats,
  ThresholdRecommendation,
  DifyInstance,
  DifyApp,
  LangGraphDeployment,
  LangGraphAssistant,
  OpenClawInstance,
  OpenClawAgent,
} from '@/lib/api'
import { demoDataStore } from '@/lib/demo-state'
import {
  generateDemoLoopAnalytics,
  generateDemoCostAnalytics,
  generateDemoDifyInstances,
  generateDemoDifyApps,
  generateDemoOpenClawInstances,
  generateDemoOpenClawAgents,
  generateDemoLangGraphDeployments,
  generateDemoLangGraphAssistants,
} from '@/lib/demo-data'

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

/**
 * Wraps TanStack Query with automatic demo-data fallback on API failure.
 * Demo mode state is stored alongside the data in the query cache so it
 * survives cache hits without extra useState.
 */
function useQueryWithFallback<T>({
  queryKey,
  queryFn,
  fallbackFn,
  enabled = true,
  refetchInterval,
}: {
  queryKey: readonly unknown[]
  queryFn: (api: ApiClient) => Promise<T>
  fallbackFn: () => T
  enabled?: boolean
  refetchInterval?: number | false
}) {
  const getApi = useApiClient()

  const query = useQuery({
    queryKey,
    queryFn: async (): Promise<{ data: T; isDemoMode: boolean }> => {
      try {
        const api = await getApi()
        const data = await queryFn(api)
        return { data, isDemoMode: false }
      } catch {
        return { data: fallbackFn(), isDemoMode: true }
      }
    },
    enabled,
    refetchInterval,
  })

  return {
    data: query.data?.data,
    isLoading: query.isLoading,
    isDemoMode: query.data?.isDemoMode ?? false,
    refetch: query.refetch,
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
  healingRecords: (params?: Record<string, unknown>) => ['healingRecords', params] as const,
  n8nConnections: () => ['n8nConnections'] as const,
  verificationMetrics: () => ['verificationMetrics'] as const,
  workflowVersions: (workflowId: string, connectionId: string) =>
    ['workflowVersions', workflowId, connectionId] as const,
  detectorStatus: () => ['detectorStatus'] as const,
  feedbackStats: () => ['feedbackStats'] as const,
  thresholdRecommendations: () => ['thresholdRecommendations'] as const,
  loopAnalytics: (days?: number) => ['loopAnalytics', days] as const,
  costAnalytics: (days?: number) => ['costAnalytics', days] as const,
  qualityAssessments: (params?: Record<string, unknown>) => ['qualityAssessments', params] as const,
  qualityAssessment: (id: string) => ['qualityAssessment', id] as const,
  qualityHealings: (assessmentId?: string) => ['qualityHealings', assessmentId] as const,
  n8nWorkflows: () => ['n8nWorkflows'] as const,
  difyInstances: () => ['difyInstances'] as const,
  difyApps: (instanceId?: string) => ['difyApps', instanceId] as const,
  langGraphDeployments: () => ['langGraphDeployments'] as const,
  langGraphAssistants: (deploymentId?: string) => ['langGraphAssistants', deploymentId] as const,
  openClawInstances: () => ['openClawInstances'] as const,
  openClawAgents: (instanceId?: string) => ['openClawAgents', instanceId] as const,
} as const

// ---------------------------------------------------------------------------
// Query hooks (with demo-data fallback)
// ---------------------------------------------------------------------------

export function useTracesQuery(params?: {
  page?: number
  perPage?: number
  status?: string
}) {
  const result = useQueryWithFallback<{ traces: Trace[]; total: number }>({
    queryKey: queryKeys.traces(params as Record<string, unknown>),
    queryFn: (api) => api.getTraces(params ?? {}),
    fallbackFn: () => {
      const allTraces = demoDataStore.getTraces()
      return {
        traces: allTraces.slice(0, params?.perPage || 20),
        total: allTraces.length,
      }
    },
  })

  return {
    traces: result.data?.traces ?? [],
    total: result.data?.total ?? 0,
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useTraceQuery(traceId: string) {
  return useQueryWithFallback<Trace | null>({
    queryKey: queryKeys.trace(traceId),
    queryFn: (api) => api.getTrace(traceId),
    fallbackFn: () => demoDataStore.getTrace(traceId) ?? null,
    enabled: !!traceId,
  })
}

export function useTraceStatesQuery(traceId: string) {
  return useQueryWithFallback<unknown[]>({
    queryKey: queryKeys.traceStates(traceId),
    queryFn: (api) => api.getTraceStates(traceId),
    fallbackFn: () => demoDataStore.getStatesForTrace(traceId),
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
  const result = useQueryWithFallback<{
    items: Detection[]
    total: number
    page: number
    per_page: number
  }>({
    queryKey: queryKeys.detections(params as Record<string, unknown>),
    queryFn: (api) => api.getDetections(params ?? {}),
    fallbackFn: () => {
      const all = demoDataStore.getDetections()
      const perPage = params?.perPage || 20
      return {
        items: all.slice(0, perPage),
        total: all.length,
        page: params?.page || 1,
        per_page: perPage,
      }
    },
  })

  return {
    detections: result.data?.items ?? [],
    total: result.data?.total ?? 0,
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useDetectionQuery(detectionId: string) {
  return useQueryWithFallback<Detection | null>({
    queryKey: queryKeys.detection(detectionId),
    queryFn: (api) => api.getDetection(detectionId),
    fallbackFn: () => demoDataStore.getDetection(detectionId) ?? null,
    enabled: !!detectionId,
  })
}

export function useHealingRecordsQuery(params?: {
  page?: number
  perPage?: number
  status?: string
  detectionId?: string
}) {
  const result = useQueryWithFallback<{
    items: HealingRecord[]
    total: number
  }>({
    queryKey: queryKeys.healingRecords(params as Record<string, unknown>),
    queryFn: async (api) => {
      const res = await api.listHealingRecords(params)
      return { items: res.items, total: res.total || res.items.length }
    },
    fallbackFn: () => {
      const allRecords = demoDataStore.getHealingRecords()
      let filtered = allRecords
      if (params?.status) filtered = allRecords.filter((r) => r.status === params.status)
      return { items: filtered.slice(0, params?.perPage || 20), total: filtered.length }
    },
  })

  return {
    records: result.data?.items ?? [],
    total: result.data?.total ?? 0,
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useN8nConnectionsQuery() {
  const result = useQueryWithFallback<N8nConnection[]>({
    queryKey: queryKeys.n8nConnections(),
    queryFn: async (api) => {
      const res = await api.listN8nConnections()
      return res.items
    },
    fallbackFn: () => demoDataStore.getN8nConnections(),
  })

  return {
    connections: result.data ?? [],
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useVerificationMetricsQuery() {
  return useQueryWithFallback<VerificationMetrics | null>({
    queryKey: queryKeys.verificationMetrics(),
    queryFn: (api) => api.getVerificationMetrics(),
    fallbackFn: () => null,
  })
}

export function useWorkflowVersionsQuery(workflowId: string, connectionId: string) {
  const result = useQueryWithFallback<WorkflowVersion[]>({
    queryKey: queryKeys.workflowVersions(workflowId, connectionId),
    queryFn: async (api) => {
      const res = await api.getWorkflowVersions(workflowId, connectionId)
      return res.versions || []
    },
    fallbackFn: () => [],
    enabled: !!workflowId && !!connectionId,
  })

  return {
    versions: result.data ?? [],
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useDetectorStatusQuery() {
  return useQueryWithFallback<{
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
    readiness_criteria: Record<string, unknown>
  }>({
    queryKey: queryKeys.detectorStatus(),
    queryFn: (api) => api.getDetectorStatus(),
    fallbackFn: () => ({
      detectors: [],
      summary: {},
      calibrated_at: new Date().toISOString(),
      readiness_criteria: {},
    }),
  })
}

export function useLoopAnalyticsQuery(days: number = 30) {
  return useQueryWithFallback<LoopAnalytics | null>({
    queryKey: queryKeys.loopAnalytics(days),
    queryFn: (api) => api.getLoopAnalytics(days),
    fallbackFn: () => generateDemoLoopAnalytics(),
  })
}

export function useCostAnalyticsQuery(days: number = 30) {
  return useQueryWithFallback<CostAnalytics | null>({
    queryKey: queryKeys.costAnalytics(days),
    queryFn: (api) => api.getCostAnalytics(days),
    fallbackFn: () => generateDemoCostAnalytics(),
  })
}

export function useQualityAssessmentsQuery(params?: {
  page?: number
  pageSize?: number
  minGrade?: string
  groupId?: string
}) {
  const result = useQueryWithFallback<{ assessments: QualityAssessment[]; total: number }>({
    queryKey: queryKeys.qualityAssessments(params as Record<string, unknown>),
    queryFn: async (api) => {
      const res = await api.listQualityAssessments(params)
      return { assessments: res.assessments, total: res.total || res.assessments.length }
    },
    fallbackFn: () => {
      const all = demoDataStore.getQualityAssessments()
      return { assessments: all.slice(0, params?.pageSize || 20), total: all.length }
    },
  })

  return {
    assessments: result.data?.assessments ?? [],
    total: result.data?.total ?? 0,
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useFeedbackStatsQuery() {
  return useQueryWithFallback<FeedbackStats>({
    queryKey: queryKeys.feedbackStats(),
    queryFn: (api) => api.getFeedbackStats(),
    fallbackFn: () => demoDataStore.getFeedbackStats() as unknown as FeedbackStats,
  })
}

export function useThresholdRecommendationsQuery() {
  return useQueryWithFallback<ThresholdRecommendation[]>({
    queryKey: queryKeys.thresholdRecommendations(),
    queryFn: (api) => api.getThresholdRecommendations(),
    fallbackFn: () => demoDataStore.getThresholdRecommendations() as unknown as ThresholdRecommendation[],
  })
}

export function useN8nWorkflowsQuery() {
  const result = useQueryWithFallback<unknown[]>({
    queryKey: queryKeys.n8nWorkflows(),
    queryFn: (api) => api.listN8nWorkflows(),
    fallbackFn: () => demoDataStore.getN8nWorkflows(),
  })

  return {
    workflows: result.data ?? [],
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useDifyInstancesQuery() {
  const result = useQueryWithFallback<DifyInstance[]>({
    queryKey: queryKeys.difyInstances(),
    queryFn: (api) => api.listDifyInstances(),
    fallbackFn: () => generateDemoDifyInstances(),
  })

  return {
    instances: result.data ?? [],
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useDifyAppsQuery(instanceId?: string) {
  const result = useQueryWithFallback<DifyApp[]>({
    queryKey: queryKeys.difyApps(instanceId),
    queryFn: (api) => api.listDifyApps(instanceId),
    fallbackFn: () => generateDemoDifyApps(),
  })

  return {
    apps: result.data ?? [],
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useLangGraphDeploymentsQuery() {
  const result = useQueryWithFallback<LangGraphDeployment[]>({
    queryKey: queryKeys.langGraphDeployments(),
    queryFn: (api) => api.listLangGraphDeployments(),
    fallbackFn: () => generateDemoLangGraphDeployments(),
  })

  return {
    deployments: result.data ?? [],
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useLangGraphAssistantsQuery(deploymentId?: string) {
  const result = useQueryWithFallback<LangGraphAssistant[]>({
    queryKey: queryKeys.langGraphAssistants(deploymentId),
    queryFn: (api) => api.listLangGraphAssistants(deploymentId),
    fallbackFn: () => generateDemoLangGraphAssistants(),
  })

  return {
    assistants: result.data ?? [],
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useOpenClawInstancesQuery() {
  const result = useQueryWithFallback<OpenClawInstance[]>({
    queryKey: queryKeys.openClawInstances(),
    queryFn: (api) => api.listOpenClawInstances(),
    fallbackFn: () => generateDemoOpenClawInstances(),
  })

  return {
    instances: result.data ?? [],
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useOpenClawAgentsQuery(instanceId?: string) {
  const result = useQueryWithFallback<OpenClawAgent[]>({
    queryKey: queryKeys.openClawAgents(instanceId),
    queryFn: (api) => api.listOpenClawAgents(instanceId),
    fallbackFn: () => generateDemoOpenClawAgents(),
  })

  return {
    agents: result.data ?? [],
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
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

export function useApproveHealingMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ healingId, approved, notes }: {
      healingId: string
      approved: boolean
      notes?: string
    }) => {
      const api = await getApi()
      return api.approveHealing(healingId, { approved, notes })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['healingRecords'] })
    },
  })
}

export function useCreateConnectionMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: { name: string; instance_url: string; api_key: string }) => {
      const api = await getApi()
      return api.createN8nConnection(data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['n8nConnections'] })
    },
  })
}

export function useTestConnectionMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (connectionId: string) => {
      const api = await getApi()
      return api.testN8nConnection(connectionId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['n8nConnections'] })
    },
  })
}

export function useDeleteConnectionMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (connectionId: string) => {
      const api = await getApi()
      return api.deleteN8nConnection(connectionId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['n8nConnections'] })
    },
  })
}

export function useRestoreVersionMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (versionId: string) => {
      const api = await getApi()
      return api.restoreVersion(versionId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflowVersions'] })
      queryClient.invalidateQueries({ queryKey: ['healingRecords'] })
    },
  })
}

export function useSubmitFeedbackMutation() {
  const getApi = useApiClient()

  return useMutation({
    mutationFn: async ({ detectionId, isValid }: { detectionId: string; isValid: boolean }) => {
      const api = await getApi()
      return api.submitFeedback(detectionId, isValid)
    },
  })
}

// ---------------------------------------------------------------------------
// Quality assessment detail + healing hooks
// ---------------------------------------------------------------------------

export function useQualityAssessmentDetailQuery(assessmentId: string) {
  const result = useQueryWithFallback<QualityAssessment | null>({
    queryKey: queryKeys.qualityAssessment(assessmentId),
    queryFn: (api) => api.getQualityAssessment(assessmentId),
    fallbackFn: () => {
      const all = demoDataStore.getQualityAssessments()
      return all.find(a => a.id === assessmentId) ?? all[0] ?? null
    },
    enabled: !!assessmentId,
  })
  return {
    assessment: result.data ?? null,
    isLoading: result.isLoading,
    isDemoMode: result.isDemoMode,
    refetch: result.refetch,
  }
}

export function useQualityHealingsQuery(assessmentId?: string) {
  const result = useQueryWithFallback<QualityHealingListResponse>({
    queryKey: queryKeys.qualityHealings(assessmentId),
    queryFn: (api) => api.listQualityHealings({ page: 1, page_size: 50 }),
    fallbackFn: () => ({ items: [], total: 0 }),
    enabled: !!assessmentId,
  })

  const matching = result.data?.items.find(
    (h: QualityHealingRecord) => h.assessment_id === assessmentId || h.id === assessmentId
  ) ?? null

  return {
    healingRecord: matching,
    allHealings: result.data?.items ?? [],
    isLoading: result.isLoading,
    refetch: result.refetch,
  }
}

export function useTriggerQualityHealingMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: {
      workflow: Record<string, unknown>
      options?: { threshold?: number; auto_apply?: boolean }
    }) => {
      const api = await getApi()
      return api.triggerQualityHealing(params.workflow, params.options)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['qualityHealings'] })
      queryClient.invalidateQueries({ queryKey: ['qualityAssessment'] })
    },
  })
}

export function useApproveQualityHealingMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (params: { healingId: string; fixIds: string[] }) => {
      const api = await getApi()
      return api.approveQualityHealing(params.healingId, params.fixIds)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['qualityHealings'] })
    },
  })
}

export function useRollbackQualityHealingMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (healingId: string) => {
      const api = await getApi()
      return api.rollbackQualityHealing(healingId)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['qualityHealings'] })
    },
  })
}

// ---------------------------------------------------------------------------
// Threshold mutations
// ---------------------------------------------------------------------------

export function useUpdateThresholdsMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: {
      framework_thresholds: Record<string, { structural_threshold: number; semantic_threshold: number }>
    }) => {
      const api = await getApi()
      return api.updateThresholds(data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feedbackStats'] })
      queryClient.invalidateQueries({ queryKey: ['thresholdRecommendations'] })
    },
  })
}

export function useResetThresholdsMutation() {
  const getApi = useApiClient()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const api = await getApi()
      return api.resetThresholds()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feedbackStats'] })
      queryClient.invalidateQueries({ queryKey: ['thresholdRecommendations'] })
    },
  })
}
