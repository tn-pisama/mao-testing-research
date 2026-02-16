/**
 * Centralized demo data store with correlated relationships
 *
 * This ensures that mock data feels realistic by maintaining relationships:
 * - Detections link to actual traces
 * - Healing records link to actual detections
 * - Quality assessments can reference real traces
 */

import {
  generateDemoTraces,
  generateDemoDetections,
  generateDemoQualityAssessments,
  generateDemoHealingRecords,
  generateDemoN8nConnections,
  generateDemoWorkflowVersions,
  generateDemoStates,
  generateDemoN8nWorkflows,
  generateDemoChaosSessions,
  generateDemoChaosExperimentTypes,
  generateDemoReplayBundles,
  generateDemoAccuracyMetrics,
  generateDemoFeedbackStats,
  generateDemoThresholdRecommendations,
  generateDemoIntegrationStatus,
  generateDemoBaselines,
  generateDemoDriftAlerts,
  QualityAssessment,
  HealingRecord,
  N8nConnection,
  WorkflowVersion,
  N8nWorkflow,
  ChaosSession,
  ChaosExperimentType,
  ReplayBundle,
  AccuracyMetric,
  FeedbackStats,
  ThresholdRecommendation,
  IntegrationStatus,
  Baseline,
  DriftAlert,
} from './demo-data'
import { Trace, Detection, State } from './api'

class DemoDataStore {
  private traces: Trace[] = []
  private detections: Detection[] = []
  private states: Map<string, State[]> = new Map()
  private qualityAssessments: QualityAssessment[] = []
  private healingRecords: HealingRecord[] = []
  private n8nConnections: N8nConnection[] = []
  private workflowVersions: Map<string, WorkflowVersion[]> = new Map()

  // New demo data types
  private n8nWorkflows: N8nWorkflow[] = []
  private chaosSessions: ChaosSession[] = []
  private chaosExperimentTypes: ChaosExperimentType[] = []
  private replayBundles: ReplayBundle[] = []
  private accuracyMetrics: AccuracyMetric[] = []
  private feedbackStats: FeedbackStats | null = null
  private thresholdRecommendations: ThresholdRecommendation[] = []
  private integrationStatus: IntegrationStatus[] = []
  private baselines: Baseline[] = []
  private driftAlerts: DriftAlert[] = []

  private initialized = false

  /**
   * Initialize the data store with correlated demo data
   */
  initialize() {
    if (this.initialized) return

    // Generate base traces
    this.traces = generateDemoTraces(50)

    // Generate states for each trace
    this.traces.forEach((trace) => {
      const stateCount = trace.state_count || 10
      const states = generateDemoStates(trace.id, stateCount)
      this.states.set(trace.id, states)
    })

    // Generate detections linked to traces
    this.detections = this.traces.flatMap((trace) => {
      const detectionCount = trace.detection_count || Math.floor(Math.random() * 3)
      if (detectionCount === 0) return []

      return Array.from({ length: detectionCount }, () => {
        const detection = generateDemoDetections(1)[0]
        // Link to this trace
        detection.trace_id = trace.id
        // Link to a random state in this trace
        const traceStates = this.states.get(trace.id) || []
        if (traceStates.length > 0) {
          detection.state_id = traceStates[Math.floor(Math.random() * traceStates.length)].id
        }
        return detection
      })
    })

    // Generate quality assessments, some linked to traces
    this.qualityAssessments = generateDemoQualityAssessments(20).map((qa, i) => {
      // 70% link to a real trace
      if (Math.random() < 0.7 && this.traces.length > 0) {
        qa.trace_id = this.traces[i % this.traces.length].id
      }
      return qa
    })

    // Generate healing records linked to detections
    this.healingRecords = this.detections
      .filter(() => Math.random() > 0.5) // 50% of detections have healing attempts
      .map((detection) => {
        const record = generateDemoHealingRecords(1)[0]
        record.detection_id = detection.id
        return record
      })

    // Generate n8n connections
    this.n8nConnections = generateDemoN8nConnections(5)

    // Generate workflow versions for quality assessments
    this.qualityAssessments.slice(0, 10).forEach((qa) => {
      const versions = generateDemoWorkflowVersions(qa.workflow_id, 10)
      this.workflowVersions.set(qa.workflow_id, versions)
    })

    // Generate new demo data types
    this.n8nWorkflows = generateDemoN8nWorkflows()
    this.chaosSessions = generateDemoChaosSessions()
    this.chaosExperimentTypes = generateDemoChaosExperimentTypes()
    this.replayBundles = generateDemoReplayBundles()
    this.accuracyMetrics = generateDemoAccuracyMetrics()
    this.feedbackStats = generateDemoFeedbackStats()
    this.thresholdRecommendations = generateDemoThresholdRecommendations()
    this.integrationStatus = generateDemoIntegrationStatus()
    this.baselines = generateDemoBaselines()
    this.driftAlerts = generateDemoDriftAlerts()

    this.initialized = true
  }

