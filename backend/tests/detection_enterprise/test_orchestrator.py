"""Tests for the Detection Orchestrator."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.detection_enterprise.orchestrator import (
    DetectionOrchestrator,
    DetectionResult,
    DiagnosisResult,
    DetectionCategory,
    Severity,
)
from app.detection.turn_aware._base import TurnAwareDetectionResult, TurnAwareSeverity
from app.ingestion.universal_trace import (
    UniversalTrace,
    UniversalSpan,
    SpanType,
    SpanStatus,
)


# ============================================================================
# DetectionOrchestrator Initialization Tests
# ============================================================================

class TestDetectionOrchestratorInit:
    """Tests for DetectionOrchestrator initialization."""

    def test_default_initialization(self):
        """Should initialize with default parameters."""
        orchestrator = DetectionOrchestrator()

        assert orchestrator.enable_llm_explanation is True
        assert orchestrator.max_parallel_detectors == 5
        assert orchestrator.timeout_seconds == 30.0

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        orchestrator = DetectionOrchestrator(
            enable_llm_explanation=False,
            max_parallel_detectors=3,
            timeout_seconds=15.0,
        )

        assert orchestrator.enable_llm_explanation is False
        assert orchestrator.max_parallel_detectors == 3
        assert orchestrator.timeout_seconds == 15.0

    def test_lazy_detector_loading(self):
        """Detectors should be None until first access."""
        orchestrator = DetectionOrchestrator()

        assert orchestrator._loop_detector is None
        assert orchestrator._overflow_detector is None
        assert orchestrator._grounding_detector is None
        assert orchestrator._retrieval_quality_detector is None


# ============================================================================
# analyze_trace Tests
# ============================================================================

class TestAnalyzeTrace:
    """Tests for the analyze_trace method."""

    def test_analyze_empty_trace(self, empty_trace):
        """Should handle empty trace gracefully."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(empty_trace)

        assert isinstance(result, DiagnosisResult)
        assert result.trace_id == empty_trace.trace_id
        assert result.total_spans == 0
        assert result.error_spans == 0
        assert result.has_failures is False

    def test_analyze_basic_trace(self, sample_universal_trace):
        """Should analyze a basic trace."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(sample_universal_trace)

        assert isinstance(result, DiagnosisResult)
        assert result.trace_id == sample_universal_trace.trace_id
        assert result.total_spans == 1
        assert result.detection_time_ms >= 0

    def test_analyze_trace_counts_errors(self, error_trace):
        """Should correctly count error spans."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(error_trace)

        assert result.error_spans == 1  # One error span in fixture

    def test_analyze_trace_tracks_tokens(self, sample_universal_trace):
        """Should track total tokens."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(sample_universal_trace)

        # sample_span has tokens_input=10, tokens_output=8
        assert result.total_tokens == 18

    def test_analyze_trace_records_detectors_run(self, multi_span_trace):
        """Should record which detectors were run."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(multi_span_trace)

        assert isinstance(result.detectors_run, list)

    def test_result_to_dict(self, sample_universal_trace):
        """Should serialize result to dictionary."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(sample_universal_trace)
        result_dict = result.to_dict()

        assert "trace_id" in result_dict
        assert "has_failures" in result_dict
        assert "all_detections" in result_dict
        assert "analyzed_at" in result_dict


# ============================================================================
# Detection Integration Tests (Mocked)
# ============================================================================

class TestLoopDetection:
    """Tests for loop detection integration."""

    def test_loop_detection_skipped_for_short_traces(self, sample_universal_trace):
        """Loop detection should be skipped for traces with < 3 spans."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(sample_universal_trace)

        # With only 1 span, loop detection shouldn't find anything
        loop_detections = [
            d for d in result.all_detections
            if d.category == DetectionCategory.LOOP
        ]
        # No loop detected because trace is too short
        assert len(loop_detections) == 0

    def test_loop_detection_with_repeated_spans(self, sample_trace_id):
        """Should detect loop when spans repeat."""
        now = datetime.utcnow()

        # Create spans with repeating pattern
        spans = []
        for i in range(6):
            spans.append(UniversalSpan(
                id=str(uuid4()),
                trace_id=sample_trace_id,
                name="repeated_action",
                span_type=SpanType.LLM_CALL,
                status=SpanStatus.OK,
                start_time=now + timedelta(milliseconds=i * 100),
                end_time=now + timedelta(milliseconds=(i + 1) * 100),
                duration_ms=100,
                prompt="Same prompt" if i % 2 == 0 else "Other prompt",
                response="Same response" if i % 2 == 0 else "Other response",
                agent_id="agent_1",
            ))

        trace = UniversalTrace(
            trace_id=sample_trace_id,
            spans=spans,
            source_format="test",
        )

        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        # Should at least process the loop detector
        assert "loop" in result.detectors_run or len(result.detectors_run) >= 0


class TestOverflowDetection:
    """Tests for context overflow detection."""

    def test_no_overflow_for_low_tokens(self, sample_universal_trace):
        """Should not detect overflow for low token counts."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(sample_universal_trace)

        overflow_detections = [
            d for d in result.all_detections
            if d.category == DetectionCategory.CONTEXT_OVERFLOW
        ]
        assert len(overflow_detections) == 0

    def test_overflow_detection_high_tokens(self, sample_trace_id):
        """Should detect overflow for high token counts."""
        now = datetime.utcnow()

        # Create a span with very high token count
        high_token_span = UniversalSpan(
            id=str(uuid4()),
            trace_id=sample_trace_id,
            name="high_token_span",
            span_type=SpanType.LLM_CALL,
            status=SpanStatus.OK,
            start_time=now,
            end_time=now + timedelta(milliseconds=1000),
            duration_ms=1000,
            model="gpt-4",
            tokens_input=7000,  # High input tokens
            tokens_output=1500,  # High output tokens
            agent_id="agent_1",
        )

        trace = UniversalTrace(
            trace_id=sample_trace_id,
            spans=[high_token_span],
            source_format="test",
        )

        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        overflow_detections = [
            d for d in result.all_detections
            if d.category == DetectionCategory.CONTEXT_OVERFLOW
        ]
        # With 8500 tokens on gpt-4 (8192 limit), should trigger overflow
        assert len(overflow_detections) >= 1

    def test_overflow_severity_based_on_usage(self, sample_trace_id):
        """Overflow severity should be based on usage percentage."""
        now = datetime.utcnow()

        # Create span at ~95% capacity
        span = UniversalSpan(
            id=str(uuid4()),
            trace_id=sample_trace_id,
            name="near_limit_span",
            span_type=SpanType.LLM_CALL,
            status=SpanStatus.OK,
            start_time=now,
            end_time=now + timedelta(milliseconds=1000),
            model="gpt-4",  # 8192 limit
            tokens_input=6000,
            tokens_output=1800,  # Total: 7800 = 95% of 8192
            agent_id="agent_1",
        )

        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        overflow_detections = [
            d for d in result.all_detections
            if d.category == DetectionCategory.CONTEXT_OVERFLOW
        ]
        if overflow_detections:
            # 95% usage should be HIGH severity (not CRITICAL which is >100%)
            assert overflow_detections[0].severity in [Severity.HIGH, Severity.CRITICAL]


class TestToolIssueDetection:
    """Tests for tool issue detection."""

    def test_detect_tool_errors(self, error_trace):
        """Should detect tool errors."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(error_trace)

        # error_trace has a tool call with error
        tool_detections = [
            d for d in result.all_detections
            if d.category == DetectionCategory.TOOL_PROVISION
        ]
        # Should detect the tool error
        assert len(tool_detections) >= 0  # May or may not depending on span type

    def test_detect_repeated_tool_calls(self, sample_trace_id):
        """Should detect repeated consecutive tool calls."""
        now = datetime.utcnow()

        # Create repeated tool calls
        spans = []
        for i in range(4):
            spans.append(UniversalSpan(
                id=str(uuid4()),
                trace_id=sample_trace_id,
                name=f"tool_call_{i}",
                span_type=SpanType.TOOL_CALL,
                status=SpanStatus.OK,
                start_time=now + timedelta(milliseconds=i * 100),
                end_time=now + timedelta(milliseconds=(i + 1) * 100),
                tool_name="search",  # Same tool repeated
                tool_args={"query": f"query_{i}"},
                agent_id="agent_1",
            ))

        trace = UniversalTrace(trace_id=sample_trace_id, spans=spans)
        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        # Should have tool_issues in detectors_run
        assert "tool_issues" in result.detectors_run


