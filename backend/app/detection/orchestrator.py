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
from app.detection.tool_provision import ToolProvisionDetector


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
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Severity levels for detected issues."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "detected": self.detected,
            "confidence": self.confidence,
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
        }


class DetectionOrchestrator:
    """Orchestrates all detection modules for comprehensive trace analysis.

    This orchestrator runs multiple detection algorithms in parallel and
    aggregates results into a unified diagnosis.
    """

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

        # Run error pattern detection
        error_results = self._detect_error_patterns(trace)
        all_detections.extend(error_results)
        if error_results:
            result.detectors_run.append("error_patterns")

        # Filter to only detected issues
        detected_issues = [d for d in all_detections if d.detected]

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
            # Log but don't fail the entire diagnosis
            pass

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
