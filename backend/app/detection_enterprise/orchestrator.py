"""Detection orchestrator for Agent Forensics.

Aggregates all detection modules and runs comprehensive failure analysis
on traces. Returns unified diagnosis results with root cause and fix suggestions.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json

import logging

from app.config import get_settings
from app.ingestion.universal_trace import UniversalTrace, UniversalSpan, SpanType, SpanStatus
from app.detection.loop import MultiLevelLoopDetector, StateSnapshot, LoopDetectionResult
from app.detection.overflow import ContextOverflowDetector
from app.detection.corruption import SemanticCorruptionDetector
from app.detection.persona import PersonaConsistencyScorer
from app.detection.hallucination import HallucinationDetector
from app.detection.injection import InjectionDetector
from app.detection.withholding import InformationWithholdingDetector
from app.detection.derailment import TaskDerailmentDetector
from app.detection.completion import CompletionMisjudgmentDetector
from app.detection.communication import CommunicationBreakdownDetector
from app.detection.specification import SpecificationMismatchDetector
from app.detection.decomposition import TaskDecompositionDetector
from app.detection.context import ContextNeglectDetector
from app.detection.coordination import CoordinationAnalyzer
from app.detection.workflow import FlawedWorkflowDetector
from app.detection_enterprise.tool_provision import ToolProvisionDetector
from app.detection_enterprise.grounding import GroundingDetector, GroundingSeverity
from app.detection_enterprise.retrieval_quality import RetrievalQualityDetector, RetrievalSeverity

# Framework-specific detectors
from app.detection.n8n import (
    N8NCycleDetector, N8NSchemaDetector, N8NComplexityDetector,
    N8NErrorDetector, N8NResourceDetector, N8NTimeoutDetector,
)
from app.detection.dify import (
    DifyRagPoisoningDetector, DifyIterationEscapeDetector,
    DifyModelFallbackDetector, DifyVariableLeakDetector,
    DifyClassifierDriftDetector, DifyToolSchemaMismatchDetector,
)
from app.detection.openclaw import (
    OpenClawSessionLoopDetector, OpenClawToolAbuseDetector,
    OpenClawElevatedRiskDetector, OpenClawSpawnChainDetector,
    OpenClawChannelMismatchDetector, OpenClawSandboxEscapeDetector,
)
from app.detection.langgraph import (
    LangGraphRecursionDetector, LangGraphStateCorruptionDetector,
    LangGraphEdgeMisrouteDetector, LangGraphToolFailureDetector,
    LangGraphParallelSyncDetector, LangGraphCheckpointCorruptionDetector,
)
from app.detection.turn_aware._base import TurnAwareDetectionResult, TurnAwareSeverity


logger = logging.getLogger(__name__)

settings = get_settings()


class DetectionCategory(str, Enum):
    """Categories of detection types."""
    LOOP = "loop"
    CONTEXT_OVERFLOW = "context_overflow"
    STATE_CORRUPTION = "state_corruption"
    PERSONA_DRIFT = "persona_drift"
    HALLUCINATION = "hallucination"
    INJECTION = "injection"
    INFORMATION_WITHHOLDING = "information_withholding"
    TASK_DERAILMENT = "task_derailment"
    COMPLETION_MISJUDGMENT = "completion_misjudgment"
    TOOL_PROVISION = "tool_provision"
    GROUNDING_FAILURE = "grounding_failure"  # F15: OfficeQA-inspired
    RETRIEVAL_QUALITY = "retrieval_quality"  # F16: OfficeQA-inspired
    COMMUNICATION_BREAKDOWN = "communication"
    SPECIFICATION_MISMATCH = "specification"
    TASK_DECOMPOSITION = "decomposition"
    CONTEXT_NEGLECT = "context"
    COORDINATION_FAILURE = "coordination"
    FLAWED_WORKFLOW = "workflow"
    # n8n framework-specific
    N8N_CYCLE = "n8n_cycle"
    N8N_SCHEMA = "n8n_schema"
    N8N_COMPLEXITY = "n8n_complexity"
    N8N_ERROR = "n8n_error"
    N8N_RESOURCE = "n8n_resource"
    N8N_TIMEOUT = "n8n_timeout"
    # Dify framework-specific
    DIFY_RAG_POISONING = "dify_rag_poisoning"
    DIFY_ITERATION_ESCAPE = "dify_iteration_escape"
    DIFY_MODEL_FALLBACK = "dify_model_fallback"
    DIFY_VARIABLE_LEAK = "dify_variable_leak"
    DIFY_CLASSIFIER_DRIFT = "dify_classifier_drift"
    DIFY_TOOL_SCHEMA_MISMATCH = "dify_tool_schema_mismatch"
    # OpenClaw framework-specific
    OPENCLAW_SESSION_LOOP = "openclaw_session_loop"
    OPENCLAW_TOOL_ABUSE = "openclaw_tool_abuse"
    OPENCLAW_ELEVATED_RISK = "openclaw_elevated_risk"
    OPENCLAW_SPAWN_CHAIN = "openclaw_spawn_chain"
    OPENCLAW_CHANNEL_MISMATCH = "openclaw_channel_mismatch"
    OPENCLAW_SANDBOX_ESCAPE = "openclaw_sandbox_escape"
    # LangGraph framework-specific
    LANGGRAPH_RECURSION = "langgraph_recursion"
    LANGGRAPH_STATE_CORRUPTION = "langgraph_state_corruption"
    LANGGRAPH_EDGE_MISROUTE = "langgraph_edge_misroute"
    LANGGRAPH_TOOL_FAILURE = "langgraph_tool_failure"
    LANGGRAPH_PARALLEL_SYNC = "langgraph_parallel_sync"
    LANGGRAPH_CHECKPOINT_CORRUPTION = "langgraph_checkpoint_corruption"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Severity levels for detected issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ConfidenceTier(str, Enum):
    """Customer-facing confidence tiers for detection results."""
    HIGH = "high"          # >= 0.80: Strong signal, high certainty
    LIKELY = "likely"      # 0.60-0.80: Probable issue
    POSSIBLE = "possible"  # 0.40-0.60: Worth investigating
    LOW = "low"            # < 0.40: Weak signal


@dataclass
class DetectionResult:
    """Result from a single detector."""
    category: DetectionCategory
    detected: bool
    confidence: float
    severity: Severity
    title: str
    description: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    affected_spans: List[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    raw_result: Optional[Any] = None

    @property
    def confidence_tier(self) -> ConfidenceTier:
        """Map raw confidence to customer-facing tier."""
        if self.confidence >= 0.80:
            return ConfidenceTier.HIGH
        elif self.confidence >= 0.60:
            return ConfidenceTier.LIKELY
        elif self.confidence >= 0.40:
            return ConfidenceTier.POSSIBLE
        else:
            return ConfidenceTier.LOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "detected": self.detected,
            "confidence": self.confidence,
            "confidence_tier": self.confidence_tier.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "affected_spans": self.affected_spans,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class DiagnosisResult:
    """Complete diagnosis result from the orchestrator."""
    trace_id: str
    analyzed_at: datetime = field(default_factory=datetime.utcnow)

    # Overall status
    has_failures: bool = False
    failure_count: int = 0

    # Primary root cause (highest confidence/severity issue)
    primary_failure: Optional[DetectionResult] = None

    # All detected issues
    all_detections: List[DetectionResult] = field(default_factory=list)

    # Summary statistics
    total_spans: int = 0
    error_spans: int = 0
    total_tokens: int = 0
    duration_ms: int = 0

    # Root cause analysis (LLM-generated if available)
    root_cause_explanation: Optional[str] = None

    # Self-healing capability
    self_healing_available: bool = False
    auto_fix_preview: Optional[Dict[str, Any]] = None

    # Metadata
    detection_time_ms: int = 0
    detectors_run: List[str] = field(default_factory=list)
    detectors_disabled: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "analyzed_at": self.analyzed_at.isoformat(),
            "has_failures": self.has_failures,
            "failure_count": self.failure_count,
            "primary_failure": self.primary_failure.to_dict() if self.primary_failure else None,
            "all_detections": [d.to_dict() for d in self.all_detections],
            "total_spans": self.total_spans,
            "error_spans": self.error_spans,
            "total_tokens": self.total_tokens,
            "duration_ms": self.duration_ms,
            "root_cause_explanation": self.root_cause_explanation,
            "self_healing_available": self.self_healing_available,
            "auto_fix_preview": self.auto_fix_preview,
            "detection_time_ms": self.detection_time_ms,
            "detectors_run": self.detectors_run,
            "detectors_disabled": self.detectors_disabled,
        }


class DetectionOrchestrator:
    """Orchestrates all detection modules for comprehensive trace analysis.

    This orchestrator runs multiple detection algorithms in parallel and
    aggregates results into a unified diagnosis.
    """

    # Detectors disabled due to calibration F1 < 0.30.  Mapping from
    # DetectionCategory to human-readable reason.  These detectors are
    # skipped at runtime and their status is reported honestly in the
    # DiagnosisResult.
    #
    # Sprint 5: Cleared all 4 previously-disabled detectors. Calibration
    # data now shows: withholding F1=0.75, derailment F1=0.833,
    # grounding F1=0.667, retrieval_quality F1=0.833.  The original
    # disable reasons were stale from before Sprint 3/4 improvements.
    DISABLED_DETECTORS: Dict[str, str] = {}

    # Framework-specific detector registry: source_format → list of
    # (name, detector_class, category) tuples.
    FRAMEWORK_DETECTORS: Dict[str, List[Tuple[str, type, "DetectionCategory"]]] = {
        "n8n": [
            ("n8n_cycle", N8NCycleDetector, DetectionCategory.N8N_CYCLE),
            ("n8n_schema", N8NSchemaDetector, DetectionCategory.N8N_SCHEMA),
            ("n8n_complexity", N8NComplexityDetector, DetectionCategory.N8N_COMPLEXITY),
            ("n8n_error", N8NErrorDetector, DetectionCategory.N8N_ERROR),
            ("n8n_resource", N8NResourceDetector, DetectionCategory.N8N_RESOURCE),
            ("n8n_timeout", N8NTimeoutDetector, DetectionCategory.N8N_TIMEOUT),
        ],
        "dify": [
            ("dify_rag_poisoning", DifyRagPoisoningDetector, DetectionCategory.DIFY_RAG_POISONING),
            ("dify_iteration_escape", DifyIterationEscapeDetector, DetectionCategory.DIFY_ITERATION_ESCAPE),
            ("dify_model_fallback", DifyModelFallbackDetector, DetectionCategory.DIFY_MODEL_FALLBACK),
            ("dify_variable_leak", DifyVariableLeakDetector, DetectionCategory.DIFY_VARIABLE_LEAK),
            ("dify_classifier_drift", DifyClassifierDriftDetector, DetectionCategory.DIFY_CLASSIFIER_DRIFT),
            ("dify_tool_schema_mismatch", DifyToolSchemaMismatchDetector, DetectionCategory.DIFY_TOOL_SCHEMA_MISMATCH),
        ],
        "openclaw": [
            ("openclaw_session_loop", OpenClawSessionLoopDetector, DetectionCategory.OPENCLAW_SESSION_LOOP),
            ("openclaw_tool_abuse", OpenClawToolAbuseDetector, DetectionCategory.OPENCLAW_TOOL_ABUSE),
            ("openclaw_elevated_risk", OpenClawElevatedRiskDetector, DetectionCategory.OPENCLAW_ELEVATED_RISK),
            ("openclaw_spawn_chain", OpenClawSpawnChainDetector, DetectionCategory.OPENCLAW_SPAWN_CHAIN),
            ("openclaw_channel_mismatch", OpenClawChannelMismatchDetector, DetectionCategory.OPENCLAW_CHANNEL_MISMATCH),
            ("openclaw_sandbox_escape", OpenClawSandboxEscapeDetector, DetectionCategory.OPENCLAW_SANDBOX_ESCAPE),
        ],
        "langgraph": [
            ("langgraph_recursion", LangGraphRecursionDetector, DetectionCategory.LANGGRAPH_RECURSION),
            ("langgraph_state_corruption", LangGraphStateCorruptionDetector, DetectionCategory.LANGGRAPH_STATE_CORRUPTION),
            ("langgraph_edge_misroute", LangGraphEdgeMisrouteDetector, DetectionCategory.LANGGRAPH_EDGE_MISROUTE),
            ("langgraph_tool_failure", LangGraphToolFailureDetector, DetectionCategory.LANGGRAPH_TOOL_FAILURE),
            ("langgraph_parallel_sync", LangGraphParallelSyncDetector, DetectionCategory.LANGGRAPH_PARALLEL_SYNC),
            ("langgraph_checkpoint_corruption", LangGraphCheckpointCorruptionDetector, DetectionCategory.LANGGRAPH_CHECKPOINT_CORRUPTION),
        ],
    }

    def __init__(
        self,
        enable_llm_explanation: bool = True,
        max_parallel_detectors: int = 5,
        timeout_seconds: float = 30.0,
    ):
        self.enable_llm_explanation = enable_llm_explanation
        self.max_parallel_detectors = max_parallel_detectors
        self.timeout_seconds = timeout_seconds

        # Initialize detectors (lazy loaded when needed)
        self._loop_detector: Optional[MultiLevelLoopDetector] = None
        self._overflow_detector: Optional[ContextOverflowDetector] = None
        self._corruption_detector: Optional[SemanticCorruptionDetector] = None
        self._persona_detector: Optional[PersonaConsistencyScorer] = None
        self._hallucination_detector: Optional[HallucinationDetector] = None
        self._injection_detector: Optional[InjectionDetector] = None
        self._withholding_detector: Optional[InformationWithholdingDetector] = None
        self._derailment_detector: Optional[TaskDerailmentDetector] = None
        self._completion_detector: Optional[CompletionMisjudgmentDetector] = None
        self._tool_provision_detector: Optional[ToolProvisionDetector] = None
        self._grounding_detector: Optional[GroundingDetector] = None
        self._retrieval_quality_detector: Optional[RetrievalQualityDetector] = None
        self._communication_detector: Optional[CommunicationBreakdownDetector] = None
        self._specification_detector: Optional[SpecificationMismatchDetector] = None
        self._decomposition_detector: Optional[TaskDecompositionDetector] = None
        self._context_detector: Optional[ContextNeglectDetector] = None
        self._coordination_detector: Optional[CoordinationAnalyzer] = None
        self._workflow_detector: Optional[FlawedWorkflowDetector] = None

    @property
    def loop_detector(self) -> MultiLevelLoopDetector:
        if self._loop_detector is None:
            self._loop_detector = MultiLevelLoopDetector()
        return self._loop_detector

    @property
    def overflow_detector(self) -> ContextOverflowDetector:
        if self._overflow_detector is None:
            self._overflow_detector = ContextOverflowDetector()
        return self._overflow_detector

    @property
    def tool_provision_detector(self) -> ToolProvisionDetector:
        if self._tool_provision_detector is None:
            self._tool_provision_detector = ToolProvisionDetector()
        return self._tool_provision_detector

    @property
    def hallucination_detector(self) -> HallucinationDetector:
        if self._hallucination_detector is None:
            self._hallucination_detector = HallucinationDetector()
        return self._hallucination_detector

    @property
    def persona_detector(self) -> PersonaConsistencyScorer:
        if self._persona_detector is None:
            self._persona_detector = PersonaConsistencyScorer()
        return self._persona_detector

    @property
    def corruption_detector(self) -> SemanticCorruptionDetector:
        if self._corruption_detector is None:
            self._corruption_detector = SemanticCorruptionDetector()
        return self._corruption_detector

    @property
    def grounding_detector(self) -> GroundingDetector:
        if self._grounding_detector is None:
            self._grounding_detector = GroundingDetector()
        return self._grounding_detector

    @property
    def retrieval_quality_detector(self) -> RetrievalQualityDetector:
        if self._retrieval_quality_detector is None:
            self._retrieval_quality_detector = RetrievalQualityDetector()
        return self._retrieval_quality_detector

    @property
    def withholding_detector(self) -> InformationWithholdingDetector:
        if self._withholding_detector is None:
            self._withholding_detector = InformationWithholdingDetector()
        return self._withholding_detector

    @property
    def derailment_detector(self) -> TaskDerailmentDetector:
        if self._derailment_detector is None:
            self._derailment_detector = TaskDerailmentDetector()
        return self._derailment_detector

    @property
    def communication_detector(self) -> CommunicationBreakdownDetector:
        if self._communication_detector is None:
            self._communication_detector = CommunicationBreakdownDetector()
        return self._communication_detector

    @property
    def specification_detector(self) -> SpecificationMismatchDetector:
        if self._specification_detector is None:
            self._specification_detector = SpecificationMismatchDetector()
        return self._specification_detector

    @property
    def decomposition_detector(self) -> TaskDecompositionDetector:
        if self._decomposition_detector is None:
            self._decomposition_detector = TaskDecompositionDetector()
        return self._decomposition_detector

    @property
    def context_detector(self) -> ContextNeglectDetector:
        if self._context_detector is None:
            self._context_detector = ContextNeglectDetector()
        return self._context_detector

    @property
    def coordination_analyzer(self) -> CoordinationAnalyzer:
        if self._coordination_detector is None:
            self._coordination_detector = CoordinationAnalyzer()
        return self._coordination_detector

    @property
    def workflow_detector(self) -> FlawedWorkflowDetector:
        if self._workflow_detector is None:
            self._workflow_detector = FlawedWorkflowDetector()
        return self._workflow_detector

    @staticmethod
    def _convert_turn_aware_result(
        ta_result: TurnAwareDetectionResult,
        category: DetectionCategory,
    ) -> DetectionResult:
        """Convert a TurnAwareDetectionResult to a DetectionResult."""
        severity_map = {
            TurnAwareSeverity.SEVERE: Severity.CRITICAL,
            TurnAwareSeverity.MODERATE: Severity.MEDIUM,
            TurnAwareSeverity.MINOR: Severity.LOW,
            TurnAwareSeverity.NONE: Severity.INFO,
        }
        return DetectionResult(
            category=category,
            detected=ta_result.detected,
            confidence=ta_result.confidence,
            severity=severity_map.get(ta_result.severity, Severity.MEDIUM),
            title=ta_result.failure_mode or category.value,
            description=ta_result.explanation,
            evidence=[ta_result.evidence] if ta_result.evidence else [],
            affected_spans=[str(t) for t in ta_result.affected_turns],
            suggested_fix=ta_result.suggested_fix,
        )

    def _build_framework_metadata(self, trace: UniversalTrace) -> Dict[str, Any]:
        """Build conversation_metadata dict from trace data for framework detectors."""
        framework = trace.source_format.lower() if trace.source_format else ""
        metadata: Dict[str, Any] = {}

        if framework == "n8n":
            # n8n detectors read workflow_duration_ms and workflow_json
            wf = trace.metadata.get("workflow_json", {})
            if not wf and trace.spans:
                # Build minimal workflow representation from spans
                nodes = []
                for span in trace.spans:
                    span_meta = span.metadata or {}
                    nodes.append({
                        "id": span.id,
                        "type": span_meta.get("n8n.node.type", span.name),
                        "name": span.name,
                        "parameters": span_meta.get("n8n.node.parameters", {}),
                    })
                wf = {"nodes": nodes}
            metadata["workflow_json"] = wf
            metadata["workflow_duration_ms"] = trace.total_duration_ms

        elif framework == "dify":
            # Dify detectors read workflow_run
            wf_run = trace.metadata.get("workflow_run", {})
            if not wf_run and trace.spans:
                nodes = []
                for span in trace.spans:
                    span_meta = span.metadata or {}
                    nodes.append({
                        "node_id": span.id,
                        "node_type": span_meta.get("dify.node.type", "unknown"),
                        "title": span.name,
                        "status": "succeeded" if not span.has_error else "failed",
                        "inputs": span_meta.get("dify.node.inputs", {}),
                        "outputs": span_meta.get("dify.node.outputs", {}),
                    })
                wf_run = {
                    "workflow_run_id": trace.trace_id,
                    "nodes": nodes,
                    "status": "succeeded",
                }
            metadata["workflow_run"] = wf_run

        elif framework == "openclaw":
            # OpenClaw detectors read session
            session = trace.metadata.get("session", {})
            if not session and trace.spans:
                events = []
                for span in trace.spans:
                    span_meta = span.metadata or {}
                    events.append({
                        "type": span_meta.get("openclaw.event.type", span.name),
                        "agent_name": span_meta.get("openclaw.agent_name", ""),
                        "timestamp": span.start_time.isoformat() if span.start_time else "",
                        "data": span_meta.get("openclaw.event.data", {}),
                    })
                session = {
                    "session_id": trace.trace_id,
                    "events": events,
                }
            metadata["session"] = session

        elif framework == "langgraph":
            # LangGraph detectors read graph_execution
            graph_exec = trace.metadata.get("graph_execution", {})
            if not graph_exec and trace.spans:
                steps = []
                for span in trace.spans:
                    span_meta = span.metadata or {}
                    steps.append({
                        "node": span.name,
                        "span_id": span.id,
                        "status": "ok" if not span.has_error else "error",
                        "metadata": span_meta,
                    })
                graph_exec = {
                    "trace_id": trace.trace_id,
                    "steps": steps,
                }
            metadata["graph_execution"] = graph_exec

        return metadata

    def _run_framework_detectors(self, trace: UniversalTrace) -> List[DetectionResult]:
        """Run framework-specific detectors based on trace.source_format."""
        framework = (trace.source_format or "").lower()
        detector_specs = self.FRAMEWORK_DETECTORS.get(framework, [])
        if not detector_specs:
            return []

        metadata = self._build_framework_metadata(trace)
        results: List[DetectionResult] = []

        for name, detector_cls, category in detector_specs:
            try:
                detector = detector_cls()
                ta_result = detector.detect(turns=[], conversation_metadata=metadata)
                if ta_result.detected:
                    results.append(self._convert_turn_aware_result(ta_result, category))
            except Exception as e:
                logger.warning("Framework detector %s failed: %s", name, e)

        return results

    def analyze_trace(self, trace: UniversalTrace) -> DiagnosisResult:
        """Run comprehensive detection on a trace.

        Args:
            trace: UniversalTrace to analyze

        Returns:
            DiagnosisResult with all findings
        """
        start_time = datetime.utcnow()

        # Initialize result
        result = DiagnosisResult(
            trace_id=trace.trace_id,
            total_spans=len(trace.spans),
            error_spans=len([s for s in trace.spans if s.has_error]),
            total_tokens=trace.total_tokens,
            duration_ms=trace.total_duration_ms,
        )

        all_detections: List[DetectionResult] = []

        # Convert spans to state snapshots for detectors that need them
        snapshots = trace.to_state_snapshots()

        # Run loop detection
        loop_result = self._detect_loops(snapshots)
        if loop_result:
            all_detections.append(loop_result)
            result.detectors_run.append("loop")

        # Run context overflow detection
        overflow_result = self._detect_overflow(trace)
        if overflow_result:
            all_detections.append(overflow_result)
            result.detectors_run.append("overflow")

        # Run tool-related detections for single-agent traces
        tool_results = self._detect_tool_issues(trace)
        all_detections.extend(tool_results)
        if tool_results:
            result.detectors_run.append("tool_issues")

        # Run F4: Inadequate Tool Provision detection
        tool_provision_result = self._detect_tool_provision(trace)
        if tool_provision_result:
            all_detections.append(tool_provision_result)
            result.detectors_run.append("tool_provision")

        # Run hallucination detection on agent outputs
        hallucination_result = self._detect_hallucination(trace)
        if hallucination_result:
            all_detections.append(hallucination_result)
            result.detectors_run.append("hallucination")

        # Run persona drift detection
        persona_result = self._detect_persona_drift(trace)
        if persona_result:
            all_detections.append(persona_result)
            result.detectors_run.append("persona_drift")

        # Run state corruption detection
        corruption_results = self._detect_corruption(trace, snapshots)
        all_detections.extend(corruption_results)
        if corruption_results:
            result.detectors_run.append("corruption")

        # Run error pattern detection
        error_results = self._detect_error_patterns(trace)
        all_detections.extend(error_results)
        if error_results:
            result.detectors_run.append("error_patterns")

        # Run information withholding detection (re-enabled Sprint 5)
        if DetectionCategory.INFORMATION_WITHHOLDING not in self.DISABLED_DETECTORS:
            withholding_result = self._detect_withholding(trace)
            if withholding_result:
                all_detections.append(withholding_result)
                result.detectors_run.append("withholding")

        # Run task derailment detection (re-enabled Sprint 5)
        if DetectionCategory.TASK_DERAILMENT not in self.DISABLED_DETECTORS:
            derailment_result = self._detect_derailment(trace)
            if derailment_result:
                all_detections.append(derailment_result)
                result.detectors_run.append("derailment")

        # Run communication breakdown detection
        communication_result = self._detect_communication(trace)
        if communication_result:
            all_detections.append(communication_result)
            result.detectors_run.append("communication")

        # Run specification mismatch detection
        specification_result = self._detect_specification(trace)
        if specification_result:
            all_detections.append(specification_result)
            result.detectors_run.append("specification")

        # Run task decomposition detection
        decomposition_result = self._detect_decomposition(trace)
        if decomposition_result:
            all_detections.append(decomposition_result)
            result.detectors_run.append("decomposition")

        # Run context neglect detection
        context_result = self._detect_context_neglect(trace)
        if context_result:
            all_detections.append(context_result)
            result.detectors_run.append("context")

        # Run coordination failure detection
        coordination_result = self._detect_coordination(trace)
        if coordination_result:
            all_detections.append(coordination_result)
            result.detectors_run.append("coordination")

        # Run flawed workflow detection
        workflow_result = self._detect_workflow(trace)
        if workflow_result:
            all_detections.append(workflow_result)
            result.detectors_run.append("workflow")

        # Run grounding failure detection (F15: OfficeQA-inspired)
        if DetectionCategory.GROUNDING_FAILURE not in self.DISABLED_DETECTORS:
            grounding_result = self._detect_grounding_failure(trace)
            if grounding_result:
                all_detections.append(grounding_result)
                result.detectors_run.append("grounding")

        # Run retrieval quality detection (F16: OfficeQA-inspired)
        if DetectionCategory.RETRIEVAL_QUALITY not in self.DISABLED_DETECTORS:
            retrieval_result = self._detect_retrieval_quality(trace)
            if retrieval_result:
                all_detections.append(retrieval_result)
                result.detectors_run.append("retrieval_quality")

        # Run framework-specific detectors based on source_format
        framework_results = self._run_framework_detectors(trace)
        all_detections.extend(framework_results)
        if framework_results:
            result.detectors_run.append(f"framework:{trace.source_format}")

        # Report disabled detectors for transparency
        result.detectors_disabled = dict(self.DISABLED_DETECTORS)

        # Filter to only detected issues
        detected_issues = [d for d in all_detections if d.detected]

        # Deduplicate correlated detections
        detected_issues = self._deduplicate_detections(detected_issues)

        # Sort by severity and confidence
        severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
        detected_issues.sort(key=lambda d: (severity_order[d.severity], -d.confidence))

        result.all_detections = detected_issues
        result.has_failures = len(detected_issues) > 0
        result.failure_count = len(detected_issues)

        if detected_issues:
            result.primary_failure = detected_issues[0]

            # Generate root cause explanation
            result.root_cause_explanation = self._generate_explanation(result.primary_failure, trace)

            # Check if self-healing is available
            if result.primary_failure.suggested_fix:
                result.self_healing_available = True
                result.auto_fix_preview = {
                    "description": f"Apply fix for {result.primary_failure.category.value}",
                    "confidence": result.primary_failure.confidence,
                    "action": result.primary_failure.suggested_fix,
                }

        # Calculate detection time
        end_time = datetime.utcnow()
        result.detection_time_ms = int((end_time - start_time).total_seconds() * 1000)

        return result

    # Subsumption rules: when both detectors in a pair fire, keep the root
    # cause and suppress the symptom.  Format: (root_cause, symptom).
    SUBSUMPTION_RULES: List[Tuple[DetectionCategory, DetectionCategory]] = [
        # Grounding failure subsumes hallucination (grounding is the root cause)
        (DetectionCategory.GROUNDING_FAILURE, DetectionCategory.HALLUCINATION),
        # Loop subsumes context overflow (loops cause context exhaustion)
        (DetectionCategory.LOOP, DetectionCategory.CONTEXT_OVERFLOW),
        # Derailment subsumes completion misjudgment (off-track → bad completion)
        (DetectionCategory.TASK_DERAILMENT, DetectionCategory.COMPLETION_MISJUDGMENT),
        # Communication breakdown subsumes coordination failure (symptom of it)
        (DetectionCategory.COMMUNICATION_BREAKDOWN, DetectionCategory.COORDINATION_FAILURE),
    ]

    def _deduplicate_detections(self, detections: List[DetectionResult]) -> List[DetectionResult]:
        """Remove correlated detections where one subsumes another.

        Two deduplication strategies:
        1. Subsumption rules: known root-cause/symptom pairs
        2. Span overlap: if two detections share >50% affected spans, keep higher-confidence
        """
        if len(detections) <= 1:
            return detections

        categories_present = {d.category for d in detections}
        suppressed_categories = set()

        # Apply subsumption rules
        for root_cause, symptom in self.SUBSUMPTION_RULES:
            if root_cause in categories_present and symptom in categories_present:
                suppressed_categories.add(symptom)

        # Filter by subsumption
        remaining = [d for d in detections if d.category not in suppressed_categories]

        # Apply span overlap deduplication
        if len(remaining) > 1:
            final = []
            skip_indices = set()
            for i, det_a in enumerate(remaining):
                if i in skip_indices:
                    continue
                for j in range(i + 1, len(remaining)):
                    if j in skip_indices:
                        continue
                    det_b = remaining[j]
                    # Check span overlap
                    if det_a.affected_spans and det_b.affected_spans:
                        set_a = set(det_a.affected_spans)
                        set_b = set(det_b.affected_spans)
                        overlap = len(set_a & set_b)
                        min_size = min(len(set_a), len(set_b))
                        if min_size > 0 and overlap / min_size > 0.5:
                            # Keep the one with higher confidence
                            if det_b.confidence > det_a.confidence:
                                skip_indices.add(i)
                                break
                            else:
                                skip_indices.add(j)
                if i not in skip_indices:
                    final.append(remaining[i])
            remaining = final

        return remaining

    async def analyze_trace_async(self, trace: UniversalTrace) -> DiagnosisResult:
        """Run comprehensive detection on a trace with parallel execution.

        Uses asyncio.gather with a semaphore to run detectors in parallel,
        bounded by max_parallel_detectors.
        """
        import asyncio

        start_time = datetime.utcnow()
        result = DiagnosisResult(
            trace_id=trace.trace_id,
            total_spans=len(trace.spans),
            error_spans=len([s for s in trace.spans if s.has_error]),
            total_tokens=trace.total_tokens,
            duration_ms=trace.total_duration_ms,
        )

        snapshots = trace.to_state_snapshots()
        sem = asyncio.Semaphore(self.max_parallel_detectors)
        loop = asyncio.get_event_loop()

        async def _run(name: str, fn, *args):
            async with sem:
                try:
                    return name, await loop.run_in_executor(None, fn, *args)
                except Exception as e:
                    logger.warning("Detector %s failed: %s", name, e)
                    return name, None

        # Build detector tasks — each returns (name, result_or_None)
        tasks = [
            _run("loop", self._detect_loops, snapshots),
            _run("overflow", self._detect_overflow, trace),
            _run("tool_issues", self._detect_tool_issues, trace),
            _run("tool_provision", self._detect_tool_provision, trace),
            _run("hallucination", self._detect_hallucination, trace),
            _run("persona_drift", self._detect_persona_drift, trace),
            _run("corruption", self._detect_corruption, trace, snapshots),
            _run("error_patterns", self._detect_error_patterns, trace),
            _run("communication", self._detect_communication, trace),
            _run("specification", self._detect_specification, trace),
            _run("decomposition", self._detect_decomposition, trace),
            _run("context", self._detect_context_neglect, trace),
            _run("coordination", self._detect_coordination, trace),
            _run("workflow", self._detect_workflow, trace),
        ]

        # Add gated detectors only if not disabled
        if DetectionCategory.INFORMATION_WITHHOLDING not in self.DISABLED_DETECTORS:
            tasks.append(_run("withholding", self._detect_withholding, trace))
        if DetectionCategory.TASK_DERAILMENT not in self.DISABLED_DETECTORS:
            tasks.append(_run("derailment", self._detect_derailment, trace))
        if DetectionCategory.GROUNDING_FAILURE not in self.DISABLED_DETECTORS:
            tasks.append(_run("grounding", self._detect_grounding_failure, trace))
        if DetectionCategory.RETRIEVAL_QUALITY not in self.DISABLED_DETECTORS:
            tasks.append(_run("retrieval_quality", self._detect_retrieval_quality, trace))

        # Add framework-specific detectors
        if (trace.source_format or "").lower() in self.FRAMEWORK_DETECTORS:
            tasks.append(_run(f"framework:{trace.source_format}", self._run_framework_detectors, trace))

        completed = await asyncio.gather(*tasks)

        # Aggregate results
        all_detections: List[DetectionResult] = []
        for name, det_result in completed:
            if det_result is None:
                continue
            if isinstance(det_result, list):
                all_detections.extend(det_result)
                if det_result:
                    result.detectors_run.append(name)
            elif isinstance(det_result, DetectionResult):
                all_detections.append(det_result)
                result.detectors_run.append(name)

        result.detectors_disabled = dict(self.DISABLED_DETECTORS)

        # Filter to only detected issues
        detected_issues = [d for d in all_detections if d.detected]
        detected_issues = self._deduplicate_detections(detected_issues)
        severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
        detected_issues.sort(key=lambda d: (severity_order[d.severity], -d.confidence))

        result.all_detections = detected_issues
        result.has_failures = len(detected_issues) > 0
        result.failure_count = len(detected_issues)

        if detected_issues:
            result.primary_failure = detected_issues[0]
            result.root_cause_explanation = self._generate_explanation(result.primary_failure, trace)
            if result.primary_failure.suggested_fix:
                result.self_healing_available = True
                result.auto_fix_preview = {
                    "description": f"Apply fix for {result.primary_failure.category.value}",
                    "confidence": result.primary_failure.confidence,
                    "action": result.primary_failure.suggested_fix,
                }

        end_time = datetime.utcnow()
        result.detection_time_ms = int((end_time - start_time).total_seconds() * 1000)

        return result

    def _detect_loops(self, snapshots: List[StateSnapshot]) -> Optional[DetectionResult]:
        """Detect loop patterns in the trace."""
        if len(snapshots) < 3:
            return None

        try:
            loop_result: LoopDetectionResult = self.loop_detector.detect(snapshots)

            if loop_result.detected:
                return DetectionResult(
                    category=DetectionCategory.LOOP,
                    detected=True,
                    confidence=loop_result.confidence,
                    severity=Severity.HIGH if loop_result.confidence > 0.8 else Severity.MEDIUM,
                    title="Loop Detected",
                    description=f"Detected repetitive pattern using {loop_result.method} analysis. "
                               f"Loop starts at step {loop_result.loop_start_index} with length {loop_result.loop_length}.",
                    evidence=[loop_result.evidence] if loop_result.evidence else [],
                    suggested_fix="Add loop detection guard or break condition to prevent infinite loops.",
                    raw_result=loop_result,
                )
        except Exception as e:
            logger.warning("Loop detector failed: %s", e)

        return None

    def _detect_overflow(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect context overflow issues."""
        total_tokens = trace.total_tokens

        if total_tokens == 0:
            return None

        # Check against common model limits
        model_limits = {
            "gpt-4": 8192,
            "gpt-4-32k": 32768,
            "gpt-4-turbo": 128000,
            "gpt-4o": 128000,
            "gpt-3.5-turbo": 4096,
            "gpt-3.5-turbo-16k": 16384,
            "claude-3": 200000,
            "claude-2": 100000,
        }

        # Try to infer model from trace
        model = None
        for span in trace.spans:
            if span.model:
                model = span.model.lower()
                break

        if not model:
            model = "gpt-4"  # Default assumption

        # Find matching limit
        limit = 8192  # Default
        for model_name, model_limit in model_limits.items():
            if model_name in model:
                limit = model_limit
                break

        usage_pct = (total_tokens / limit) * 100

        if usage_pct > 90:
            return DetectionResult(
                category=DetectionCategory.CONTEXT_OVERFLOW,
                detected=True,
                confidence=min(usage_pct / 100, 1.0),
                severity=Severity.CRITICAL if usage_pct > 100 else Severity.HIGH,
                title="Context Window Overflow Risk",
                description=f"Token usage ({total_tokens:,}) is at {usage_pct:.1f}% of estimated limit ({limit:,}). "
                           "Information may be truncated or lost.",
                evidence=[{
                    "total_tokens": total_tokens,
                    "estimated_limit": limit,
                    "usage_percent": usage_pct,
                    "model": model,
                }],
                suggested_fix="Implement context summarization or use a model with larger context window.",
            )
        elif usage_pct > 70:
            return DetectionResult(
                category=DetectionCategory.CONTEXT_OVERFLOW,
                detected=True,
                confidence=usage_pct / 100,
                severity=Severity.MEDIUM,
                title="Context Window Warning",
                description=f"Token usage ({total_tokens:,}) is at {usage_pct:.1f}% of estimated limit ({limit:,}). "
                           "Consider monitoring for longer conversations.",
                evidence=[{
                    "total_tokens": total_tokens,
                    "estimated_limit": limit,
                    "usage_percent": usage_pct,
                }],
                suggested_fix="Monitor token usage and consider implementing summarization for long sessions.",
            )

        return None

    def _detect_tool_issues(self, trace: UniversalTrace) -> List[DetectionResult]:
        """Detect tool-related issues (for single-agent scenarios)."""
        results = []

        tool_calls = trace.get_tool_calls()
        if not tool_calls:
            return results

        # Check for repeated tool calls (potential tool loop)
        tool_sequence = [s.tool_name for s in tool_calls if s.tool_name]
        if len(tool_sequence) >= 3:
            # Check for immediate repeats
            repeats = []
            for i in range(1, len(tool_sequence)):
                if tool_sequence[i] == tool_sequence[i-1]:
                    repeats.append((i-1, tool_sequence[i]))

            if len(repeats) >= 2:
                results.append(DetectionResult(
                    category=DetectionCategory.LOOP,
                    detected=True,
                    confidence=0.7 + (len(repeats) * 0.05),
                    severity=Severity.MEDIUM,
                    title="Repeated Tool Calls",
                    description=f"Tool '{repeats[0][1]}' called {len(repeats) + 1} times consecutively. "
                               "This may indicate a retry loop or stuck agent.",
                    evidence=[{"repeated_tool": repeats[0][1], "count": len(repeats) + 1}],
                    affected_spans=[s.id for s in tool_calls if s.tool_name == repeats[0][1]],
                    suggested_fix="Add tool result validation and retry limits.",
                ))

        # Check for tool errors
        failed_tools = [s for s in tool_calls if s.has_error]
        if failed_tools:
            for tool_span in failed_tools:
                results.append(DetectionResult(
                    category=DetectionCategory.TOOL_PROVISION,
                    detected=True,
                    confidence=0.95,
                    severity=Severity.HIGH,
                    title=f"Tool Error: {tool_span.tool_name}",
                    description=f"Tool '{tool_span.tool_name}' failed with error: {tool_span.error or 'Unknown error'}",
                    evidence=[{
                        "tool_name": tool_span.tool_name,
                        "error": tool_span.error,
                        "args": tool_span.tool_args,
                    }],
                    affected_spans=[tool_span.id],
                    suggested_fix="Add error handling for tool failures and consider retry logic.",
                ))

        return results

    def _detect_tool_provision(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect F4: Inadequate Tool Provision using the real ToolProvisionDetector.

        Extracts task description, agent output, available tools and tool call
        data from the trace, then delegates to ToolProvisionDetector.detect().
        """
        from app.detection_enterprise.tool_provision import ProvisionSeverity

        # Extract task, agent output, tools from trace spans
        task = ""
        agent_output_parts: List[str] = []
        available_tools: List[str] = []
        tool_calls: List[Dict[str, Any]] = []

        for span in trace.spans:
            # Extract task from span metadata
            if not task:
                task = (span.metadata or {}).get("gen_ai.task", "")
                if not task and span.prompt:
                    task = span.prompt[:500]

            # Collect agent output
            if span.response:
                agent_output_parts.append(span.response)

            # Collect available tools
            if span.tool_name:
                if not span.has_error:
                    available_tools.append(span.tool_name)
                tool_calls.append({
                    "name": span.tool_name,
                    "status": "error" if span.has_error else "success",
                    "error": span.error or "",
                    "result": {"args": span.tool_args} if span.tool_args else {},
                })

        agent_output = "\n".join(agent_output_parts)

        if not task and not agent_output:
            return None

        try:
            result = self.tool_provision_detector.detect(
                task=task,
                agent_output=agent_output,
                available_tools=available_tools if available_tools else None,
                tool_calls=tool_calls if tool_calls else None,
            )

            if result.detected:
                severity_map = {
                    ProvisionSeverity.CRITICAL: Severity.CRITICAL,
                    ProvisionSeverity.SEVERE: Severity.HIGH,
                    ProvisionSeverity.MODERATE: Severity.MEDIUM,
                    ProvisionSeverity.MINOR: Severity.LOW,
                    ProvisionSeverity.NONE: Severity.INFO,
                }

                return DetectionResult(
                    category=DetectionCategory.TOOL_PROVISION,
                    detected=True,
                    confidence=result.confidence,
                    severity=severity_map.get(result.severity, Severity.MEDIUM),
                    title="Inadequate Tool Provision",
                    description=result.explanation,
                    evidence=[{
                        "issues": [{"type": i.issue_type.value, "tool": i.tool_name, "desc": i.description} for i in result.issues],
                        "missing_tools": result.missing_tools,
                        "hallucinated_tools": result.hallucinated_tools,
                    }],
                    suggested_fix=result.suggested_fix,
                    raw_result=result,
                )
        except Exception as e:
            logger.warning("Tool provision detector failed: %s", e)

        return None

    def _detect_error_patterns(self, trace: UniversalTrace) -> List[DetectionResult]:
        """Detect general error patterns in the trace."""
        results = []

        error_spans = trace.get_errors()
        if not error_spans:
            return results

        # Check for cascading errors (multiple errors in sequence)
        if len(error_spans) >= 2:
            results.append(DetectionResult(
                category=DetectionCategory.UNKNOWN,
                detected=True,
                confidence=0.8,
                severity=Severity.HIGH,
                title="Multiple Errors Detected",
                description=f"{len(error_spans)} spans have errors. This may indicate a cascading failure.",
                evidence=[{
                    "error_count": len(error_spans),
                    "errors": [{"span_id": s.id, "error": s.error} for s in error_spans[:5]],
                }],
                affected_spans=[s.id for s in error_spans],
                suggested_fix="Review the first error in the chain - fixing it may resolve subsequent errors.",
            ))

        return results

    def _detect_grounding_failure(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect F15: Grounding Failure - output not supported by sources.

        Inspired by OfficeQA benchmark showing agents achieve <45% accuracy on
        document-grounded tasks due to extracting wrong values, misattributing data,
        and hallucinating numbers not present in sources.
        """
        # Extract agent output and source documents from trace
        agent_output = ""
        source_documents = []

        for span in trace.spans:
            # Collect LLM outputs
            if span.span_type == SpanType.LLM_CALL and span.response:
                agent_output += span.response + "\n"

            # Collect tool outputs as potential sources
            if span.span_type == SpanType.TOOL_CALL and span.tool_result:
                source_documents.append(str(span.tool_result))

            # Collect retrieval results
            if span.span_type == SpanType.RETRIEVAL and span.output_data:
                source_documents.append(str(span.output_data))

        # Need both output and sources to check grounding
        if not agent_output or not source_documents:
            return None

        try:
            result = self.grounding_detector.detect(
                agent_output=agent_output,
                source_documents=source_documents,
            )

            if result.detected:
                # Map severity
                severity_map = {
                    GroundingSeverity.CRITICAL: Severity.CRITICAL,
                    GroundingSeverity.SEVERE: Severity.HIGH,
                    GroundingSeverity.MODERATE: Severity.MEDIUM,
                    GroundingSeverity.MINOR: Severity.LOW,
                    GroundingSeverity.NONE: Severity.INFO,
                }

                return DetectionResult(
                    category=DetectionCategory.GROUNDING_FAILURE,
                    detected=True,
                    confidence=result.confidence,
                    severity=severity_map.get(result.severity, Severity.MEDIUM),
                    title="Grounding Failure Detected",
                    description=result.explanation,
                    evidence=[{
                        "grounding_score": result.grounding_score,
                        "citation_accuracy": result.citation_accuracy,
                        "ungrounded_claims": len(result.ungrounded_claims),
                        "numerical_errors": len(result.numerical_errors),
                    }],
                    suggested_fix=result.suggested_fix,
                    raw_result=result,
                )
        except Exception as e:
            logger.warning("Grounding detector failed: %s", e)

        return None

    def _detect_retrieval_quality(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect F16: Retrieval Quality Failure - wrong/insufficient documents retrieved.

        Inspired by OfficeQA benchmark showing humans need 50 min/question to find
        data 'buried across decades' - retrieval is the bottleneck.
        """
        # Extract query and retrieved documents from trace
        query = ""
        retrieved_documents = []
        agent_output = ""

        for span in trace.spans:
            # Find the original query (usually first LLM input or user message)
            if span.span_type == SpanType.LLM_CALL and span.prompt and not query:
                query = span.prompt

            # Collect retrieval results
            if span.span_type == SpanType.RETRIEVAL and span.output_data:
                retrieved_documents.append(str(span.output_data))

            # Collect LLM outputs
            if span.span_type == SpanType.LLM_CALL and span.response:
                agent_output += span.response + "\n"

        # Need query and retrieval to check quality
        if not query or not retrieved_documents:
            return None

        try:
            result = self.retrieval_quality_detector.detect(
                query=query,
                retrieved_documents=retrieved_documents,
                agent_output=agent_output,
            )

            if result.detected:
                # Map severity
                severity_map = {
                    RetrievalSeverity.CRITICAL: Severity.CRITICAL,
                    RetrievalSeverity.SEVERE: Severity.HIGH,
                    RetrievalSeverity.MODERATE: Severity.MEDIUM,
                    RetrievalSeverity.MINOR: Severity.LOW,
                    RetrievalSeverity.NONE: Severity.INFO,
                }

                return DetectionResult(
                    category=DetectionCategory.RETRIEVAL_QUALITY,
                    detected=True,
                    confidence=result.confidence,
                    severity=severity_map.get(result.severity, Severity.MEDIUM),
                    title="Retrieval Quality Issue Detected",
                    description=result.explanation,
                    evidence=[{
                        "relevance_score": result.relevance_score,
                        "coverage_score": result.coverage_score,
                        "precision": result.precision,
                        "irrelevant_docs": len(result.irrelevant_docs),
                        "missing_signals": len(result.missing_signals),
                    }],
                    suggested_fix=result.suggested_fix,
                    raw_result=result,
                )
        except Exception as e:
            logger.warning("Retrieval quality detector failed: %s", e)

        return None

    def _detect_hallucination(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect hallucination in agent outputs by checking against source documents."""
        from app.detection.hallucination import SourceDocument

        # Collect agent outputs and source documents from spans
        outputs: List[str] = []
        sources: List[SourceDocument] = []

        for span in trace.spans:
            if span.response and len(span.response) > 50:
                outputs.append(span.response)
            # Extract sources from retrieval spans or metadata
            if span.span_type == SpanType.RETRIEVAL and span.metadata:
                docs = span.metadata.get("retrieved_documents", [])
                for doc in docs:
                    if isinstance(doc, dict) and doc.get("content"):
                        sources.append(SourceDocument(
                            content=doc["content"],
                            metadata=doc.get("metadata", {}),
                        ))

        if not outputs:
            return None

        try:
            combined_output = "\n".join(outputs[-3:])  # Check last 3 outputs
            result = self.hallucination_detector.detect_hallucination(
                combined_output, sources if sources else None,
            )

            if result.detected:
                return DetectionResult(
                    category=DetectionCategory.HALLUCINATION,
                    detected=True,
                    confidence=result.confidence,
                    severity=Severity.HIGH if result.confidence > 0.8 else Severity.MEDIUM,
                    title="Hallucination Detected",
                    description=f"Agent output contains claims not grounded in source documents. "
                               f"Type: {result.hallucination_type or 'general'}. "
                               f"Grounding score: {result.grounding_score:.2f}.",
                    evidence=[{"evidence": result.evidence[:5]}] if result.evidence else [],
                    suggested_fix="Verify agent output against source documents. Add retrieval-augmented generation with citation checking.",
                    raw_result=result,
                )
        except Exception as e:
            logger.warning("Hallucination detector failed: %s", e)

        return None

    def _detect_persona_drift(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect persona drift by checking if agent outputs match their persona."""
        from app.detection.persona import Agent, RoleType

        for span in trace.spans:
            if not span.response or len(span.response) < 50:
                continue

            # Extract persona from span metadata or prompt
            persona = (span.metadata or {}).get("gen_ai.persona", "")
            if not persona and span.prompt:
                # Use first line of system prompt as persona
                persona = span.prompt.split("\n")[0][:200]

            if not persona:
                continue

            try:
                agent = Agent(
                    id=span.agent_name or span.id,
                    persona_description=persona,
                    allowed_actions=["*"],
                )
                result = self.persona_detector.score_consistency(agent, span.response)

                if not result.consistent and result.confidence > 0.6:
                    return DetectionResult(
                        category=DetectionCategory.PERSONA_DRIFT,
                        detected=True,
                        confidence=1.0 - result.score,
                        severity=Severity.MEDIUM,
                        title="Persona Drift Detected",
                        description=f"Agent '{span.agent_name or 'unknown'}' output drifted from its assigned persona. "
                                   f"Consistency score: {result.score:.2f}.",
                        evidence=[{"issues": result.issues[:3]}] if result.issues else [],
                        affected_spans=[span.id],
                        suggested_fix="Reinforce agent persona in system prompt. Add persona compliance checks.",
                        raw_result=result,
                    )
            except Exception as e:
                logger.warning("Persona detector failed on span %s: %s", span.id, e)

        return None

    def _detect_corruption(self, trace: UniversalTrace, snapshots: List[StateSnapshot]) -> List[DetectionResult]:
        """Detect state corruption between sequential agent states."""
        from app.detection.corruption import StateSnapshot as CorruptionSnapshot

        results: List[DetectionResult] = []

        for i in range(1, len(snapshots)):
            try:
                prev = CorruptionSnapshot(
                    state_delta=snapshots[i - 1].state_delta or {},
                    agent_id=snapshots[i - 1].agent_id or "unknown",
                )
                curr = CorruptionSnapshot(
                    state_delta=snapshots[i].state_delta or {},
                    agent_id=snapshots[i].agent_id or "unknown",
                )

                result = self.corruption_detector.detect_corruption_with_confidence(prev, curr)

                if result.detected and result.confidence > 0.5:
                    results.append(DetectionResult(
                        category=DetectionCategory.STATE_CORRUPTION,
                        detected=True,
                        confidence=result.confidence,
                        severity=Severity.HIGH if result.confidence > 0.8 else Severity.MEDIUM,
                        title="State Corruption Detected",
                        description=f"State corruption detected between steps {i - 1} and {i}. "
                                   f"{result.issue_count} issue(s) found.",
                        evidence=[{
                            "issues": [{"type": iss.issue_type, "message": iss.message} for iss in result.issues[:3]],
                        }],
                        suggested_fix="Add state validation between agent handoffs. Implement rollback for corrupted state.",
                        raw_result=result,
                    ))
            except Exception as e:
                logger.warning("Corruption detector failed at step %d: %s", i, e)

        return results

    def _detect_withholding(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect information withholding — agent has relevant info but omits it."""
        for span in trace.spans:
            if not span.response or len(span.response) < 50:
                continue

            # Build context from available info (prompt + tool results)
            internal_state = ""
            if span.prompt:
                internal_state += span.prompt + "\n"
            for s in trace.spans:
                if s.span_type == SpanType.TOOL_CALL and s.tool_result:
                    internal_state += str(s.tool_result) + "\n"

            if not internal_state:
                continue

            try:
                result = self.withholding_detector.detect(
                    internal_state=internal_state,
                    agent_output=span.response,
                )

                if result.detected and result.confidence > 0.5:
                    return DetectionResult(
                        category=DetectionCategory.INFORMATION_WITHHOLDING,
                        detected=True,
                        confidence=result.confidence,
                        severity=Severity.MEDIUM,
                        title="Information Withholding Detected",
                        description=result.explanation,
                        evidence=[{
                        "issues": [{"type": iss.issue_type.value, "info": iss.withheld_info, "description": iss.description} for iss in result.issues[:3]],
                        "retention_ratio": result.information_retention_ratio,
                    }] if result.issues else [],
                        affected_spans=[span.id],
                        suggested_fix=result.suggested_fix,
                        raw_result=result,
                    )
            except Exception as e:
                logger.warning("Withholding detector failed: %s", e)

        return None

    def _detect_derailment(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect task derailment — agent strays from the assigned task."""
        # Extract task from first prompt or metadata
        task = ""
        agent_outputs: List[str] = []

        for span in trace.spans:
            if not task:
                task = (span.metadata or {}).get("gen_ai.task", "")
                if not task and span.prompt:
                    task = span.prompt[:500]
            if span.response and len(span.response) > 50:
                agent_outputs.append(span.response)

        if not task or not agent_outputs:
            return None

        try:
            result = self.derailment_detector.detect(
                task=task,
                output="\n".join(agent_outputs[-3:]),
            )

            if result.detected and result.confidence > 0.5:
                return DetectionResult(
                    category=DetectionCategory.TASK_DERAILMENT,
                    detected=True,
                    confidence=result.confidence,
                    severity=Severity.MEDIUM if result.confidence < 0.8 else Severity.HIGH,
                    title="Task Derailment Detected",
                    description=result.explanation,
                    evidence=[{"topic_drift_score": result.topic_drift_score, "task_coverage": result.task_coverage}],
                    suggested_fix=result.suggested_fix,
                    raw_result=result,
                )
        except Exception as e:
            logger.warning("Derailment detector failed: %s", e)

        return None

    def _detect_communication(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect communication breakdown between agents."""
        # Need at least 2 spans with different agents communicating
        agent_spans = [(s.agent_name or s.id, s) for s in trace.spans if s.response]
        if len(agent_spans) < 2:
            return None

        # Look for sequential agent-to-agent communication
        for i in range(1, len(agent_spans)):
            sender_name, sender_span = agent_spans[i - 1]
            receiver_name, receiver_span = agent_spans[i]

            if not sender_span.response or not receiver_span.response:
                continue

            try:
                result = self.communication_detector.detect(
                    sender_message=sender_span.response,
                    receiver_response=receiver_span.response,
                    sender_name=sender_name,
                    receiver_name=receiver_name,
                )

                if result.detected and result.confidence > 0.5:
                    return DetectionResult(
                        category=DetectionCategory.COMMUNICATION_BREAKDOWN,
                        detected=True,
                        confidence=result.confidence,
                        severity=Severity.MEDIUM if result.confidence < 0.8 else Severity.HIGH,
                        title="Communication Breakdown Detected",
                        description=result.explanation,
                        evidence=[{
                            "breakdown_type": result.breakdown_type.value if result.breakdown_type else None,
                            "intent_alignment": result.intent_alignment,
                        }],
                        affected_spans=[sender_span.id, receiver_span.id],
                        suggested_fix=result.suggested_fix,
                        raw_result=result,
                    )
            except Exception as e:
                logger.warning("Communication detector failed: %s", e)

        return None

    def _detect_specification(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect specification mismatch — output doesn't match requirements."""
        # Extract user intent from ALL spans (multi-turn aggregation).
        # Later turns may refine the specification, so we collect prompts
        # across spans up to a char budget, prioritising later refinements.
        user_prompts: list[str] = []
        task_specification = ""
        char_budget = 3000

        for span in trace.spans:
            if span.prompt:
                user_prompts.append(span.prompt)
            if not task_specification:
                task_specification = (span.metadata or {}).get("gen_ai.task_spec", "")

        # Build aggregated intent: join all prompts (truncate to budget)
        user_intent = ""
        if user_prompts:
            combined = "\n".join(user_prompts)
            user_intent = combined[:char_budget]

        if not task_specification and user_intent:
            task_specification = user_intent[:1000]

        # Need last output to compare against spec
        last_output = ""
        for span in reversed(trace.spans):
            if span.response and len(span.response) > 50:
                last_output = span.response
                break

        if not user_intent or not last_output:
            return None

        try:
            result = self.specification_detector.detect(
                user_intent=user_intent,
                task_specification=task_specification or user_intent,
                original_request=user_intent,
            )

            if result.detected and result.confidence > 0.5:
                return DetectionResult(
                    category=DetectionCategory.SPECIFICATION_MISMATCH,
                    detected=True,
                    confidence=result.confidence,
                    severity=Severity.MEDIUM if result.confidence < 0.8 else Severity.HIGH,
                    title="Specification Mismatch Detected",
                    description=result.explanation,
                    evidence=[{
                        "mismatch_type": result.mismatch_type.value if result.mismatch_type else None,
                        "requirement_coverage": result.requirement_coverage,
                        "missing_requirements": result.missing_requirements[:3],
                    }],
                    suggested_fix=result.suggested_fix,
                    raw_result=result,
                )
        except Exception as e:
            logger.warning("Specification detector failed: %s", e)

        return None

    def _detect_decomposition(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect task decomposition issues — poor subtask breakdown."""
        # Extract task description and decomposition from trace
        task_description = ""
        decomposition = ""

        for span in trace.spans:
            if not task_description:
                task_description = (span.metadata or {}).get("gen_ai.task", "")
                if not task_description and span.prompt:
                    task_description = span.prompt[:500]

            # Look for decomposition in metadata or early responses
            if not decomposition and span.response:
                decomposition = span.response[:2000]

        if not task_description or not decomposition:
            return None

        try:
            result = self.decomposition_detector.detect(
                task_description=task_description,
                decomposition=decomposition,
            )

            if result.detected and result.confidence > 0.5:
                return DetectionResult(
                    category=DetectionCategory.TASK_DECOMPOSITION,
                    detected=True,
                    confidence=result.confidence,
                    severity=Severity.MEDIUM if result.confidence < 0.8 else Severity.HIGH,
                    title="Task Decomposition Issue Detected",
                    description=result.explanation,
                    evidence=[{
                        "subtask_count": result.subtask_count,
                        "problematic_subtasks": result.problematic_subtasks[:3],
                        "vague_count": result.vague_count,
                        "complex_count": result.complex_count,
                    }],
                    suggested_fix=result.suggested_fix,
                    raw_result=result,
                )
        except Exception as e:
            logger.warning("Decomposition detector failed: %s", e)

        return None

    def _detect_context_neglect(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect context neglect — agent ignores relevant context information."""
        for span in trace.spans:
            if not span.response or len(span.response) < 50:
                continue

            # Context comes from prompt + any retrieval/tool data
            context = span.prompt or ""
            if not context:
                continue

            try:
                result = self.context_detector.detect(
                    context=context,
                    output=span.response,
                    task=(span.metadata or {}).get("gen_ai.task", None),
                    agent_name=span.agent_name,
                )

                if result.detected and result.confidence > 0.5:
                    return DetectionResult(
                        category=DetectionCategory.CONTEXT_NEGLECT,
                        detected=True,
                        confidence=result.confidence,
                        severity=Severity.MEDIUM if result.confidence < 0.8 else Severity.HIGH,
                        title="Context Neglect Detected",
                        description=result.explanation,
                        evidence=[{
                            "context_utilization": result.context_utilization,
                            "missing_elements": result.missing_elements[:3],
                        }],
                        affected_spans=[span.id],
                        suggested_fix=result.suggested_fix,
                        raw_result=result,
                    )
            except Exception as e:
                logger.warning("Context neglect detector failed: %s", e)

        return None

    def _detect_coordination(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect coordination failures in multi-agent traces."""
        from app.detection.coordination import Message

        # Build message list from trace spans
        messages: List[Message] = []
        agent_ids: List[str] = []
        seen_agents = set()

        for i, span in enumerate(trace.spans):
            agent_id = span.agent_name or span.id
            if agent_id not in seen_agents:
                agent_ids.append(agent_id)
                seen_agents.add(agent_id)

            if span.response:
                # Determine receiver (next different agent in trace)
                next_agent = agent_id
                for future_span in trace.spans[i + 1:]:
                    next_name = future_span.agent_name or future_span.id
                    if next_name != agent_id:
                        next_agent = next_name
                        break

                messages.append(Message(
                    from_agent=agent_id,
                    to_agent=next_agent,
                    content=span.response,
                    timestamp=float(i),
                ))

        if len(agent_ids) < 2 or len(messages) < 2:
            return None

        try:
            result = self.coordination_analyzer.analyze_coordination_with_confidence(
                messages=messages,
                agent_ids=agent_ids,
            )

            if result.detected and result.confidence > 0.5:
                return DetectionResult(
                    category=DetectionCategory.COORDINATION_FAILURE,
                    detected=True,
                    confidence=result.confidence,
                    severity=Severity.MEDIUM if result.confidence < 0.8 else Severity.HIGH,
                    title="Coordination Failure Detected",
                    description=f"{result.issue_count} coordination issue(s) detected among {len(agent_ids)} agents.",
                    evidence=[{
                        "issues": [{"type": iss.issue_type, "message": iss.message, "agents": iss.agents_involved} for iss in result.issues[:3]],
                        "metrics": result.metrics,
                    }],
                    suggested_fix="Improve agent handoff protocols and add coordination checkpoints.",
                    raw_result=result,
                )
        except Exception as e:
            logger.warning("Coordination detector failed: %s", e)

        return None

    def _detect_workflow(self, trace: UniversalTrace) -> Optional[DetectionResult]:
        """Detect flawed workflow structure."""
        from app.detection.workflow import WorkflowNode

        # Build workflow nodes from trace spans using actual topology
        span_index = {span.id: i for i, span in enumerate(trace.spans)}
        nodes: List[WorkflowNode] = []

        for i, span in enumerate(trace.spans):
            incoming = []
            outgoing = []

            # Use parent_id for actual topology
            if span.parent_id and span.parent_id in span_index:
                parent_idx = span_index[span.parent_id]
                incoming.append(trace.spans[parent_idx].id)
            elif i > 0:
                incoming = [trace.spans[i - 1].id]  # fallback: linear

            # Add outgoing for children (will be filled by other spans' incoming)
            if i + 1 < len(trace.spans):
                next_span = trace.spans[i + 1]
                if not next_span.parent_id or next_span.parent_id not in span_index:
                    outgoing = [next_span.id]

            nodes.append(WorkflowNode(
                id=span.id,
                name=span.agent_name or span.tool_name or f"step_{i}",
                node_type=span.span_type.value if span.span_type else "unknown",
                incoming=incoming,
                outgoing=outgoing,
            ))

        # Agent name repetition detection: add edges between same-agent spans
        agent_positions: Dict[str, int] = {}
        for i, span in enumerate(trace.spans):
            agent = span.agent_name or span.tool_name
            if agent:
                if agent in agent_positions:
                    # Same agent appeared before - add edge from previous to current
                    prev_idx = agent_positions[agent]
                    # Add outgoing edge from prev node to current node
                    nodes[prev_idx].outgoing.append(nodes[i].id)
                    nodes[i].incoming.append(nodes[prev_idx].id)
                agent_positions[agent] = i

        if len(nodes) < 2:
            return None

        try:
            result = self.workflow_detector.detect(nodes=nodes)

            if result.detected and result.confidence > 0.5:
                return DetectionResult(
                    category=DetectionCategory.FLAWED_WORKFLOW,
                    detected=True,
                    confidence=result.confidence,
                    severity=Severity.MEDIUM if result.confidence < 0.8 else Severity.HIGH,
                    title="Flawed Workflow Detected",
                    description=result.explanation,
                    evidence=[{
                        "node_count": result.node_count,
                        "edge_count": result.edge_count,
                        "problematic_nodes": result.problematic_nodes[:3],
                        "issues": [iss.value for iss in result.issues[:5]],
                    }],
                    suggested_fix=result.suggested_fix,
                    raw_result=result,
                )
        except Exception as e:
            logger.warning("Workflow detector failed: %s", e)

        return None

    def _generate_explanation(self, primary: DetectionResult, trace: UniversalTrace) -> str:
        """Generate a human-readable root cause explanation.

        This is a simple template-based explanation. In production, this
        could use an LLM for more detailed analysis.
        """
        explanations = {
            DetectionCategory.LOOP: (
                f"The agent entered a repetitive loop pattern. {primary.description} "
                "This typically happens when the agent doesn't recognize it has already attempted "
                "an action, or when the exit condition for a loop is never satisfied."
            ),
            DetectionCategory.CONTEXT_OVERFLOW: (
                f"The conversation exceeded safe context limits. {primary.description} "
                "When context overflows, the model may lose important information from earlier "
                "in the conversation, leading to inconsistent or degraded responses."
            ),
            DetectionCategory.TOOL_PROVISION: (
                f"A tool call failed during execution. {primary.description} "
                "This could be due to invalid inputs, API errors, or the tool not being available."
            ),
            DetectionCategory.STATE_CORRUPTION: (
                f"Agent state became corrupted during execution. {primary.description} "
                "This can occur when data is improperly serialized, parsed, or when "
                "there are concurrent modifications to shared state."
            ),
            DetectionCategory.HALLUCINATION: (
                f"Agent output contains hallucinated content. {primary.description} "
                "This occurs when the agent generates claims, facts, or references "
                "not supported by the provided source documents or context."
            ),
            DetectionCategory.PERSONA_DRIFT: (
                f"Agent behavior drifted from its assigned persona. {primary.description} "
                "This happens when the agent's output doesn't match its configured role, "
                "tone, or allowed actions."
            ),
            DetectionCategory.GROUNDING_FAILURE: (
                f"Agent output contains information not properly grounded in source documents. "
                f"{primary.description} This is a common issue identified in document-grounded tasks, "
                "where agents extract wrong values from tables, misattribute data to wrong columns, "
                "or hallucinate numbers not present in sources."
            ),
            DetectionCategory.RETRIEVAL_QUALITY: (
                f"Agent retrieved wrong, irrelevant, or insufficient documents for the task. "
                f"{primary.description} Poor retrieval quality is often the bottleneck in RAG systems, "
                "leading to incomplete or incorrect reasoning when relevant documents are missed "
                "or irrelevant documents dilute the context."
            ),
            DetectionCategory.INFORMATION_WITHHOLDING: (
                f"Agent withheld relevant information from its output. {primary.description} "
                "This occurs when the agent has access to pertinent data but fails to include it "
                "in its response, potentially due to overly conservative filtering or context loss."
            ),
            DetectionCategory.TASK_DERAILMENT: (
                f"Agent strayed from its assigned task. {primary.description} "
                "This happens when the agent loses focus on the original objective and "
                "pursues tangential topics or performs unrelated actions."
            ),
            DetectionCategory.COMMUNICATION_BREAKDOWN: (
                f"Communication between agents broke down. {primary.description} "
                "This occurs when one agent's message is misinterpreted, ignored, or "
                "insufficiently acted upon by the receiving agent."
            ),
            DetectionCategory.SPECIFICATION_MISMATCH: (
                f"Agent output does not match the task specification. {primary.description} "
                "This happens when the agent produces output that misses required elements "
                "or deviates from the specified format, constraints, or requirements."
            ),
            DetectionCategory.TASK_DECOMPOSITION: (
                f"Task decomposition has issues. {primary.description} "
                "This occurs when a complex task is broken into subtasks that are too vague, "
                "overlapping, missing dependencies, or not properly scoped."
            ),
            DetectionCategory.CONTEXT_NEGLECT: (
                f"Agent neglected relevant context information. {primary.description} "
                "This happens when important context (previous messages, tool results, "
                "or instructions) is available but not reflected in the agent's response."
            ),
            DetectionCategory.COORDINATION_FAILURE: (
                f"Coordination failure detected among agents. {primary.description} "
                "This occurs when multiple agents fail to properly hand off work, "
                "duplicate effort, or miss necessary synchronization points."
            ),
            DetectionCategory.FLAWED_WORKFLOW: (
                f"Workflow structure has issues. {primary.description} "
                "This indicates problems in the overall execution flow such as "
                "disconnected nodes, missing error handling, or inefficient routing."
            ),
        }

        base_explanation = explanations.get(
            primary.category,
            f"An issue was detected: {primary.description}"
        )

        if primary.suggested_fix:
            base_explanation += f"\n\nSuggested fix: {primary.suggested_fix}"

        return base_explanation


# Convenience function for quick diagnosis
def diagnose_trace(trace: UniversalTrace) -> DiagnosisResult:
    """Convenience function to diagnose a trace.

    Args:
        trace: UniversalTrace to analyze

    Returns:
        DiagnosisResult with findings
    """
    orchestrator = DetectionOrchestrator()
    return orchestrator.analyze_trace(trace)