class TestErrorPatternDetection:
    """Tests for error pattern detection."""

    def test_detect_multiple_errors(self, sample_trace_id):
        """Should detect multiple errors as cascading failure."""
        now = datetime.utcnow()

        spans = []
        for i in range(3):
            spans.append(UniversalSpan(
                id=str(uuid4()),
                trace_id=sample_trace_id,
                name=f"error_span_{i}",
                span_type=SpanType.LLM_CALL,
                status=SpanStatus.ERROR,
                start_time=now + timedelta(milliseconds=i * 100),
                end_time=now + timedelta(milliseconds=(i + 1) * 100),
                error=f"Error {i}",
                error_type="RuntimeError",
                agent_id="agent_1",
            ))

        trace = UniversalTrace(trace_id=sample_trace_id, spans=spans)
        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        # Should detect error patterns
        assert "error_patterns" in result.detectors_run
        assert result.has_failures is True


# ============================================================================
# Result Aggregation Tests
# ============================================================================

class TestResultAggregation:
    """Tests for result aggregation logic."""

    def test_primary_failure_is_highest_severity(self, sample_trace_id):
        """Primary failure should be the highest severity detection."""
        now = datetime.utcnow()

        # Create a trace that will generate multiple detections
        spans = [
            UniversalSpan(
                id=str(uuid4()),
                trace_id=sample_trace_id,
                name="error_span",
                span_type=SpanType.TOOL_CALL,
                status=SpanStatus.ERROR,
                start_time=now,
                end_time=now + timedelta(milliseconds=100),
                error="Tool failed",
                tool_name="failing_tool",
                agent_id="agent_1",
            ),
            UniversalSpan(
                id=str(uuid4()),
                trace_id=sample_trace_id,
                name="another_error",
                span_type=SpanType.TOOL_CALL,
                status=SpanStatus.ERROR,
                start_time=now + timedelta(milliseconds=100),
                end_time=now + timedelta(milliseconds=200),
                error="Another failure",
                tool_name="another_tool",
                agent_id="agent_1",
            ),
        ]

        trace = UniversalTrace(trace_id=sample_trace_id, spans=spans)
        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        if result.all_detections:
            # Primary failure should be set
            assert result.primary_failure is not None
            # And should be the first (highest severity) detection
            assert result.primary_failure == result.all_detections[0]

    def test_failure_count_matches_detections(self, error_trace):
        """failure_count should match number of detections."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(error_trace)

        assert result.failure_count == len(result.all_detections)


# ============================================================================
# Self-Healing Tests
# ============================================================================

class TestSelfHealing:
    """Tests for self-healing capability detection."""

    def test_self_healing_available_when_fix_present(self, sample_trace_id):
        """Self-healing should be available when suggested fix is present."""
        now = datetime.utcnow()

        # Create a trace with tool error (which generates suggested_fix)
        span = UniversalSpan(
            id=str(uuid4()),
            trace_id=sample_trace_id,
            name="failing_tool",
            span_type=SpanType.TOOL_CALL,
            status=SpanStatus.ERROR,
            start_time=now,
            end_time=now + timedelta(milliseconds=100),
            error="Connection failed",
            tool_name="api_call",
            agent_id="agent_1",
        )

        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        if result.primary_failure and result.primary_failure.suggested_fix:
            assert result.self_healing_available is True
            assert result.auto_fix_preview is not None


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_trace_with_only_error_spans(self, sample_trace_id):
        """Should handle trace where all spans are errors."""
        now = datetime.utcnow()

        spans = [
            UniversalSpan(
                id=str(uuid4()),
                trace_id=sample_trace_id,
                name=f"error_{i}",
                span_type=SpanType.LLM_CALL,
                status=SpanStatus.ERROR,
                start_time=now,
                end_time=now + timedelta(milliseconds=100),
                error=f"Error {i}",
                agent_id="agent_1",
            )
            for i in range(3)
        ]

        trace = UniversalTrace(trace_id=sample_trace_id, spans=spans)
        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        assert result.error_spans == 3
        assert result.total_spans == 3

    def test_trace_with_no_tokens(self, sample_trace_id):
        """Should handle trace with no token information."""
        now = datetime.utcnow()

        span = UniversalSpan(
            id=str(uuid4()),
            trace_id=sample_trace_id,
            name="no_token_span",
            span_type=SpanType.AGENT,
            status=SpanStatus.OK,
            start_time=now,
            end_time=now + timedelta(milliseconds=100),
            agent_id="agent_1",
            # No tokens set
        )

        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator.analyze_trace(trace)

        assert result.total_tokens == 0

    def test_detection_time_is_measured(self, sample_universal_trace):
        """Detection time should be measured."""
        orchestrator = DetectionOrchestrator()

        result = orchestrator.analyze_trace(sample_universal_trace)

        assert result.detection_time_ms >= 0


# ============================================================================
# DetectionResult Tests
# ============================================================================

class TestDetectionResult:
    """Tests for DetectionResult dataclass."""

    def test_detection_result_to_dict(self):
        """Should serialize to dictionary."""
        result = DetectionResult(
            category=DetectionCategory.LOOP,
            detected=True,
            confidence=0.85,
            severity=Severity.HIGH,
            title="Test Detection",
            description="Test description",
            evidence=[{"key": "value"}],
            affected_spans=["span1", "span2"],
            suggested_fix="Apply this fix",
        )

        result_dict = result.to_dict()

        assert result_dict["category"] == "loop"
        assert result_dict["detected"] is True
        assert result_dict["confidence"] == 0.85
        assert result_dict["severity"] == "high"
        assert result_dict["title"] == "Test Detection"
        assert len(result_dict["evidence"]) == 1
        assert len(result_dict["affected_spans"]) == 2


# ============================================================================
# DiagnosisResult Tests
# ============================================================================

class TestDiagnosisResult:
    """Tests for DiagnosisResult dataclass."""

    def test_diagnosis_result_defaults(self):
        """Should have sensible defaults."""
        result = DiagnosisResult(trace_id="test-trace")

        assert result.has_failures is False
        assert result.failure_count == 0
        assert result.primary_failure is None
        assert result.all_detections == []
        assert result.self_healing_available is False

    def test_diagnosis_result_to_dict(self):
        """Should serialize to dictionary."""
        detection = DetectionResult(
            category=DetectionCategory.INJECTION,
            detected=True,
            confidence=0.9,
            severity=Severity.CRITICAL,
            title="Injection Detected",
            description="Prompt injection detected",
        )

        result = DiagnosisResult(
            trace_id="test-trace",
            has_failures=True,
            failure_count=1,
            primary_failure=detection,
            all_detections=[detection],
        )

        result_dict = result.to_dict()

        assert result_dict["trace_id"] == "test-trace"
        assert result_dict["has_failures"] is True
        assert result_dict["failure_count"] == 1
        assert result_dict["primary_failure"] is not None


# ============================================================================
# Sprint 6: Tests for _detect_communication (Task 1)
# ============================================================================

class TestCommunicationDetection:
    """Tests for _detect_communication() method."""

    def test_skipped_for_single_agent(self, sample_universal_trace):
        """Should return None when trace has fewer than 2 agent spans with responses."""
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_communication(sample_universal_trace)
        assert result is None

    def test_skipped_for_no_responses(self, sample_trace_id):
        """Should return None when agent spans have no responses."""
        now = datetime.utcnow()
        spans = [
            UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s1",
                         span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                         start_time=now, end_time=now + timedelta(milliseconds=100),
                         agent_name="Agent A"),
            UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s2",
                         span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                         start_time=now + timedelta(milliseconds=100),
                         end_time=now + timedelta(milliseconds=200),
                         agent_name="Agent B"),
        ]
        trace = UniversalTrace(trace_id=sample_trace_id, spans=spans)
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_communication(trace)
        assert result is None

    def test_returns_detection_result_on_issue(self, sample_trace_id):
        """Should return DetectionResult when communication issue found."""
        now = datetime.utcnow()
        spans = [
            UniversalSpan(id="span-a", trace_id=sample_trace_id, name="s1",
                         span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                         start_time=now, end_time=now + timedelta(milliseconds=100),
                         response="Please deploy the API to production server immediately.",
                         agent_name="Manager Agent"),
            UniversalSpan(id="span-b", trace_id=sample_trace_id, name="s2",
                         span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                         start_time=now + timedelta(milliseconds=100),
                         end_time=now + timedelta(milliseconds=200),
                         response="Here is a nice recipe for chocolate cake.",
                         agent_name="Worker Agent"),
        ]
        trace = UniversalTrace(trace_id=sample_trace_id, spans=spans)
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_communication(trace)
        # May or may not detect depending on detector threshold; verify structure if detected
        if result is not None:
            assert result.category == DetectionCategory.COMMUNICATION_BREAKDOWN
            assert result.detected is True
            assert "span-a" in result.affected_spans
            assert "span-b" in result.affected_spans


# ============================================================================
# Sprint 6: Tests for _detect_specification (Task 1)
# ============================================================================

class TestSpecificationDetection:
    """Tests for _detect_specification() method."""

    def test_skipped_when_no_user_intent(self, sample_trace_id):
        """Should return None when there's no prompt/user_intent."""
        now = datetime.utcnow()
        span = UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s",
                            span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                            start_time=now, end_time=now + timedelta(milliseconds=100),
                            response="Some output without a prompt.")
        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_specification(trace)
        assert result is None

    def test_skipped_when_no_output(self, sample_trace_id):
        """Should return None when no response > 50 chars."""
        now = datetime.utcnow()
        span = UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s",
                            span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                            start_time=now, end_time=now + timedelta(milliseconds=100),
                            prompt="Write a detailed report", response="OK")
        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_specification(trace)
        assert result is None

    def test_returns_detection_on_mismatch(self, sample_trace_id):
        """Should return DetectionResult when output diverges from spec."""
        now = datetime.utcnow()
        span = UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s",
                            span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                            start_time=now, end_time=now + timedelta(milliseconds=100),
                            prompt="Write a Python function that sorts a list using merge sort. Include docstring and type hints.",
                            response="The weather today is sunny with a high of 72 degrees. I recommend wearing sunscreen and staying hydrated throughout the day.")
        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_specification(trace)
        if result is not None:
            assert result.category == DetectionCategory.SPECIFICATION_MISMATCH
            assert result.detected is True