  /**
   * Get all traces
   */
  getTraces(): Trace[] {
    this.initialize()
    return this.traces
  }

  /**
   * Get a single trace by ID
   */
  getTrace(id: string): Trace | undefined {
    this.initialize()
    return this.traces.find((t) => t.id === id)
  }

  /**
   * Get all detections
   */
  getDetections(): Detection[] {
    this.initialize()
    return this.detections
  }

  /**
   * Get a single detection by ID
   */
  getDetection(id: string): Detection | undefined {
    this.initialize()
    return this.detections.find((d) => d.id === id)
  }

  /**
   * Get detections for a specific trace
   */
  getDetectionsForTrace(traceId: string): Detection[] {
    this.initialize()
    return this.detections.filter((d) => d.trace_id === traceId)
  }

  /**
   * Get states for a specific trace
   */
  getStatesForTrace(traceId: string): State[] {
    this.initialize()
    return this.states.get(traceId) || []
  }

  /**
   * Get quality assessments
   */
  getQualityAssessments(): QualityAssessment[] {
    this.initialize()
    return this.qualityAssessments
  }

  /**
   * Get a single quality assessment by ID
   */
  getQualityAssessment(id: string): QualityAssessment | undefined {
    this.initialize()
    return this.qualityAssessments.find((qa) => qa.id === id)
  }

  /**
   * Get healing records
   */
  getHealingRecords(): HealingRecord[] {
    this.initialize()
    return this.healingRecords
  }

  /**
   * Get healing record for a specific detection
   */
  getHealingForDetection(detectionId: string): HealingRecord | undefined {
    this.initialize()
    return this.healingRecords.find((hr) => hr.detection_id === detectionId)
  }

  /**
   * Get n8n connections
   */
  getN8nConnections(): N8nConnection[] {
    this.initialize()
    return this.n8nConnections
  }

  /**
   * Get workflow versions
   */
  getWorkflowVersions(workflowId: string): WorkflowVersion[] {
    this.initialize()
    return this.workflowVersions.get(workflowId) || generateDemoWorkflowVersions(workflowId, 10)
  }

  /**
   * Get n8n workflows
   */
  getN8nWorkflows(): N8nWorkflow[] {
    this.initialize()
    return this.n8nWorkflows
  }

  /**
   * Get chaos sessions
   */
  getChaosSessions(): ChaosSession[] {
    this.initialize()
    return this.chaosSessions
  }

  /**
   * Get chaos experiment types
   */
  getChaosExperimentTypes(): ChaosExperimentType[] {
    this.initialize()
    return this.chaosExperimentTypes
  }

  /**
   * Get replay bundles
   */
  getReplayBundles(): ReplayBundle[] {
    this.initialize()
    return this.replayBundles
  }

  /**
   * Get accuracy metrics
   */
  getAccuracyMetrics(): AccuracyMetric[] {
    this.initialize()
    return this.accuracyMetrics
  }

  /**
   * Get feedback statistics
   */
  getFeedbackStats(): FeedbackStats {
    this.initialize()
    return this.feedbackStats || generateDemoFeedbackStats()
  }

  /**
   * Get threshold recommendations
   */
  getThresholdRecommendations(): ThresholdRecommendation[] {
    this.initialize()
    return this.thresholdRecommendations
  }

  /**
   * Get integration status
   */
  getIntegrationStatus(): IntegrationStatus[] {
    this.initialize()
    return this.integrationStatus
  }

  /**
   * Get baselines
   */
  getBaselines(): Baseline[] {
    this.initialize()
    return this.baselines
  }

  /**
   * Get drift alerts
   */
  getDriftAlerts(): DriftAlert[] {
    this.initialize()
    return this.driftAlerts
  }

  /**
   * Reset the store (useful for testing or refreshing data)
   */
  reset() {
    this.traces = []
    this.detections = []
    this.states.clear()
    this.qualityAssessments = []
    this.healingRecords = []
    this.n8nConnections = []
    this.workflowVersions.clear()

    this.n8nWorkflows = []
    this.chaosSessions = []
    this.chaosExperimentTypes = []
    this.replayBundles = []
    this.accuracyMetrics = []
    this.feedbackStats = null
    this.thresholdRecommendations = []
    this.integrationStatus = []
    this.baselines = []
    this.driftAlerts = []

    this.initialized = false
  }
}

// Export singleton instance
export const demoDataStore = new DemoDataStore()
