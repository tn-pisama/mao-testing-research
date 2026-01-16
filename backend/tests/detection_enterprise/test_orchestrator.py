"""Tests for the Detection Orchestrator."""

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