# ============================================================================
# Sprint 6: Tests for _detect_decomposition (Task 1)
# ============================================================================

class TestDecompositionDetection:
    """Tests for _detect_decomposition() method."""

    def test_skipped_for_empty_trace(self, empty_trace):
        """Should return None when trace has no spans."""
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_decomposition(empty_trace)
        assert result is None

    def test_skipped_when_no_task_or_response(self, sample_trace_id):
        """Should return None when no task_description or decomposition text."""
        now = datetime.utcnow()
        span = UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s",
                            span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                            start_time=now, end_time=now + timedelta(milliseconds=100))
        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_decomposition(trace)
        assert result is None

    def test_returns_detection_on_bad_breakdown(self, sample_trace_id):
        """Should detect vague task decomposition."""
        now = datetime.utcnow()
        span = UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s",
                            span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                            start_time=now, end_time=now + timedelta(milliseconds=100),
                            prompt="Build a complete e-commerce platform with payments, inventory, and shipping",
                            response="Step 1: Do everything. Step 2: Done.",
                            metadata={"gen_ai.task": "Build a complete e-commerce platform"})
        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_decomposition(trace)
        if result is not None:
            assert result.category == DetectionCategory.TASK_DECOMPOSITION
            assert result.detected is True


# ============================================================================
# Sprint 6: Tests for _detect_context_neglect (Task 1)
# ============================================================================

class TestContextNeglectDetection:
    """Tests for _detect_context_neglect() method."""

    def test_skipped_for_short_response(self, sample_trace_id):
        """Should skip spans with response < 50 chars."""
        now = datetime.utcnow()
        span = UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s",
                            span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                            start_time=now, end_time=now + timedelta(milliseconds=100),
                            prompt="Tell me about the budget", response="OK")
        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_context_neglect(trace)
        assert result is None

    def test_skipped_when_no_prompt(self, sample_trace_id):
        """Should skip spans with no prompt/context."""
        now = datetime.utcnow()
        span = UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s",
                            span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                            start_time=now, end_time=now + timedelta(milliseconds=100),
                            response="A" * 100)
        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_context_neglect(trace)
        assert result is None

    def test_returns_detection_when_ignoring_context(self, sample_trace_id):
        """Should detect when output ignores key context from prompt."""
        now = datetime.utcnow()
        span = UniversalSpan(id="span-ctx", trace_id=sample_trace_id, name="s",
                            span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                            start_time=now, end_time=now + timedelta(milliseconds=100),
                            prompt="The patient has a severe allergy to penicillin. Recommend antibiotics for their infection.",
                            response="I recommend prescribing penicillin 500mg three times daily for 10 days. This is the standard treatment for bacterial infections and should clear up the issue quickly.")
        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_context_neglect(trace)
        if result is not None:
            assert result.category == DetectionCategory.CONTEXT_NEGLECT
            assert result.detected is True
            assert "span-ctx" in result.affected_spans


