// ---------------------------------------------------------------------------
// Barrel re-exports: all types from every domain module
// ---------------------------------------------------------------------------

// Client / base
export { fetchApi } from './client'
export type { FetchOptions, ApiError } from './client'

// Traces
export type { Trace, State, TraceListResponse } from './traces'

// Detections
export type {
  Detection,
  DetectionListResponse,
  CodeChange,
  FixSuggestion,
  FixSuggestionsResponse,
  FixSuggestionSummary,
  ApplyFixResult,
  SourceFix,
} from './detections'

// Healing
export type {
  HealingRecord,
  HealingListResponse,
  TriggerHealingRequest,
  TriggerHealingResponse,
  ApproveHealingRequest,
  ApproveHealingResponse,
  RollbackResponse,
  N8nConnection,
  N8nConnectionListResponse,
  CreateN8nConnectionRequest,
  ApplyFixToN8nRequest,
  ApplyFixToN8nResponse,
  WorkflowDiff,
  PromoteResponse,
  RejectResponse,
  VerifyRequest,
  VerifyResponse,
  VerificationMetrics,
  WorkflowVersion,
  VersionHistoryResponse,
  RestoreVersionResponse,
} from './healing'

// Diagnose
export type {
  DiagnoseDetection,
  DiagnoseAutoFix,
  DiagnoseResult,
  DiagnoseQuickCheckResult,
} from './diagnose'

// Quality
export type {
  QualityDimensionScore,
  AgentQualityScore,
  ComplexityMetrics,
  OrchestrationQualityScore,
  QualityImprovement,
  QualityAssessment,
  QualityAssessmentListResponse,
  QualityDimensionInfo,
  QualityDimensionsResponse,
  QualityHealingRecord,
  QualityHealingListResponse,
  QualityHealingTriggerResponse,
} from './quality'

// Evals
export type {
  EvalResult,
  QuickEvalResult,
  LLMJudgeResult,
  CustomScorer,
  ScorerResult,
  ScorerRunSummary,
  ConversationEvaluation,
} from './evals'

// Analytics
export type { LoopAnalytics, CostAnalytics } from './analytics'

// Testing
export type {
  AccuracyMetric,
  IntegrationStatus,
  HandoffAnalysis,
  Handoff,
  AssertionResult,
  GeneratedTestSuite,
} from './testing'

// Replay
export type { ReplayBundle, ReplayResult, ReplayDiff } from './replay'

// Regression
export type { Baseline, DriftAlert, ModelFingerprint } from './regression'

// Chaos
export type {
  ChaosSession,
  ChaosExperimentType,
  ChaosExperimentConfig,
  ChaosTargetConfig,
  ChaosSafetyConfig,
} from './chaos'

// Security
export type {
  InjectionCheckResult,
  HallucinationCheckResult,
  OverflowCheckResult,
  CostCalculation,
} from './security'

// Integrations
export type {
  N8nWorkflow,
  OpenClawInstance,
  OpenClawAgent,
  DifyInstance,
  DifyApp,
  LangGraphDeployment,
  LangGraphAssistant,
} from './integrations'

// Memory
export type {
  CognitiveMemoryItem,
  ScoredMemory,
  MemoryTreeNode,
  MemoryStats,
} from './memory'

// Tenants / Settings
export type {
  FeedbackStats,
  ThresholdRecommendation,
  ImportJob,
  MetricsExport,
  AutoDetectRule,
  AutoDetectRules,
  WorkflowGroup,
  CreateGroupRequest,
  AssignWorkflowsRequest,
  AutoDetectResponse,
} from './tenants'

// ---------------------------------------------------------------------------
// Domain API factories (internal, used only by createApiClient)
// ---------------------------------------------------------------------------

import { createTracesApi } from './traces'
import { createDetectionsApi } from './detections'
import { createHealingApi } from './healing'
import { createDiagnoseApi } from './diagnose'
import { createQualityApi } from './quality'
import { createEvalsApi } from './evals'
import { createAgentsApi } from './agents'
import { createAnalyticsApi } from './analytics'
import { createTestingApi } from './testing'
import { createReplayApi } from './replay'
import { createRegressionApi } from './regression'
import { createChaosApi } from './chaos'
import { createSecurityApi } from './security'
import { createIntegrationsApi } from './integrations'
import { createMemoryApi } from './memory'
import { createTenantsApi } from './tenants'

// ---------------------------------------------------------------------------
// Public API client factory -- identical signature to the original
// ---------------------------------------------------------------------------

export function createApiClient(token?: string | null, tenantId?: string | null) {
  const opts = { token, tenantId }

  return {
    ...createTracesApi(opts),
    ...createDetectionsApi(opts),
    ...createHealingApi(opts),
    ...createDiagnoseApi(opts),
    ...createQualityApi(opts),
    ...createEvalsApi(opts),
    ...createAgentsApi(opts),
    ...createAnalyticsApi(opts),
    ...createTestingApi(opts),
    ...createReplayApi(opts),
    ...createRegressionApi(opts),
    ...createChaosApi(opts),
    ...createSecurityApi(opts),
    ...createIntegrationsApi(opts),
    ...createMemoryApi(opts),
    ...createTenantsApi(opts),
  }
}

/** Default client instance (no auth, no tenant) */
export const api = createApiClient()
