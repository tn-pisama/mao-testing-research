"""
Tests for the testing module - handoff extraction, assertions, and test generation.
"""

import pytest
from datetime import datetime, timedelta

from app.testing import (
    HandoffExtractor,
    Handoff,
    HandoffAnalysis,
    HandoffAssertions,
    AssertionResult,
    assert_context_complete,
    assert_no_data_loss,
    assert_handoff_sla,
    assert_no_circular_handoff,
    HandoffTestGenerator,
    TestCase,
    TestSuite,
)
from app.testing.handoff import HandoffType, HandoffStatus
from app.testing.assertions import AssertionStatus
from app.testing.generator import TestPriority, TestCategory, TestResult


# =============================================================================
# Handoff Extractor Tests
# =============================================================================

class TestHandoffExtractor:
    """Tests for HandoffExtractor class."""

    def test_extractor_initialization_defaults(self):
        """Test default initialization."""
        extractor = HandoffExtractor()
        assert extractor.context_fields == []
        assert extractor.latency_threshold_ms == 5000

    def test_extractor_initialization_custom(self):
        """Test custom initialization."""
        extractor = HandoffExtractor(
            context_fields=["user_id", "session_id"],
            latency_threshold_ms=1000,
        )
        assert extractor.context_fields == ["user_id", "session_id"]
        assert extractor.latency_threshold_ms == 1000

    def test_extract_from_empty_trace(self):
        """Test extraction from trace with no spans."""
        extractor = HandoffExtractor()
        trace = {"spans": []}
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs == []

    def test_extract_from_single_span_trace(self):
        """Test extraction from trace with only one span."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {"name": "agent1", "output": {"content": "Hello"}}
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs == []

    def test_extract_handoff_between_two_agents(self):
        """Test extraction of handoff between two different agents."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {"name": "agent1", "output": {"content": "Hello", "data": "value1"}},
                {"name": "agent2", "input": {"context": "Hello", "data": "value1"}},
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert len(handoffs) == 1
        assert handoffs[0].sender_agent == "agent1"
        assert handoffs[0].receiver_agent == "agent2"

    def test_no_handoff_same_agent(self):
        """Test that spans from same agent don't create handoff."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {"name": "agent1", "output": {"content": "Step 1"}},
                {"name": "agent1", "input": {"context": "Step 2"}},
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs == []

    def test_no_handoff_for_tool_spans(self):
        """Test that tool/function spans don't create handoffs."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {"name": "agent1", "type": "agent", "output": {"content": "Calling tool"}},
                {"name": "search_tool", "type": "tool", "input": {"query": "test"}},
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs == []

    def test_extract_multiple_handoffs(self):
        """Test extraction of multiple handoffs in chain."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {"name": "planner", "output": {"task": "analyze"}},
                {"name": "analyzer", "input": {"task": "analyze"}, "output": {"result": "done"}},
                {"name": "reporter", "input": {"result": "done"}},
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert len(handoffs) == 2
        assert handoffs[0].sender_agent == "planner"
        assert handoffs[0].receiver_agent == "analyzer"
        assert handoffs[1].sender_agent == "analyzer"
        assert handoffs[1].receiver_agent == "reporter"

    def test_handoff_with_latency_calculation(self):
        """Test latency calculation from timestamps."""
        extractor = HandoffExtractor()
        now = datetime.utcnow()
        later = now + timedelta(milliseconds=250)

        trace = {
            "spans": [
                {
                    "name": "agent1",
                    "end_time": now.isoformat(),
                    "output": {"content": "Done"},
                },
                {
                    "name": "agent2",
                    "start_time": later.isoformat(),
                    "input": {"context": "Starting"},
                },
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert len(handoffs) == 1
        assert handoffs[0].latency_ms >= 200  # Allow some tolerance

    def test_handoff_timeout_status(self):
        """Test timeout status when latency exceeds threshold."""
        extractor = HandoffExtractor(latency_threshold_ms=100)
        now = datetime.utcnow()
        later = now + timedelta(milliseconds=500)

        trace = {
            "spans": [
                {"name": "agent1", "end_time": now.isoformat(), "output": {}},
                {"name": "agent2", "start_time": later.isoformat(), "input": {}},
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs[0].status == HandoffStatus.TIMEOUT

    def test_extract_context_from_nested_data(self):
        """Test context extraction from nested output/input."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {
                    "name": "agent1",
                    "output": {
                        "context": {"user_id": "123", "session": "abc"},
                        "content": "Hello",
                    },
                },
                {
                    "name": "agent2",
                    "input": {
                        "context": {"user_id": "123"},
                    },
                },
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert "user_id" in handoffs[0].context_passed
        assert "session" in handoffs[0].context_passed

    def test_fields_missing_detection(self):
        """Test detection of missing fields in handoff."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {
                    "name": "agent1",
                    "output": {"field1": "value1", "field2": "value2"},
                },
                {
                    "name": "agent2",
                    "input": {"field1": "value1"},  # field2 missing
                },
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert "field2" in handoffs[0].fields_missing
        assert handoffs[0].status == HandoffStatus.PARTIAL

    def test_handoff_type_delegation(self):
        """Test delegation handoff type detection."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {
                    "name": "manager",
                    "output": {"task": "analyze"},
                    "attributes": {"delegates_to": "worker"},
                },
                {"name": "worker", "input": {"task": "analyze"}},
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs[0].handoff_type == HandoffType.DELEGATION

    def test_handoff_type_callback(self):
        """Test callback handoff type detection."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {"name": "worker", "output": {"result": "done"}},
                {
                    "name": "manager",
                    "input": {"result": "done"},
                    "attributes": {"callback_from": "worker"},
                },
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs[0].handoff_type == HandoffType.CALLBACK

    def test_handoff_type_broadcast(self):
        """Test broadcast handoff type detection."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {
                    "name": "coordinator",
                    "output": {"message": "start"},
                    "attributes": {"broadcast": True},
                },
                {"name": "worker1", "input": {"message": "start"}},
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs[0].handoff_type == HandoffType.BROADCAST

    def test_handoff_type_conditional(self):
        """Test conditional handoff type detection."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {
                    "name": "router",
                    "output": {"route": "path_a"},
                    "attributes": {"condition": "score > 0.5"},
                },
                {"name": "handler_a", "input": {"route": "path_a"}},
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs[0].handoff_type == HandoffType.CONDITIONAL

    def test_handoff_type_sequential_default(self):
        """Test that default handoff type is sequential."""
        extractor = HandoffExtractor()
        trace = {
            "spans": [
                {"name": "agent1", "output": {"data": "value"}},
                {"name": "agent2", "input": {"data": "value"}},
            ]
        }
        handoffs = extractor.extract_from_trace(trace)
        assert handoffs[0].handoff_type == HandoffType.SEQUENTIAL


class TestHandoffAnalysis:
    """Tests for handoff analysis."""

    def test_analyze_empty_handoffs(self):
        """Test analysis with no handoffs."""
        extractor = HandoffExtractor()
        analysis = extractor.analyze([])
        assert analysis.total_handoffs == 0
        assert analysis.successful_handoffs == 0
        assert analysis.context_completeness == 1.0
        assert analysis.circular_handoffs == []

    def test_analyze_successful_handoffs(self):
        """Test analysis with all successful handoffs."""
        extractor = HandoffExtractor()
        handoffs = [
            Handoff(
                id="h1",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="a1",
                receiver_agent="a2",
                context_passed={"key": "value"},
                context_received={"key": "value"},
                sender_output="output1",
                receiver_input="input2",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                status=HandoffStatus.SUCCESS,
                fields_expected=["key"],
                fields_received=["key"],
            ),
        ]
        analysis = extractor.analyze(handoffs)
        assert analysis.total_handoffs == 1
        assert analysis.successful_handoffs == 1
        assert analysis.failed_handoffs == 0

    def test_analyze_latency_calculation(self):
        """Test average and max latency calculation."""
        extractor = HandoffExtractor()
        handoffs = [
            Handoff(
                id=f"h{i}",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent=f"a{i}",
                receiver_agent=f"a{i+1}",
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=latency,
                fields_expected=[],
                fields_received=[],
            )
            for i, latency in enumerate([100, 200, 300])
        ]
        analysis = extractor.analyze(handoffs)
        assert analysis.avg_latency_ms == 200
        assert analysis.max_latency_ms == 300

    def test_analyze_context_completeness(self):
        """Test context completeness calculation."""
        extractor = HandoffExtractor()
        handoffs = [
            Handoff(
                id="h1",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="a1",
                receiver_agent="a2",
                context_passed={"f1": "v1", "f2": "v2"},
                context_received={"f1": "v1"},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                fields_expected=["f1", "f2"],
                fields_received=["f1"],
                fields_missing=["f2"],
            ),
        ]
        analysis = extractor.analyze(handoffs)
        assert analysis.context_completeness == 0.5  # 1 of 2 fields received
        assert analysis.data_loss_detected is True

    def test_detect_circular_handoffs(self):
        """Test circular handoff detection."""
        extractor = HandoffExtractor()
        handoffs = [
            Handoff(
                id="h1",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="agent_a",
                receiver_agent="agent_b",
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                fields_expected=[],
                fields_received=[],
            ),
            Handoff(
                id="h2",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="agent_b",
                receiver_agent="agent_a",  # Circular!
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                fields_expected=[],
                fields_received=[],
            ),
        ]
        analysis = extractor.analyze(handoffs)
        assert len(analysis.circular_handoffs) == 1
        assert ("agent_a", "agent_b") in analysis.circular_handoffs or \
               ("agent_b", "agent_a") in analysis.circular_handoffs

    def test_analyze_builds_handoff_graph(self):
        """Test that analysis builds correct handoff graph."""
        extractor = HandoffExtractor()
        handoffs = [
            Handoff(
                id="h1",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="router",
                receiver_agent="worker1",
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                fields_expected=[],
                fields_received=[],
            ),
            Handoff(
                id="h2",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="router",
                receiver_agent="worker2",
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                fields_expected=[],
                fields_received=[],
            ),
        ]
        analysis = extractor.analyze(handoffs)
        assert "router" in analysis.handoff_graph
        assert "worker1" in analysis.handoff_graph["router"]
        assert "worker2" in analysis.handoff_graph["router"]

    def test_analyze_issues_high_latency(self):
        """Test that high latency is flagged as issue."""
        extractor = HandoffExtractor(latency_threshold_ms=100)
        handoffs = [
            Handoff(
                id="h1",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="a1",
                receiver_agent="a2",
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=500,  # Exceeds threshold
                fields_expected=[],
                fields_received=[],
            ),
        ]
        analysis = extractor.analyze(handoffs)
        assert any("High latency" in issue for issue in analysis.issues)


class TestHandoffChain:
    """Tests for get_handoff_chain method."""

    def test_get_handoff_chain(self):
        """Test getting handoff chain from start agent."""
        extractor = HandoffExtractor()
        handoffs = [
            Handoff(
                id="h1",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="agent_a",
                receiver_agent="agent_b",
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                fields_expected=[],
                fields_received=[],
            ),
            Handoff(
                id="h2",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="agent_b",
                receiver_agent="agent_c",
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                fields_expected=[],
                fields_received=[],
            ),
        ]
        chain = extractor.get_handoff_chain(handoffs, "agent_a")
        assert len(chain) == 2
        assert chain[0].sender_agent == "agent_a"
        assert chain[1].sender_agent == "agent_b"

    def test_get_handoff_chain_stops_at_end(self):
        """Test chain stops when no more handoffs found."""
        extractor = HandoffExtractor()
        handoffs = [
            Handoff(
                id="h1",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="agent_a",
                receiver_agent="agent_b",
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                fields_expected=[],
                fields_received=[],
            ),
        ]
        chain = extractor.get_handoff_chain(handoffs, "agent_a")
        assert len(chain) == 1

    def test_get_handoff_chain_nonexistent_start(self):
        """Test chain with nonexistent start agent returns empty."""
        extractor = HandoffExtractor()
        handoffs = [
            Handoff(
                id="h1",
                handoff_type=HandoffType.SEQUENTIAL,
                sender_agent="agent_a",
                receiver_agent="agent_b",
                context_passed={},
                context_received={},
                sender_output="",
                receiver_input="",
                timestamp=datetime.utcnow(),
                latency_ms=100,
                fields_expected=[],
                fields_received=[],
            ),
        ]
        chain = extractor.get_handoff_chain(handoffs, "nonexistent")
        assert chain == []


# =============================================================================
# Handoff Assertions Tests
# =============================================================================

class TestHandoffAssertions:
    """Tests for HandoffAssertions class."""

    @pytest.fixture
    def sample_handoff(self):
        """Create a sample handoff for testing."""
        return Handoff(
            id="test_handoff",
            handoff_type=HandoffType.SEQUENTIAL,
            sender_agent="sender",
            receiver_agent="receiver",
            context_passed={"user_id": "123", "task": "analyze"},
            context_received={"user_id": "123", "task": "analyze"},
            sender_output="Analysis complete",
            receiver_input="Analysis complete",
            timestamp=datetime.utcnow(),
            latency_ms=100,
            status=HandoffStatus.SUCCESS,
            fields_expected=["user_id", "task"],
            fields_received=["user_id", "task"],
        )

    def test_assertions_initialization(self):
        """Test assertions collector initialization."""
        assertions = HandoffAssertions()
        assert assertions.results == []

    def test_assert_context_complete_pass(self, sample_handoff):
        """Test context complete assertion passes when all fields present."""
        assertions = HandoffAssertions()
        result = assertions.assert_context_complete(sample_handoff)
        assert result.status == AssertionStatus.PASSED
        assert result.name == "context_complete"

    def test_assert_context_complete_fail(self, sample_handoff):
        """Test context complete assertion fails when fields missing."""
        sample_handoff.fields_received = ["user_id"]  # Missing "task"
        assertions = HandoffAssertions()
        result = assertions.assert_context_complete(sample_handoff)
        assert result.status == AssertionStatus.FAILED
        assert "task" in result.details["missing"]

    def test_assert_context_complete_custom_fields(self, sample_handoff):
        """Test context complete with custom required fields."""
        assertions = HandoffAssertions()
        result = assertions.assert_context_complete(
            sample_handoff,
            required_fields=["user_id"],  # Only check user_id
        )
        assert result.status == AssertionStatus.PASSED

    def test_assert_no_data_loss_pass(self, sample_handoff):
        """Test no data loss assertion passes when all data preserved."""
        assertions = HandoffAssertions()
        result = assertions.assert_no_data_loss(sample_handoff)
        assert result.status == AssertionStatus.PASSED

    def test_assert_no_data_loss_fail_missing(self, sample_handoff):
        """Test no data loss fails when field is missing."""
        sample_handoff.context_received = {"user_id": "123"}  # Missing "task"
        assertions = HandoffAssertions()
        result = assertions.assert_no_data_loss(sample_handoff)
        assert result.status == AssertionStatus.FAILED

    def test_assert_no_data_loss_fail_modified(self, sample_handoff):
        """Test no data loss fails when field is modified."""
        sample_handoff.context_received = {
            "user_id": "456",  # Modified!
            "task": "analyze",
        }
        assertions = HandoffAssertions()
        result = assertions.assert_no_data_loss(sample_handoff)
        assert result.status == AssertionStatus.FAILED
        assert any("modified" in f for f in result.details["lost_fields"])

    def test_assert_no_data_loss_critical_fields(self, sample_handoff):
        """Test no data loss with specific critical fields."""
        sample_handoff.context_received = {"user_id": "123"}  # task missing
        assertions = HandoffAssertions()
        # Only check user_id (which is present)
        result = assertions.assert_no_data_loss(
            sample_handoff,
            critical_fields=["user_id"],
        )
        assert result.status == AssertionStatus.PASSED

    def test_assert_handoff_sla_pass(self, sample_handoff):
        """Test SLA assertion passes when under threshold."""
        assertions = HandoffAssertions()
        result = assertions.assert_handoff_sla(sample_handoff, max_latency_ms=500)
        assert result.status == AssertionStatus.PASSED

    def test_assert_handoff_sla_fail(self, sample_handoff):
        """Test SLA assertion fails when over threshold."""
        sample_handoff.latency_ms = 600
        assertions = HandoffAssertions()
        result = assertions.assert_handoff_sla(sample_handoff, max_latency_ms=500)
        assert result.status == AssertionStatus.FAILED
        assert result.details["exceeded_by_ms"] == 100

    def test_assert_no_circular_handoff_pass(self):
        """Test circular handoff assertion passes when no cycles."""
        analysis = HandoffAnalysis(
            total_handoffs=2,
            successful_handoffs=2,
            failed_handoffs=0,
            avg_latency_ms=100,
            max_latency_ms=150,
            context_completeness=1.0,
            data_loss_detected=False,
            circular_handoffs=[],
            agents_involved=["a1", "a2", "a3"],
            handoff_graph={"a1": ["a2"], "a2": ["a3"]},
        )
        assertions = HandoffAssertions()
        result = assertions.assert_no_circular_handoff(analysis)
        assert result.status == AssertionStatus.PASSED

    def test_assert_no_circular_handoff_fail(self):
        """Test circular handoff assertion fails when cycles exist."""
        analysis = HandoffAnalysis(
            total_handoffs=2,
            successful_handoffs=2,
            failed_handoffs=0,
            avg_latency_ms=100,
            max_latency_ms=150,
            context_completeness=1.0,
            data_loss_detected=False,
            circular_handoffs=[("a1", "a2")],
            agents_involved=["a1", "a2"],
            handoff_graph={"a1": ["a2"], "a2": ["a1"]},
        )
        assertions = HandoffAssertions()
        result = assertions.assert_no_circular_handoff(analysis)
        assert result.status == AssertionStatus.FAILED

    def test_assert_handoff_success_pass(self, sample_handoff):
        """Test handoff success assertion passes on success status."""
        assertions = HandoffAssertions()
        result = assertions.assert_handoff_success(sample_handoff)
        assert result.status == AssertionStatus.PASSED

    def test_assert_handoff_success_fail(self, sample_handoff):
        """Test handoff success assertion fails on failed status."""
        sample_handoff.status = HandoffStatus.FAILED
        sample_handoff.error = "Connection timeout"
        assertions = HandoffAssertions()
        result = assertions.assert_handoff_success(sample_handoff)
        assert result.status == AssertionStatus.FAILED
        assert result.details["error"] == "Connection timeout"

    def test_assert_output_continuity_pass(self, sample_handoff):
        """Test output continuity assertion passes on similar content."""
        sample_handoff.sender_output = "The analysis shows good results"
        sample_handoff.receiver_input = "Based on analysis good results proceed"
        assertions = HandoffAssertions()
        result = assertions.assert_output_continuity(sample_handoff, min_similarity=0.3)
        assert result.status == AssertionStatus.PASSED

    def test_assert_output_continuity_fail(self, sample_handoff):
        """Test output continuity assertion fails on different content."""
        sample_handoff.sender_output = "The analysis shows good results"
        sample_handoff.receiver_input = "Something completely unrelated"
        assertions = HandoffAssertions()
        result = assertions.assert_output_continuity(sample_handoff, min_similarity=0.5)
        assert result.status == AssertionStatus.FAILED

    def test_assert_output_continuity_skipped(self, sample_handoff):
        """Test output continuity is skipped when output/input empty."""
        sample_handoff.sender_output = ""
        sample_handoff.receiver_input = "Some input"
        assertions = HandoffAssertions()
        result = assertions.assert_output_continuity(sample_handoff)
        assert result.status == AssertionStatus.SKIPPED

    def test_get_results(self, sample_handoff):
        """Test get_results returns all assertion results."""
        assertions = HandoffAssertions()
        assertions.assert_context_complete(sample_handoff)
        assertions.assert_no_data_loss(sample_handoff)
        results = assertions.get_results()
        assert len(results) == 2

    def test_get_summary(self, sample_handoff):
        """Test get_summary returns correct statistics."""
        assertions = HandoffAssertions()
        assertions.assert_context_complete(sample_handoff)  # Pass
        sample_handoff.status = HandoffStatus.FAILED
        assertions.assert_handoff_success(sample_handoff)  # Fail

        summary = assertions.get_summary()
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["pass_rate"] == 0.5

    def test_reset(self, sample_handoff):
        """Test reset clears results."""
        assertions = HandoffAssertions()
        assertions.assert_context_complete(sample_handoff)
        assert len(assertions.results) == 1
        assertions.reset()
        assert len(assertions.results) == 0


class TestStandaloneAssertions:
    """Tests for standalone assertion functions."""

    @pytest.fixture
    def sample_handoff(self):
        """Create a sample handoff for testing."""
        return Handoff(
            id="test_handoff",
            handoff_type=HandoffType.SEQUENTIAL,
            sender_agent="sender",
            receiver_agent="receiver",
            context_passed={"key": "value"},
            context_received={"key": "value"},
            sender_output="output",
            receiver_input="input",
            timestamp=datetime.utcnow(),
            latency_ms=100,
            status=HandoffStatus.SUCCESS,
            fields_expected=["key"],
            fields_received=["key"],
        )

    def test_standalone_assert_context_complete(self, sample_handoff):
        """Test standalone assert_context_complete function."""
        result = assert_context_complete(sample_handoff)
        assert isinstance(result, AssertionResult)
        assert result.status == AssertionStatus.PASSED

    def test_standalone_assert_no_data_loss(self, sample_handoff):
        """Test standalone assert_no_data_loss function."""
        result = assert_no_data_loss(sample_handoff)
        assert isinstance(result, AssertionResult)
        assert result.status == AssertionStatus.PASSED

    def test_standalone_assert_handoff_sla(self, sample_handoff):
        """Test standalone assert_handoff_sla function."""
        result = assert_handoff_sla(sample_handoff, max_latency_ms=500)
        assert isinstance(result, AssertionResult)
        assert result.status == AssertionStatus.PASSED

    def test_standalone_assert_no_circular_handoff(self):
        """Test standalone assert_no_circular_handoff function."""
        analysis = HandoffAnalysis(
            total_handoffs=1,
            successful_handoffs=1,
            failed_handoffs=0,
            avg_latency_ms=100,
            max_latency_ms=100,
            context_completeness=1.0,
            data_loss_detected=False,
            circular_handoffs=[],
            agents_involved=["a1", "a2"],
            handoff_graph={"a1": ["a2"]},
        )
        result = assert_no_circular_handoff(analysis)
        assert isinstance(result, AssertionResult)
        assert result.status == AssertionStatus.PASSED


# =============================================================================
# Test Generator Tests
# =============================================================================

class TestHandoffTestGenerator:
    """Tests for HandoffTestGenerator class."""

    def test_generator_initialization_defaults(self):
        """Test default initialization."""
        generator = HandoffTestGenerator()
        assert generator.default_sla_ms == 500
        assert generator.critical_fields == []

    def test_generator_initialization_custom(self):
        """Test custom initialization."""
        generator = HandoffTestGenerator(
            default_sla_ms=1000,
            critical_fields=["user_id", "session_id"],
        )
        assert generator.default_sla_ms == 1000
        assert generator.critical_fields == ["user_id", "session_id"]

    def test_generate_from_trace(self):
        """Test generating test suite from trace."""
        generator = HandoffTestGenerator()
        trace = {
            "trace_id": "trace_123",
            "tenant_id": "tenant_abc",
            "spans": [
                {"name": "agent1", "output": {"data": "value1"}},
                {"name": "agent2", "input": {"data": "value1"}},
            ],
        }
        suite = generator.generate_from_trace(trace)
        assert isinstance(suite, TestSuite)
        assert suite.trace_id == "trace_123"
        assert suite.tenant_id == "tenant_abc"
        assert len(suite.test_cases) > 0

    def test_generate_from_trace_custom_name(self):
        """Test generating suite with custom name."""
        generator = HandoffTestGenerator()
        trace = {
            "spans": [
                {"name": "agent1", "output": {"data": "value1"}},
                {"name": "agent2", "input": {"data": "value1"}},
            ],
        }
        suite = generator.generate_from_trace(trace, suite_name="Custom Suite")
        assert suite.name == "Custom Suite"

    def test_generates_context_tests(self):
        """Test that context completeness tests are generated."""
        generator = HandoffTestGenerator()
        trace = {
            "spans": [
                {"name": "agent1", "output": {"field1": "value1"}},
                {"name": "agent2", "input": {"field1": "value1"}},
            ],
        }
        suite = generator.generate_from_trace(trace)
        context_tests = [tc for tc in suite.test_cases if tc.category == TestCategory.CONTEXT]
        assert len(context_tests) > 0
        assert "assert_context_complete" in context_tests[0].assertions

    def test_generates_data_integrity_tests(self):
        """Test that data integrity tests are generated."""
        generator = HandoffTestGenerator()
        trace = {
            "spans": [
                {"name": "agent1", "output": {"field1": "value1"}},
                {"name": "agent2", "input": {"field1": "value1"}},
            ],
        }
        suite = generator.generate_from_trace(trace)
        integrity_tests = [tc for tc in suite.test_cases if tc.category == TestCategory.DATA_INTEGRITY]
        assert len(integrity_tests) > 0

    def test_generates_sla_tests(self):
        """Test that SLA compliance tests are generated."""
        generator = HandoffTestGenerator()
        trace = {
            "spans": [
                {"name": "agent1", "output": {}},
                {"name": "agent2", "input": {}},
            ],
        }
        suite = generator.generate_from_trace(trace)
        sla_tests = [tc for tc in suite.test_cases if tc.category == TestCategory.LATENCY]
        assert len(sla_tests) > 0

    def test_generates_circular_test(self):
        """Test that circular handoff test is generated."""
        generator = HandoffTestGenerator()
        trace = {
            "spans": [
                {"name": "agent1", "output": {}},
                {"name": "agent2", "input": {}},
            ],
        }
        suite = generator.generate_from_trace(trace)
        circular_tests = [tc for tc in suite.test_cases if tc.category == TestCategory.CIRCULAR]
        assert len(circular_tests) == 1

    def test_generates_data_loss_warning_test(self):
        """Test that global data loss test is generated when detected."""
        generator = HandoffTestGenerator()
        trace = {
            "spans": [
                {"name": "agent1", "output": {"field1": "value1", "field2": "value2"}},
                {"name": "agent2", "input": {"field1": "value1"}},  # field2 missing
            ],
        }
        suite = generator.generate_from_trace(trace)
        data_loss_tests = [
            tc for tc in suite.test_cases
            if tc.category == TestCategory.DATA_INTEGRITY and "global" in tc.tags
        ]
        assert len(data_loss_tests) == 1
        assert data_loss_tests[0].expected_result == "fail"

    def test_test_case_structure(self):
        """Test that generated test cases have correct structure."""
        generator = HandoffTestGenerator()
        trace = {
            "spans": [
                {"name": "agent1", "output": {"data": "value"}},
                {"name": "agent2", "input": {"data": "value"}},
            ],
        }
        suite = generator.generate_from_trace(trace)
        test_case = suite.test_cases[0]

        assert test_case.id
        assert test_case.name
        assert test_case.description
        assert isinstance(test_case.category, TestCategory)
        assert isinstance(test_case.priority, TestPriority)
        assert isinstance(test_case.tags, list)


class TestRunSuite:
    """Tests for running test suites."""

    def test_run_suite_all_pass(self):
        """Test running suite with all passing tests."""
        generator = HandoffTestGenerator()
        handoff = Handoff(
            id="handoff_0",
            handoff_type=HandoffType.SEQUENTIAL,
            sender_agent="agent1",
            receiver_agent="agent2",
            context_passed={"data": "value"},
            context_received={"data": "value"},
            sender_output="Hello world",
            receiver_input="Hello world",
            timestamp=datetime.utcnow(),
            latency_ms=100,
            status=HandoffStatus.SUCCESS,
            fields_expected=["data"],
            fields_received=["data"],
        )
        analysis = HandoffAnalysis(
            total_handoffs=1,
            successful_handoffs=1,
            failed_handoffs=0,
            avg_latency_ms=100,
            max_latency_ms=100,
            context_completeness=1.0,
            data_loss_detected=False,
            circular_handoffs=[],
            agents_involved=["agent1", "agent2"],
            handoff_graph={"agent1": ["agent2"]},
        )

        trace = {
            "spans": [
                {"name": "agent1", "output": {"data": "value"}},
                {"name": "agent2", "input": {"data": "value"}},
            ],
        }
        suite = generator.generate_from_trace(trace)
        results = generator.run_suite(suite, [handoff], analysis)

        assert len(results) > 0
        passed = sum(1 for r in results if r.status == AssertionStatus.PASSED)
        assert passed > 0

    def test_run_suite_with_failure(self):
        """Test running suite with failing tests."""
        generator = HandoffTestGenerator()
        handoff = Handoff(
            id="handoff_0",
            handoff_type=HandoffType.SEQUENTIAL,
            sender_agent="agent1",
            receiver_agent="agent2",
            context_passed={"data": "value"},
            context_received={},  # Missing data - will fail
            sender_output="output",
            receiver_input="input",
            timestamp=datetime.utcnow(),
            latency_ms=1000,  # Over SLA - will fail
            status=HandoffStatus.FAILED,  # Will fail
            fields_expected=["data"],
            fields_received=[],
            fields_missing=["data"],
        )
        analysis = HandoffAnalysis(
            total_handoffs=1,
            successful_handoffs=0,
            failed_handoffs=1,
            avg_latency_ms=1000,
            max_latency_ms=1000,
            context_completeness=0.0,
            data_loss_detected=True,
            circular_handoffs=[],
            agents_involved=["agent1", "agent2"],
            handoff_graph={"agent1": ["agent2"]},
        )

        trace = {
            "spans": [
                {"name": "agent1", "output": {"data": "value"}},
                {"name": "agent2", "input": {}},
            ],
        }
        suite = generator.generate_from_trace(trace)
        results = generator.run_suite(suite, [handoff], analysis)

        failed = sum(1 for r in results if r.status == AssertionStatus.FAILED)
        assert failed > 0

    def test_run_suite_handles_exceptions(self):
        """Test that run_suite handles exceptions gracefully."""
        generator = HandoffTestGenerator()

        # Create a suite with a test case that will cause an error
        suite = TestSuite(
            id="test_suite",
            name="Error Test",
            description="Tests error handling",
            created_at=datetime.utcnow(),
            test_cases=[
                TestCase(
                    id="bad_test",
                    name="Bad Test",
                    description="This test references a non-existent handoff",
                    category=TestCategory.CONTEXT,
                    priority=TestPriority.HIGH,
                    handoff_id="nonexistent_handoff",
                    assertions=["assert_context_complete"],
                ),
            ],
        )

        analysis = HandoffAnalysis(
            total_handoffs=0,
            successful_handoffs=0,
            failed_handoffs=0,
            avg_latency_ms=0,
            max_latency_ms=0,
            context_completeness=1.0,
            data_loss_detected=False,
            circular_handoffs=[],
            agents_involved=[],
            handoff_graph={},
        )

        # Should not raise, but test won't run assertions without handoff
        results = generator.run_suite(suite, [], analysis)
        assert len(results) == 1


class TestGenerateReport:
    """Tests for report generation."""

    def test_generate_report_all_pass(self):
        """Test report with all passing tests."""
        generator = HandoffTestGenerator()
        results = [
            TestResult(
                test_case=TestCase(
                    id="t1",
                    name="Test 1",
                    description="Test",
                    category=TestCategory.CONTEXT,
                    priority=TestPriority.HIGH,
                ),
                status=AssertionStatus.PASSED,
                duration_ms=10,
                assertions=[],
            ),
            TestResult(
                test_case=TestCase(
                    id="t2",
                    name="Test 2",
                    description="Test",
                    category=TestCategory.LATENCY,
                    priority=TestPriority.MEDIUM,
                ),
                status=AssertionStatus.PASSED,
                duration_ms=10,
                assertions=[],
            ),
        ]
        report = generator.generate_report(results)
        assert report["total"] == 2
        assert report["passed"] == 2
        assert report["failed"] == 0
        assert report["pass_rate"] == 1.0
        assert report["failures"] == []

    def test_generate_report_with_failures(self):
        """Test report with some failing tests."""
        generator = HandoffTestGenerator()
        results = [
            TestResult(
                test_case=TestCase(
                    id="t1",
                    name="Test 1",
                    description="Test",
                    category=TestCategory.CONTEXT,
                    priority=TestPriority.HIGH,
                ),
                status=AssertionStatus.PASSED,
                duration_ms=10,
                assertions=[],
            ),
            TestResult(
                test_case=TestCase(
                    id="t2",
                    name="Test 2",
                    description="Test",
                    category=TestCategory.LATENCY,
                    priority=TestPriority.MEDIUM,
                ),
                status=AssertionStatus.FAILED,
                duration_ms=10,
                assertions=[
                    AssertionResult(
                        name="handoff_sla",
                        status=AssertionStatus.FAILED,
                        message="Exceeded SLA",
                    ),
                ],
            ),
        ]
        report = generator.generate_report(results)
        assert report["total"] == 2
        assert report["passed"] == 1
        assert report["failed"] == 1
        assert report["pass_rate"] == 0.5
        assert len(report["failures"]) == 1
        assert report["failures"][0]["test"] == "Test 2"

    def test_generate_report_by_category(self):
        """Test report groups results by category."""
        generator = HandoffTestGenerator()
        results = [
            TestResult(
                test_case=TestCase(
                    id="t1",
                    name="Test 1",
                    description="Test",
                    category=TestCategory.CONTEXT,
                    priority=TestPriority.HIGH,
                ),
                status=AssertionStatus.PASSED,
                duration_ms=10,
                assertions=[],
            ),
            TestResult(
                test_case=TestCase(
                    id="t2",
                    name="Test 2",
                    description="Test",
                    category=TestCategory.CONTEXT,
                    priority=TestPriority.HIGH,
                ),
                status=AssertionStatus.FAILED,
                duration_ms=10,
                assertions=[],
            ),
            TestResult(
                test_case=TestCase(
                    id="t3",
                    name="Test 3",
                    description="Test",
                    category=TestCategory.LATENCY,
                    priority=TestPriority.MEDIUM,
                ),
                status=AssertionStatus.PASSED,
                duration_ms=10,
                assertions=[],
            ),
        ]
        report = generator.generate_report(results)
        assert "context" in report["by_category"]
        assert report["by_category"]["context"]["passed"] == 1
        assert report["by_category"]["context"]["failed"] == 1
        assert "latency" in report["by_category"]
        assert report["by_category"]["latency"]["passed"] == 1

    def test_generate_report_empty_results(self):
        """Test report with no results."""
        generator = HandoffTestGenerator()
        report = generator.generate_report([])
        assert report["total"] == 0
        assert report["passed"] == 0
        assert report["failed"] == 0
        assert report["pass_rate"] == 0


# =============================================================================
# Module Import Tests
# =============================================================================

class TestModuleImports:
    """Tests for module imports."""

    def test_import_from_testing_module(self):
        """Test that all exports are importable from testing module."""
        from app.testing import (
            HandoffExtractor,
            Handoff,
            HandoffAnalysis,
            HandoffAssertions,
            AssertionResult,
            assert_context_complete,
            assert_no_data_loss,
            assert_handoff_sla,
            assert_no_circular_handoff,
            HandoffTestGenerator,
            TestCase,
            TestSuite,
        )
        assert HandoffExtractor is not None
        assert Handoff is not None
        assert HandoffAnalysis is not None
        assert HandoffAssertions is not None
        assert AssertionResult is not None
        assert assert_context_complete is not None
        assert assert_no_data_loss is not None
        assert assert_handoff_sla is not None
        assert assert_no_circular_handoff is not None
        assert HandoffTestGenerator is not None
        assert TestCase is not None
        assert TestSuite is not None

    def test_import_enums(self):
        """Test that enums are importable."""
        from app.testing.handoff import HandoffType, HandoffStatus
        from app.testing.assertions import AssertionStatus
        from app.testing.generator import TestPriority, TestCategory

        assert HandoffType.SEQUENTIAL
        assert HandoffStatus.SUCCESS
        assert AssertionStatus.PASSED
        assert TestPriority.CRITICAL
        assert TestCategory.CONTEXT