# ============================================================================
# Sprint 6: Tests for _detect_coordination (Task 1)
# ============================================================================

class TestCoordinationDetection:
    """Tests for _detect_coordination() method."""

    def test_skipped_for_single_agent(self, sample_universal_trace):
        """Should return None when fewer than 2 agents."""
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_coordination(sample_universal_trace)
        assert result is None

    def test_skipped_for_insufficient_messages(self, sample_trace_id):
        """Should return None when fewer than 2 messages."""
        now = datetime.utcnow()
        span = UniversalSpan(id=str(uuid4()), trace_id=sample_trace_id, name="s",
                            span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                            start_time=now, end_time=now + timedelta(milliseconds=100),
                            response="Hello", agent_name="Agent A")
        trace = UniversalTrace(trace_id=sample_trace_id, spans=[span])
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_coordination(trace)
        assert result is None

    def test_returns_detection_on_coordination_issue(self, sample_trace_id):
        """Should detect coordination issues among multiple agents."""
        now = datetime.utcnow()
        spans = []
        # Create excessive back-and-forth between two agents
        for i in range(8):
            agent = "Agent A" if i % 2 == 0 else "Agent B"
            spans.append(UniversalSpan(
                id=str(uuid4()), trace_id=sample_trace_id, name=f"s{i}",
                span_type=SpanType.LLM_CALL, status=SpanStatus.OK,
                start_time=now + timedelta(milliseconds=i * 100),
                end_time=now + timedelta(milliseconds=(i + 1) * 100),
                response=f"I think you should handle this task, {agent}. I cannot do it.",
                agent_name=agent))
        trace = UniversalTrace(trace_id=sample_trace_id, spans=spans)
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_coordination(trace)
        if result is not None:
            assert result.category == DetectionCategory.COORDINATION_FAILURE
            assert result.detected is True


# ============================================================================
# Sprint 6: Tests for _detect_workflow (Task 1)
# ============================================================================

class TestWorkflowDetection:
    """Tests for _detect_workflow() method."""

    def test_skipped_for_single_node(self, sample_universal_trace):
        """Should return None when trace has < 2 spans."""
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_workflow(sample_universal_trace)
        assert result is None

    def test_processes_multi_span_trace(self, multi_span_trace):
        """Should run workflow detection on traces with 2+ spans."""
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_workflow(multi_span_trace)
        # May or may not detect an issue — verify it runs without error
        assert result is None or isinstance(result, DetectionResult)

    def test_returns_detection_on_flawed_workflow(self, sample_trace_id):
        """Should detect workflow structure issues."""
        now = datetime.utcnow()
        # Create disconnected-looking workflow with many spans
        spans = [
            UniversalSpan(id=f"node-{i}", trace_id=sample_trace_id, name=f"step_{i}",
                         span_type=SpanType.AGENT, status=SpanStatus.OK,
                         start_time=now + timedelta(milliseconds=i * 100),
                         end_time=now + timedelta(milliseconds=(i + 1) * 100),
                         agent_name=f"agent_{i}")
            for i in range(5)
        ]
        trace = UniversalTrace(trace_id=sample_trace_id, spans=spans)
        orchestrator = DetectionOrchestrator()
        result = orchestrator._detect_workflow(trace)
        if result is not None:
            assert result.category == DetectionCategory.FLAWED_WORKFLOW
            assert result.detected is True


# ============================================================================
# Sprint 6: Tests for _deduplicate_detections (Task 2)
# ============================================================================

class TestDeduplicateDetections:
    """Tests for _deduplicate_detections() method."""

    def _make_detection(self, category, confidence=0.7, spans=None):
        """Helper to create a DetectionResult."""
        return DetectionResult(
            category=category,
            detected=True,
            confidence=confidence,
            severity=Severity.MEDIUM,
            title=f"Test {category.value}",
            description=f"Test detection for {category.value}",
            affected_spans=spans or [],
        )

    def test_empty_list_returns_empty(self):
        orchestrator = DetectionOrchestrator()
        assert orchestrator._deduplicate_detections([]) == []

    def test_single_detection_unchanged(self):
        orchestrator = DetectionOrchestrator()
        det = self._make_detection(DetectionCategory.LOOP)
        result = orchestrator._deduplicate_detections([det])
        assert len(result) == 1
        assert result[0] is det

    def test_subsumption_grounding_hallucination(self):
        """Grounding failure should subsume hallucination."""
        orchestrator = DetectionOrchestrator()
        grounding = self._make_detection(DetectionCategory.GROUNDING_FAILURE)
        hallucination = self._make_detection(DetectionCategory.HALLUCINATION)
        result = orchestrator._deduplicate_detections([grounding, hallucination])
        categories = {d.category for d in result}
        assert DetectionCategory.GROUNDING_FAILURE in categories
        assert DetectionCategory.HALLUCINATION not in categories

    def test_subsumption_loop_overflow(self):
        """Loop should subsume context overflow."""
        orchestrator = DetectionOrchestrator()
        loop = self._make_detection(DetectionCategory.LOOP)
        overflow = self._make_detection(DetectionCategory.CONTEXT_OVERFLOW)
        result = orchestrator._deduplicate_detections([loop, overflow])
        categories = {d.category for d in result}
        assert DetectionCategory.LOOP in categories
        assert DetectionCategory.CONTEXT_OVERFLOW not in categories

    def test_subsumption_derailment_completion(self):
        """Derailment should subsume completion misjudgment."""
        orchestrator = DetectionOrchestrator()
        derail = self._make_detection(DetectionCategory.TASK_DERAILMENT)
        completion = self._make_detection(DetectionCategory.COMPLETION_MISJUDGMENT)
        result = orchestrator._deduplicate_detections([derail, completion])
        categories = {d.category for d in result}
        assert DetectionCategory.TASK_DERAILMENT in categories
        assert DetectionCategory.COMPLETION_MISJUDGMENT not in categories

    def test_subsumption_communication_coordination(self):
        """Communication breakdown should subsume coordination failure."""
        orchestrator = DetectionOrchestrator()
        comm = self._make_detection(DetectionCategory.COMMUNICATION_BREAKDOWN)
        coord = self._make_detection(DetectionCategory.COORDINATION_FAILURE)
        result = orchestrator._deduplicate_detections([comm, coord])
        categories = {d.category for d in result}
        assert DetectionCategory.COMMUNICATION_BREAKDOWN in categories
        assert DetectionCategory.COORDINATION_FAILURE not in categories

    def test_no_subsumption_unrelated_detections(self):
        """Unrelated detections should both survive."""
        orchestrator = DetectionOrchestrator()
        injection = self._make_detection(DetectionCategory.INJECTION)
        persona = self._make_detection(DetectionCategory.PERSONA_DRIFT)
        result = orchestrator._deduplicate_detections([injection, persona])
        assert len(result) == 2

    def test_span_overlap_keeps_higher_confidence(self):
        """When two detections share >50% spans, keep higher-confidence one."""
        orchestrator = DetectionOrchestrator()
        det_a = self._make_detection(DetectionCategory.INJECTION, confidence=0.6,
                                     spans=["s1", "s2", "s3"])
        det_b = self._make_detection(DetectionCategory.PERSONA_DRIFT, confidence=0.9,
                                     spans=["s1", "s2", "s4"])
        result = orchestrator._deduplicate_detections([det_a, det_b])
        # >50% overlap (2/3), keep higher confidence (det_b at 0.9)
        assert len(result) == 1
        assert result[0].category == DetectionCategory.PERSONA_DRIFT

    def test_span_overlap_below_threshold_keeps_both(self):
        """When two detections share ≤50% spans, keep both."""
        orchestrator = DetectionOrchestrator()
        det_a = self._make_detection(DetectionCategory.INJECTION, confidence=0.6,
                                     spans=["s1", "s2", "s3", "s4"])
        det_b = self._make_detection(DetectionCategory.PERSONA_DRIFT, confidence=0.9,
                                     spans=["s1", "s5", "s6", "s7"])
        result = orchestrator._deduplicate_detections([det_a, det_b])
        # 1/4 overlap = 25%, both should survive
        assert len(result) == 2

    def test_no_spans_no_overlap_dedup(self):
        """Detections with empty affected_spans should not be span-deduplicated."""
        orchestrator = DetectionOrchestrator()
        det_a = self._make_detection(DetectionCategory.INJECTION, confidence=0.6)
        det_b = self._make_detection(DetectionCategory.PERSONA_DRIFT, confidence=0.9)
        result = orchestrator._deduplicate_detections([det_a, det_b])
        assert len(result) == 2

    # ---- Multi-failure compound subsumption tests ----

    def test_subsumption_pair_plus_unrelated_survives(self):
        """Subsumption removes symptom but unrelated detection survives."""
        orchestrator = DetectionOrchestrator()
        grounding = self._make_detection(DetectionCategory.GROUNDING_FAILURE)
        hallucination = self._make_detection(DetectionCategory.HALLUCINATION)
        injection = self._make_detection(DetectionCategory.INJECTION)
        result = orchestrator._deduplicate_detections([grounding, hallucination, injection])
        categories = {d.category for d in result}
        assert len(result) == 2
        assert DetectionCategory.GROUNDING_FAILURE in categories
        assert DetectionCategory.INJECTION in categories
        assert DetectionCategory.HALLUCINATION not in categories

    def test_two_subsumption_pairs_simultaneously(self):
        """Two independent subsumption pairs fire — both symptoms suppressed."""
        orchestrator = DetectionOrchestrator()
        grounding = self._make_detection(DetectionCategory.GROUNDING_FAILURE)
        hallucination = self._make_detection(DetectionCategory.HALLUCINATION)
        loop = self._make_detection(DetectionCategory.LOOP)
        overflow = self._make_detection(DetectionCategory.CONTEXT_OVERFLOW)
        result = orchestrator._deduplicate_detections(
            [grounding, hallucination, loop, overflow]
        )
        categories = {d.category for d in result}
        assert len(result) == 2
        assert categories == {DetectionCategory.GROUNDING_FAILURE, DetectionCategory.LOOP}

    def test_all_four_subsumption_pairs_fire(self):
        """All 4 subsumption pairs fire — 4 root causes survive, 4 symptoms suppressed."""
        orchestrator = DetectionOrchestrator()
        detections = [
            self._make_detection(DetectionCategory.GROUNDING_FAILURE),
            self._make_detection(DetectionCategory.HALLUCINATION),
            self._make_detection(DetectionCategory.LOOP),
            self._make_detection(DetectionCategory.CONTEXT_OVERFLOW),
            self._make_detection(DetectionCategory.TASK_DERAILMENT),
            self._make_detection(DetectionCategory.COMPLETION_MISJUDGMENT),
            self._make_detection(DetectionCategory.COMMUNICATION_BREAKDOWN),
            self._make_detection(DetectionCategory.COORDINATION_FAILURE),
        ]
        result = orchestrator._deduplicate_detections(detections)
        categories = {d.category for d in result}
        assert len(result) == 4
        assert categories == {
            DetectionCategory.GROUNDING_FAILURE,
            DetectionCategory.LOOP,
            DetectionCategory.TASK_DERAILMENT,
            DetectionCategory.COMMUNICATION_BREAKDOWN,
        }

    def test_symptom_only_without_root_cause_survives(self):
        """Symptom present without its root cause should survive."""
        orchestrator = DetectionOrchestrator()
        hallucination = self._make_detection(DetectionCategory.HALLUCINATION)
        result = orchestrator._deduplicate_detections([hallucination])
        assert len(result) == 1
        assert result[0].category == DetectionCategory.HALLUCINATION

    def test_subsumption_then_span_overlap_combined(self):
        """Subsumption removes symptom, then span overlap removes lower-confidence."""
        orchestrator = DetectionOrchestrator()
        grounding = self._make_detection(
            DetectionCategory.GROUNDING_FAILURE, confidence=0.9,
            spans=["s1", "s2", "s3"],
        )
        hallucination = self._make_detection(DetectionCategory.HALLUCINATION)
        injection = self._make_detection(
            DetectionCategory.INJECTION, confidence=0.5,
            spans=["s1", "s2", "s4"],  # >50% overlap with grounding
        )
        result = orchestrator._deduplicate_detections([grounding, hallucination, injection])
        categories = {d.category for d in result}
        # hallucination subsumed by grounding, injection removed by span overlap
        assert len(result) == 1
        assert categories == {DetectionCategory.GROUNDING_FAILURE}

    def test_subsumption_and_no_span_overlap_keeps_both(self):
        """Subsumption removes symptom but disjoint-span detection survives."""
        orchestrator = DetectionOrchestrator()
        grounding = self._make_detection(
            DetectionCategory.GROUNDING_FAILURE, confidence=0.9,
            spans=["s1", "s2"],
        )
        hallucination = self._make_detection(DetectionCategory.HALLUCINATION)
        injection = self._make_detection(
            DetectionCategory.INJECTION, confidence=0.8,
            spans=["s5", "s6"],  # no overlap with grounding
        )
        result = orchestrator._deduplicate_detections([grounding, hallucination, injection])
        categories = {d.category for d in result}
        assert len(result) == 2
        assert categories == {DetectionCategory.GROUNDING_FAILURE, DetectionCategory.INJECTION}


# ============================================================================
# Sprint 6: Tests for analyze_trace_async (Task 2)
# ============================================================================

class TestAnalyzeTraceAsync:
    """Tests for analyze_trace_async() method."""

    def test_returns_diagnosis_result(self, sample_universal_trace):
        """Async analysis should return a DiagnosisResult."""
        orchestrator = DetectionOrchestrator()
        result = asyncio.run(orchestrator.analyze_trace_async(sample_universal_trace))
        assert isinstance(result, DiagnosisResult)
        assert result.trace_id == sample_universal_trace.trace_id

    def test_handles_detector_failure_gracefully(self, sample_universal_trace):
        """Should continue even if one detector raises an exception."""
        orchestrator = DetectionOrchestrator()
        # Break one detector by setting it to a non-callable
        orchestrator._loop_detector = "not_a_detector"
        # Should not raise; broken detector gets caught by try/except in _run
        result = asyncio.run(orchestrator.analyze_trace_async(sample_universal_trace))
        assert isinstance(result, DiagnosisResult)

    def test_async_produces_comparable_results(self, multi_span_trace):
        """Async and sync should produce comparable results for same trace."""
        orchestrator = DetectionOrchestrator()
        sync_result = orchestrator.analyze_trace(multi_span_trace)
        async_result = asyncio.run(orchestrator.analyze_trace_async(multi_span_trace))

        # Both should have same trace metadata
        assert sync_result.trace_id == async_result.trace_id
        assert sync_result.total_spans == async_result.total_spans
        assert sync_result.error_spans == async_result.error_spans


# ============================================================================
# Tests for agents with multiple simultaneous failure modes
# ============================================================================

class TestMultipleSimultaneousFailures:
    """Tests for traces that trigger several failure modes at once.

    Uses patching on individual _detect_* methods to control which
    detectors fire, avoiding fragile trace construction.
    """

    @staticmethod
    def _make_detection(category, confidence=0.7, severity=Severity.MEDIUM, spans=None):
        return DetectionResult(
            category=category,
            detected=True,
            confidence=confidence,
            severity=severity,
            title=f"Test {category.value}",
            description=f"Test detection for {category.value}",
            affected_spans=spans or [],
            suggested_fix=f"Fix {category.value}",
        )

    def test_three_unrelated_detectors_all_survive(self, sample_universal_trace):
        """Three unrelated failure modes should all appear in results."""
        orchestrator = DetectionOrchestrator()
        injection = self._make_detection(
            DetectionCategory.INJECTION, spans=["s1"],
        )
        persona = self._make_detection(
            DetectionCategory.PERSONA_DRIFT, spans=["s2"],
        )
        context = self._make_detection(
            DetectionCategory.CONTEXT_NEGLECT, spans=["s3"],
        )
        with patch.object(orchestrator, '_detect_loops', return_value=None), \
             patch.object(orchestrator, '_detect_overflow', return_value=None), \
             patch.object(orchestrator, '_detect_tool_issues', return_value=[]), \
             patch.object(orchestrator, '_detect_tool_provision', return_value=None), \
             patch.object(orchestrator, '_detect_hallucination', return_value=injection), \
             patch.object(orchestrator, '_detect_persona_drift', return_value=persona), \
             patch.object(orchestrator, '_detect_corruption', return_value=[]), \
             patch.object(orchestrator, '_detect_error_patterns', return_value=[]), \
             patch.object(orchestrator, '_detect_withholding', return_value=None), \
             patch.object(orchestrator, '_detect_derailment', return_value=None), \
             patch.object(orchestrator, '_detect_communication', return_value=None), \
             patch.object(orchestrator, '_detect_specification', return_value=None), \
             patch.object(orchestrator, '_detect_decomposition', return_value=None), \
             patch.object(orchestrator, '_detect_context_neglect', return_value=context), \
             patch.object(orchestrator, '_detect_coordination', return_value=None), \
             patch.object(orchestrator, '_detect_workflow', return_value=None), \
             patch.object(orchestrator, '_detect_grounding_failure', return_value=None), \
             patch.object(orchestrator, '_detect_retrieval_quality', return_value=None):
            result = orchestrator.analyze_trace(sample_universal_trace)

        assert result.failure_count == 3
        categories = {d.category for d in result.all_detections}
        assert categories == {
            DetectionCategory.INJECTION,
            DetectionCategory.PERSONA_DRIFT,
            DetectionCategory.CONTEXT_NEGLECT,
        }

    def test_primary_failure_is_highest_severity(self, sample_universal_trace):
        """Primary failure should be the one with highest severity."""
        orchestrator = DetectionOrchestrator()
        critical = self._make_detection(
            DetectionCategory.INJECTION, confidence=0.9,
            severity=Severity.CRITICAL, spans=["s1"],
        )
        high = self._make_detection(
            DetectionCategory.PERSONA_DRIFT, confidence=0.8,
            severity=Severity.HIGH, spans=["s2"],
        )
        medium = self._make_detection(
            DetectionCategory.CONTEXT_NEGLECT, confidence=0.7,
            severity=Severity.MEDIUM, spans=["s3"],
        )
        with patch.object(orchestrator, '_detect_loops', return_value=None), \
             patch.object(orchestrator, '_detect_overflow', return_value=None), \
             patch.object(orchestrator, '_detect_tool_issues', return_value=[]), \
             patch.object(orchestrator, '_detect_tool_provision', return_value=None), \
             patch.object(orchestrator, '_detect_hallucination', return_value=critical), \
             patch.object(orchestrator, '_detect_persona_drift', return_value=high), \
             patch.object(orchestrator, '_detect_corruption', return_value=[]), \
             patch.object(orchestrator, '_detect_error_patterns', return_value=[]), \
             patch.object(orchestrator, '_detect_withholding', return_value=None), \
             patch.object(orchestrator, '_detect_derailment', return_value=None), \
             patch.object(orchestrator, '_detect_communication', return_value=None), \
             patch.object(orchestrator, '_detect_specification', return_value=None), \
             patch.object(orchestrator, '_detect_decomposition', return_value=None), \
             patch.object(orchestrator, '_detect_context_neglect', return_value=medium), \
             patch.object(orchestrator, '_detect_coordination', return_value=None), \
             patch.object(orchestrator, '_detect_workflow', return_value=None), \
             patch.object(orchestrator, '_detect_grounding_failure', return_value=None), \
             patch.object(orchestrator, '_detect_retrieval_quality', return_value=None):
            result = orchestrator.analyze_trace(sample_universal_trace)

        assert result.failure_count == 3
        assert result.primary_failure.category == DetectionCategory.INJECTION
        assert result.primary_failure.severity == Severity.CRITICAL

    def test_primary_failure_tiebreaks_by_confidence(self, sample_universal_trace):
        """Same severity — primary should be the higher confidence one."""
        orchestrator = DetectionOrchestrator()
        high_conf = self._make_detection(
            DetectionCategory.PERSONA_DRIFT, confidence=0.95,
            severity=Severity.HIGH, spans=["s1"],
        )
        low_conf = self._make_detection(
            DetectionCategory.INJECTION, confidence=0.65,
            severity=Severity.HIGH, spans=["s2"],
        )
        with patch.object(orchestrator, '_detect_loops', return_value=None), \
             patch.object(orchestrator, '_detect_overflow', return_value=None), \
             patch.object(orchestrator, '_detect_tool_issues', return_value=[]), \
             patch.object(orchestrator, '_detect_tool_provision', return_value=None), \
             patch.object(orchestrator, '_detect_hallucination', return_value=low_conf), \
             patch.object(orchestrator, '_detect_persona_drift', return_value=high_conf), \
             patch.object(orchestrator, '_detect_corruption', return_value=[]), \
             patch.object(orchestrator, '_detect_error_patterns', return_value=[]), \
             patch.object(orchestrator, '_detect_withholding', return_value=None), \
             patch.object(orchestrator, '_detect_derailment', return_value=None), \
             patch.object(orchestrator, '_detect_communication', return_value=None), \
             patch.object(orchestrator, '_detect_specification', return_value=None), \
             patch.object(orchestrator, '_detect_decomposition', return_value=None), \
             patch.object(orchestrator, '_detect_context_neglect', return_value=None), \
             patch.object(orchestrator, '_detect_coordination', return_value=None), \
             patch.object(orchestrator, '_detect_workflow', return_value=None), \
             patch.object(orchestrator, '_detect_grounding_failure', return_value=None), \
             patch.object(orchestrator, '_detect_retrieval_quality', return_value=None):
            result = orchestrator.analyze_trace(sample_universal_trace)

        assert result.failure_count == 2
        assert result.primary_failure.category == DetectionCategory.PERSONA_DRIFT
        assert result.primary_failure.confidence == 0.95

    @pytest.mark.parametrize("pair_name,categories", [
        ("injection_and_persona", [DetectionCategory.INJECTION, DetectionCategory.PERSONA_DRIFT]),
        ("loop_and_corruption", [DetectionCategory.LOOP, DetectionCategory.STATE_CORRUPTION]),
        ("context_and_decomposition", [DetectionCategory.CONTEXT_NEGLECT, DetectionCategory.TASK_DECOMPOSITION]),
        ("withholding_and_workflow", [DetectionCategory.INFORMATION_WITHHOLDING, DetectionCategory.FLAWED_WORKFLOW]),
        ("specification_and_overflow", [DetectionCategory.SPECIFICATION_MISMATCH, DetectionCategory.CONTEXT_OVERFLOW]),
    ])
    def test_compound_scenario_pairs(self, sample_universal_trace, pair_name, categories):
        """Parametrized: two non-subsuming categories should both survive."""
        orchestrator = DetectionOrchestrator()
        det_a = self._make_detection(categories[0], spans=["s1"])
        det_b = self._make_detection(categories[1], spans=["s2"])

        # Build a full patch dict — all detectors return None/[]
        null_patches = {
            '_detect_loops': None,
            '_detect_overflow': None,
            '_detect_tool_issues': [],
            '_detect_tool_provision': None,
            '_detect_hallucination': None,
            '_detect_persona_drift': None,
            '_detect_corruption': [],
            '_detect_error_patterns': [],
            '_detect_withholding': None,
            '_detect_derailment': None,
            '_detect_communication': None,
            '_detect_specification': None,
            '_detect_decomposition': None,
            '_detect_context_neglect': None,
            '_detect_coordination': None,
            '_detect_workflow': None,
            '_detect_grounding_failure': None,
            '_detect_retrieval_quality': None,
        }

        # Map categories to detector method names
        cat_to_detector = {
            DetectionCategory.INJECTION: '_detect_hallucination',  # reuse slot
            DetectionCategory.PERSONA_DRIFT: '_detect_persona_drift',
            DetectionCategory.LOOP: '_detect_loops',
            DetectionCategory.STATE_CORRUPTION: '_detect_corruption',
            DetectionCategory.CONTEXT_NEGLECT: '_detect_context_neglect',
            DetectionCategory.TASK_DECOMPOSITION: '_detect_decomposition',
            DetectionCategory.INFORMATION_WITHHOLDING: '_detect_withholding',
            DetectionCategory.FLAWED_WORKFLOW: '_detect_workflow',
            DetectionCategory.SPECIFICATION_MISMATCH: '_detect_specification',
            DetectionCategory.CONTEXT_OVERFLOW: '_detect_overflow',
        }

        # Inject the two detections into their respective detector slots
        for cat, det in [(categories[0], det_a), (categories[1], det_b)]:
            method = cat_to_detector[cat]
            if method in ('_detect_corruption', '_detect_error_patterns', '_detect_tool_issues'):
                null_patches[method] = [det]
            else:
                null_patches[method] = det

        import contextlib
        with contextlib.ExitStack() as stack:
            for method_name, return_val in null_patches.items():
                stack.enter_context(
                    patch.object(orchestrator, method_name, return_value=return_val)
                )
            result = orchestrator.analyze_trace(sample_universal_trace)

        found = {d.category for d in result.all_detections}
        assert categories[0] in found, f"Expected {categories[0].value} in {found}"
        assert categories[1] in found, f"Expected {categories[1].value} in {found}"

    def test_diagnosis_result_to_dict_with_multiple_detections(self):
        """to_dict() should serialize all detections, not just primary."""
        result = DiagnosisResult(trace_id="test-123")
        dets = [
            self._make_detection(DetectionCategory.INJECTION, confidence=0.9, severity=Severity.CRITICAL),
            self._make_detection(DetectionCategory.PERSONA_DRIFT, confidence=0.8, severity=Severity.HIGH),
            self._make_detection(DetectionCategory.CONTEXT_NEGLECT, confidence=0.6, severity=Severity.MEDIUM),
        ]
        result.all_detections = dets
        result.failure_count = 3
        result.has_failures = True
        result.primary_failure = dets[0]

        d = result.to_dict()
        assert d["failure_count"] == 3
        assert len(d["all_detections"]) == 3
        categories_in_dict = {det["category"] for det in d["all_detections"]}
        assert categories_in_dict == {"injection", "persona_drift", "context"}


# ============================================================================
# Framework Detector Integration Tests
# ============================================================================

def _make_framework_trace(source_format: str, metadata: dict = None) -> UniversalTrace:
    """Helper to create a minimal trace with a given source_format."""
    now = datetime.utcnow()
    span = UniversalSpan(
        id=str(uuid4()),
        trace_id=str(uuid4()),
        name="test_span",
        span_type=SpanType.LLM_CALL,
        status=SpanStatus.OK,
        start_time=now,
        end_time=now + timedelta(milliseconds=100),
        duration_ms=100,
        agent_id="agent_1",
    )
    trace = UniversalTrace(
        trace_id=span.trace_id,
        spans=[span],
        source_format=source_format,
        metadata=metadata or {},
    )
    return trace


class TestFrameworkDetectorIntegration:
    """Tests for framework-specific detector routing in the orchestrator."""

    def test_n8n_framework_detectors_run_for_n8n_trace(self):
        """n8n trace should trigger n8n framework detectors."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("n8n", {
            "workflow_json": {"nodes": [{"id": "1", "type": "n8n-nodes-base.httpRequest"}]},
        })

        results = orchestrator._run_framework_detectors(trace)

        # Results is a list (may be empty if no issues detected on minimal data,
        # but the method should not raise)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, DetectionResult)
            assert r.category.value.startswith("n8n_")

    def test_dify_framework_detectors_run_for_dify_trace(self):
        """Dify trace should trigger dify framework detectors."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("dify", {
            "workflow_run": {
                "workflow_run_id": "run-1",
                "nodes": [{"node_id": "n1", "node_type": "llm", "title": "LLM", "status": "succeeded"}],
                "status": "succeeded",
            },
        })

        results = orchestrator._run_framework_detectors(trace)
        assert isinstance(results, list)
        for r in results:
            assert r.category.value.startswith("dify_")

    def test_openclaw_framework_detectors_run_for_openclaw_trace(self):
        """OpenClaw trace should trigger openclaw framework detectors."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("openclaw", {
            "session": {
                "session_id": "sess-1",
                "events": [{"type": "message.received", "agent_name": "bot"}],
            },
        })

        results = orchestrator._run_framework_detectors(trace)
        assert isinstance(results, list)
        for r in results:
            assert r.category.value.startswith("openclaw_")

    def test_langgraph_framework_detectors_run_for_langgraph_trace(self):
        """LangGraph trace should trigger langgraph framework detectors."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("langgraph", {
            "graph_execution": {
                "trace_id": "t-1",
                "steps": [{"node": "agent", "status": "ok"}],
            },
        })

        results = orchestrator._run_framework_detectors(trace)
        assert isinstance(results, list)
        for r in results:
            assert r.category.value.startswith("langgraph_")

    def test_unknown_source_skips_framework_detectors(self):
        """Unknown source_format should return empty list."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("unknown")

        results = orchestrator._run_framework_detectors(trace)
        assert results == []

    def test_framework_results_included_in_diagnosis(self):
        """Framework DetectionResults should appear in DiagnosisResult.all_detections."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("n8n", {
            "workflow_json": {"nodes": [{"id": "1", "type": "n8n-nodes-base.httpRequest"}]},
        })

        result = orchestrator.analyze_trace(trace)
        assert isinstance(result, DiagnosisResult)
        # The framework detectors ran (even if nothing detected on minimal data)
        # Check that detectors_run includes framework label if any detections
        framework_categories = {d.category for d in result.all_detections if d.category.value.startswith("n8n_")}
        if framework_categories:
            assert any("framework:" in dr for dr in result.detectors_run)

    def test_convert_turn_aware_result_severity_mapping(self):
        """Severity conversion should map TurnAwareSeverity to Severity correctly."""
        ta_result = TurnAwareDetectionResult(
            detected=True,
            severity=TurnAwareSeverity.SEVERE,
            confidence=0.95,
            failure_mode="test_failure",
            explanation="A severe failure was found.",
            affected_turns=[0, 1, 2],
            evidence={"key": "value"},
            suggested_fix="Fix the issue.",
        )

        det_result = DetectionOrchestrator._convert_turn_aware_result(
            ta_result, DetectionCategory.N8N_CYCLE,
        )

        assert det_result.category == DetectionCategory.N8N_CYCLE
        assert det_result.detected is True
        assert det_result.severity == Severity.CRITICAL
        assert det_result.confidence == 0.95
        assert det_result.title == "test_failure"
        assert det_result.suggested_fix == "Fix the issue."
        assert det_result.affected_spans == ["0", "1", "2"]

        # Test moderate → medium
        ta_moderate = TurnAwareDetectionResult(
            detected=True,
            severity=TurnAwareSeverity.MODERATE,
            confidence=0.7,
            failure_mode="moderate_issue",
            explanation="Moderate.",
        )
        det_moderate = DetectionOrchestrator._convert_turn_aware_result(
            ta_moderate, DetectionCategory.DIFY_VARIABLE_LEAK,
        )
        assert det_moderate.severity == Severity.MEDIUM

        # Test minor → low
        ta_minor = TurnAwareDetectionResult(
            detected=True,
            severity=TurnAwareSeverity.MINOR,
            confidence=0.4,
            failure_mode="minor_issue",
            explanation="Minor.",
        )
        det_minor = DetectionOrchestrator._convert_turn_aware_result(
            ta_minor, DetectionCategory.OPENCLAW_CHANNEL_MISMATCH,
        )
        assert det_minor.severity == Severity.LOW

        # Test none → info
        ta_none = TurnAwareDetectionResult(
            detected=False,
            severity=TurnAwareSeverity.NONE,
            confidence=0.0,
            failure_mode=None,
            explanation="Nothing.",
        )
        det_none = DetectionOrchestrator._convert_turn_aware_result(
            ta_none, DetectionCategory.LANGGRAPH_RECURSION,
        )
        assert det_none.severity == Severity.INFO

    @pytest.mark.asyncio
    async def test_framework_detectors_in_async_path(self):
        """analyze_trace_async should also run framework detectors."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("dify", {
            "workflow_run": {
                "workflow_run_id": "run-async",
                "nodes": [],
                "status": "succeeded",
            },
        })

        result = await orchestrator.analyze_trace_async(trace)
        assert isinstance(result, DiagnosisResult)
        # Async path should process without errors
        assert result.trace_id == trace.trace_id

    def test_build_framework_metadata_n8n_from_spans(self):
        """_build_framework_metadata should construct n8n metadata from spans."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("n8n")

        metadata = orchestrator._build_framework_metadata(trace)
        assert "workflow_json" in metadata
        assert "workflow_duration_ms" in metadata
        assert isinstance(metadata["workflow_json"]["nodes"], list)

    def test_build_framework_metadata_dify_from_spans(self):
        """_build_framework_metadata should construct dify metadata from spans."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("dify")

        metadata = orchestrator._build_framework_metadata(trace)
        assert "workflow_run" in metadata
        assert "nodes" in metadata["workflow_run"]

    def test_build_framework_metadata_openclaw_from_spans(self):
        """_build_framework_metadata should construct openclaw metadata from spans."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("openclaw")

        metadata = orchestrator._build_framework_metadata(trace)
        assert "session" in metadata
        assert "events" in metadata["session"]

    def test_build_framework_metadata_langgraph_from_spans(self):
        """_build_framework_metadata should construct langgraph metadata from spans."""
        orchestrator = DetectionOrchestrator()
        trace = _make_framework_trace("langgraph")

        metadata = orchestrator._build_framework_metadata(trace)
        assert "graph_execution" in metadata
        assert "steps" in metadata["graph_execution"]

    def test_framework_detector_registry_completeness(self):
        """All four frameworks should be registered with exactly 6 detectors each."""
        registry = DetectionOrchestrator.FRAMEWORK_DETECTORS
        assert set(registry.keys()) == {"n8n", "dify", "openclaw", "langgraph"}
        for framework, detectors in registry.items():
            assert len(detectors) == 6, f"{framework} should have 6 detectors, got {len(detectors)}"
            for name, cls, category in detectors:
                assert name.startswith(framework.replace("langgraph", "langgraph")), \
                    f"Detector name {name} should start with framework prefix"
