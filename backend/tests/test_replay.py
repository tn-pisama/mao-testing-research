"""
Tests for Replay Module
=======================

Comprehensive tests for:
- Event recording
- Bundle creation and serialization
- Diff comparison
- Replay engine execution
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from app.replay.recorder import (
    ReplayRecorder,
    RecordedEvent,
    EventType,
)
from app.replay.bundle import (
    ReplayBundle,
    BundleMetadata,
)
from app.replay.diff import (
    ReplayDiff,
    DiffResult,
    DiffType,
    DiffSegment,
)
from app.replay.engine import (
    ReplayEngine,
    ReplayMode,
    ReplayStatus,
    ReplayResult,
)


# =============================================================================
# Recorder Tests
# =============================================================================

class TestRecordedEvent:
    """Tests for recorded events."""

    def test_create_event(self):
        """Test creating a recorded event."""
        event = RecordedEvent(
            event_type=EventType.LLM_RESPONSE,
            sequence_number=1,
            agent_name="TestAgent",
            output_data={"content": "Hello"},
        )

        assert event.event_type == EventType.LLM_RESPONSE
        assert event.sequence_number == 1
        assert event.agent_name == "TestAgent"

    def test_compute_checksum(self):
        """Test checksum computation."""
        event = RecordedEvent(
            event_type=EventType.LLM_RESPONSE,
            sequence_number=1,
            input_data={"prompt": "Hello"},
            output_data={"content": "Hi"},
        )

        checksum = event.compute_checksum()
        assert checksum is not None
        assert len(checksum) == 16

    def test_checksum_deterministic(self):
        """Test that checksum is deterministic."""
        event1 = RecordedEvent(
            event_type=EventType.TOOL_CALL,
            sequence_number=1,
            input_data={"tool": "search"},
        )
        event2 = RecordedEvent(
            event_type=EventType.TOOL_CALL,
            sequence_number=1,
            input_data={"tool": "search"},
        )

        assert event1.compute_checksum() == event2.compute_checksum()


class TestReplayRecorder:
    """Tests for replay recorder."""

    def test_create_recorder(self):
        """Test creating a recorder."""
        recorder = ReplayRecorder(trace_id="trace-1", tenant_id="tenant-1")

        assert recorder.trace_id == "trace-1"
        assert recorder.tenant_id == "tenant-1"
        assert len(recorder.events) == 0

    def test_set_context(self):
        """Test setting context."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")
        recorder.set_context(agent_name="Agent1", span_id="span-1")

        assert recorder.current_agent == "Agent1"
        assert recorder.current_span == "span-1"

    def test_record_llm_request(self):
        """Test recording LLM request."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")
        recorder.set_context(agent_name="Agent1")

        event = recorder.record_llm_request(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4",
            parameters={"temperature": 0.7},
        )

        assert event.event_type == EventType.LLM_REQUEST
        assert event.model == "gpt-4"
        assert event.sequence_number == 1
        assert event.checksum is not None

    def test_record_llm_response(self):
        """Test recording LLM response."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")

        event = recorder.record_llm_response(
            content="Hello! How can I help?",
            model="gpt-4",
            tokens_used=50,
            latency_ms=200,
        )

        assert event.event_type == EventType.LLM_RESPONSE
        assert event.tokens_used == 50
        assert event.latency_ms == 200

    def test_record_tool_call(self):
        """Test recording tool call."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")

        event = recorder.record_tool_call(
            tool_name="search",
            arguments={"query": "weather"},
            tool_call_id="tc-1",
        )

        assert event.event_type == EventType.TOOL_CALL
        assert event.input_data["tool_name"] == "search"

    def test_record_tool_response(self):
        """Test recording tool response."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")

        event = recorder.record_tool_response(
            tool_name="search",
            result={"results": ["sunny", "warm"]},
            latency_ms=150,
            success=True,
        )

        assert event.event_type == EventType.TOOL_RESPONSE
        assert event.output_data["success"] == True

    def test_record_state_transition(self):
        """Test recording state transition."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")

        event = recorder.record_state_transition(
            from_state={"step": 1},
            to_state={"step": 2},
            trigger="next",
        )

        assert event.event_type == EventType.STATE_TRANSITION
        assert event.input_data["from_state"]["step"] == 1
        assert event.output_data["to_state"]["step"] == 2

    def test_record_handoff(self):
        """Test recording agent handoff."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")
        recorder.set_context(agent_name="Agent1")

        event = recorder.record_handoff(
            from_agent="Agent1",
            to_agent="Agent2",
            context={"task": "continue"},
        )

        assert event.event_type == EventType.AGENT_HANDOFF
        assert recorder.current_agent == "Agent2"

    def test_record_error(self):
        """Test recording error."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")

        event = recorder.record_error(
            error_type="ValueError",
            message="Invalid input",
            stack_trace="line 1...",
        )

        assert event.event_type == EventType.ERROR
        assert event.output_data["error_type"] == "ValueError"

    def test_create_checkpoint(self):
        """Test creating checkpoint."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")

        event = recorder.create_checkpoint(
            name="before_api_call",
            state={"data": "saved"},
        )

        assert event.event_type == EventType.CHECKPOINT
        assert event.input_data["name"] == "before_api_call"

    def test_sequence_numbering(self):
        """Test sequence numbers increment correctly."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")

        e1 = recorder.record_llm_request([], "gpt-4")
        e2 = recorder.record_llm_response("Hi", "gpt-4", 10, 100)
        e3 = recorder.record_tool_call("search", {})

        assert e1.sequence_number == 1
        assert e2.sequence_number == 2
        assert e3.sequence_number == 3

    def test_get_events(self):
        """Test getting all events."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")
        recorder.record_llm_request([], "gpt-4")
        recorder.record_llm_response("Hi", "gpt-4", 10, 100)

        events = recorder.get_events()
        assert len(events) == 2

    def test_get_llm_responses(self):
        """Test getting LLM responses only."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")
        recorder.record_llm_request([], "gpt-4")
        recorder.record_llm_response("Hi", "gpt-4", 10, 100)
        recorder.record_tool_call("search", {})

        responses = recorder.get_llm_responses()
        assert len(responses) == 1

    def test_get_checkpoints(self):
        """Test getting checkpoints only."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")
        recorder.create_checkpoint("cp1", {})
        recorder.record_llm_response("Hi", "gpt-4", 10, 100)
        recorder.create_checkpoint("cp2", {})

        checkpoints = recorder.get_checkpoints()
        assert len(checkpoints) == 2

    def test_to_dict(self):
        """Test serialization to dict."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")
        recorder.record_llm_response("Hi", "gpt-4", 10, 100)

        data = recorder.to_dict()

        assert data["trace_id"] == "t1"
        assert data["event_count"] == 1
        assert len(data["events"]) == 1


# =============================================================================
# Bundle Tests
# =============================================================================

class TestBundleMetadata:
    """Tests for bundle metadata."""

    def test_create_metadata(self):
        """Test creating bundle metadata."""
        metadata = BundleMetadata(
            trace_id="trace-1",
            tenant_id="tenant-1",
            original_duration_ms=1000,
            event_count=10,
            llm_call_count=3,
            tool_call_count=2,
            checkpoint_count=1,
        )

        assert metadata.trace_id == "trace-1"
        assert metadata.event_count == 10


class TestReplayBundle:
    """Tests for replay bundles."""

    def _create_sample_events(self) -> list[RecordedEvent]:
        """Create sample events for testing."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")
        recorder.set_context(agent_name="TestAgent")
        recorder.record_llm_request([{"role": "user", "content": "Hi"}], "gpt-4")
        recorder.record_llm_response("Hello!", "gpt-4", 20, 150)
        recorder.record_tool_call("search", {"q": "test"})
        recorder.record_tool_response("search", {"results": []}, 100)
        recorder.create_checkpoint("mid", {"step": 1})
        return recorder.get_events()

    def test_create_bundle_from_recorder(self):
        """Test creating bundle from recorder events."""
        events = self._create_sample_events()

        bundle = ReplayBundle.from_recorder(
            trace_id="t1",
            tenant_id="tenant-1",
            events=events,
            duration_ms=500,
        )

        assert bundle.metadata.trace_id == "t1"
        assert bundle.metadata.event_count == 5
        assert bundle.metadata.llm_call_count == 1
        assert bundle.metadata.tool_call_count == 1
        assert bundle.metadata.checkpoint_count == 1

    def test_bundle_frozen_responses(self):
        """Test frozen responses are captured."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        assert "llm_0" in bundle.frozen_responses
        assert bundle.frozen_responses["llm_0"]["content"] == "Hello!"

    def test_get_frozen_llm_response(self):
        """Test getting frozen LLM response."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        response = bundle.get_frozen_llm_response(0)
        assert response is not None
        assert response["content"] == "Hello!"

    def test_get_frozen_tool_response(self):
        """Test getting frozen tool response."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        response = bundle.get_frozen_tool_response("search")
        assert response is not None

    def test_get_checkpoint(self):
        """Test getting checkpoint by name."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        checkpoint = bundle.get_checkpoint("mid")
        assert checkpoint is not None
        assert checkpoint.event_type == EventType.CHECKPOINT

    def test_get_events_after_checkpoint(self):
        """Test getting events after checkpoint."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        # Checkpoint is the 5th event (index 4, sequence 5)
        after = bundle.get_events_after_checkpoint("mid")
        # Should return events after the checkpoint
        assert len(after) < len(events)

    def test_compute_checksum(self):
        """Test bundle checksum computation."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        checksum = bundle.compute_checksum()
        assert checksum is not None
        assert len(checksum) == 32

    def test_serialize_deserialize(self):
        """Test bundle serialization and deserialization."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        serialized = bundle.serialize(compress=True)
        assert isinstance(serialized, bytes)

        restored = ReplayBundle.deserialize(serialized, compressed=True)
        assert restored.metadata.trace_id == "t1"
        assert len(restored.events) == 5

    def test_serialize_uncompressed(self):
        """Test uncompressed serialization."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        serialized = bundle.serialize(compress=False)
        restored = ReplayBundle.deserialize(serialized, compressed=False)

        assert restored.metadata.trace_id == "t1"

    def test_to_partial_bundle(self):
        """Test creating partial bundle."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        partial = bundle.to_partial_bundle(freeze_agents=["TestAgent"])

        assert partial.metadata.trace_id == "t1"
        # Should have additional frozen responses for the agent
        assert len(partial.frozen_responses) >= len(bundle.frozen_responses)

    def test_create_what_if_bundle(self):
        """Test creating what-if bundle with modifications."""
        events = self._create_sample_events()
        bundle = ReplayBundle.from_recorder("t1", "tenant-1", events)

        # Modify event at sequence 2 (LLM response)
        modified = bundle.create_what_if_bundle({
            2: {"output_data": {"content": "Modified response"}}
        })

        assert modified.metadata.trace_id == "t1"
        # Find the modified event
        for event in modified.events:
            if event.sequence_number == 2:
                assert event.output_data["content"] == "Modified response"


# =============================================================================
# Diff Tests
# =============================================================================

class TestReplayDiff:
    """Tests for replay diff comparison."""

    def test_compare_identical(self):
        """Test comparing identical texts."""
        diff = ReplayDiff()
        result = diff.compare_text("Hello world", "Hello world")

        assert result.diff_type == DiffType.IDENTICAL
        assert result.similarity_score == 1.0
        assert len(result.segments) == 0

    def test_compare_minor_difference(self):
        """Test comparing texts with minor differences."""
        diff = ReplayDiff()
        result = diff.compare_text(
            "Hello world, how are you today?",
            "Hello world, how are you?"
        )

        assert result.diff_type in [DiffType.MINOR, DiffType.MODERATE]
        assert result.similarity_score > 0.7

    def test_compare_major_difference(self):
        """Test comparing texts with major differences."""
        diff = ReplayDiff()
        result = diff.compare_text(
            "The quick brown fox jumps over the lazy dog",
            "Lorem ipsum dolor sit amet consectetur"
        )

        assert result.diff_type in [DiffType.MAJOR, DiffType.COMPLETELY_DIFFERENT]
        assert result.similarity_score < 0.5

    def test_compare_empty_texts(self):
        """Test comparing empty texts."""
        diff = ReplayDiff()

        result = diff.compare_text("", "")
        assert result.similarity_score == 1.0

        result = diff.compare_text("Hello", "")
        assert result.similarity_score == 0.0

    def test_diff_segments(self):
        """Test diff segments are computed."""
        diff = ReplayDiff()
        result = diff.compare_text("Hello world", "Hello there world")

        assert len(result.segments) > 0

    def test_changed_lines_count(self):
        """Test changed lines counting."""
        diff = ReplayDiff()
        result = diff.compare_text(
            "Line 1\nLine 2\nLine 3",
            "Line 1\nModified\nLine 3"
        )

        assert result.changed_lines >= 1

    def test_compare_structured(self):
        """Test structured comparison."""
        diff = ReplayDiff()

        original = {"name": "John", "age": "30"}
        replay = {"name": "John", "age": "31"}

        results = diff.compare_structured(original, replay)

        assert "name" in results
        assert "age" in results
        assert results["name"].diff_type == DiffType.IDENTICAL
        assert results["age"].diff_type != DiffType.IDENTICAL

    def test_compare_multiple(self):
        """Test comparing multiple replays."""
        diff = ReplayDiff()

        original = "Hello world"
        replays = {
            "replay_a": "Hello world",
            "replay_b": "Hello there",
            "replay_c": "Goodbye world",
        }

        results = diff.compare_multiple(original, replays)

        assert len(results) == 3
        assert results["replay_a"].diff_type == DiffType.IDENTICAL

    def test_custom_thresholds(self):
        """Test custom similarity thresholds."""
        diff = ReplayDiff(
            similarity_threshold_identical=0.999,
            similarity_threshold_minor=0.95,
            similarity_threshold_moderate=0.80,
        )

        result = diff.compare_text("Hello world", "Hello World")
        # With stricter thresholds, may not be identical
        assert result.similarity_score < 1.0

    def test_format_diff_html(self):
        """Test HTML diff formatting."""
        diff = ReplayDiff()
        result = diff.compare_text("Hello", "Hello world")

        html = diff.format_diff_html(result, "Hello", "Hello world")
        assert isinstance(html, str)

    def test_format_diff_markdown(self):
        """Test markdown diff formatting."""
        diff = ReplayDiff()
        result = diff.compare_text("Hello", "Hello world")

        md = diff.format_diff_markdown(result, "Hello", "Hello world")

        assert "## Diff Summary" in md or "Identical" in md


# =============================================================================
# Engine Tests
# =============================================================================

class TestReplayEngine:
    """Tests for replay engine."""

    def _create_sample_bundle(self) -> ReplayBundle:
        """Create sample bundle for testing."""
        recorder = ReplayRecorder(trace_id="t1", tenant_id="t1")
        recorder.set_context(agent_name="Agent1")
        recorder.record_llm_request([{"role": "user", "content": "Hi"}], "gpt-4")
        recorder.record_llm_response("Hello!", "gpt-4", 20, 150)
        recorder.set_context(agent_name="Agent2")
        recorder.record_llm_request([{"role": "user", "content": "Continue"}], "gpt-4")
        recorder.record_llm_response("Sure!", "gpt-4", 15, 100)

        return ReplayBundle.from_recorder(
            trace_id="t1",
            tenant_id="tenant-1",
            events=recorder.get_events(),
            duration_ms=300,
        )

    def test_create_engine(self):
        """Test creating replay engine."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle, mode=ReplayMode.FULL)

        assert engine.bundle == bundle
        assert engine.mode == ReplayMode.FULL

    def test_freeze_agents(self):
        """Test freezing agents."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle)
        engine.freeze_agents(["Agent1"])

        assert "Agent1" in engine.frozen_agents
        assert "Agent2" in engine.live_agents

    def test_set_live_agents(self):
        """Test setting live agents."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle)
        engine.set_live_agents(["Agent2"])

        assert "Agent2" in engine.live_agents
        assert "Agent1" in engine.frozen_agents

    def test_get_next_llm_response_full_mode(self):
        """Test getting LLM response in full mode."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle, mode=ReplayMode.FULL)

        response = engine.get_next_llm_response()
        assert response is not None
        assert response["content"] == "Hello!"

        response2 = engine.get_next_llm_response()
        assert response2["content"] == "Sure!"

    def test_get_next_llm_response_partial_frozen(self):
        """Test getting LLM response in partial mode for frozen agent."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle, mode=ReplayMode.PARTIAL)
        engine.freeze_agents(["Agent1"])

        response = engine.get_next_llm_response(agent_name="Agent1")
        assert response is not None

    def test_get_next_llm_response_partial_live(self):
        """Test getting LLM response in partial mode for live agent."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle, mode=ReplayMode.PARTIAL)
        engine.freeze_agents(["Agent1"])

        response = engine.get_next_llm_response(agent_name="Agent2")
        assert response is None  # Live agent should get None

    def test_record_divergence(self):
        """Test recording divergence."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle)

        engine.record_divergence(
            event_index=1,
            expected="Hello",
            actual="Hi",
            divergence_type="llm_response",
        )

        assert len(engine.divergences) == 1
        assert engine.divergences[0]["type"] == "llm_response"

    @pytest.mark.asyncio
    async def test_execute_full_replay(self):
        """Test full replay execution."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle, mode=ReplayMode.FULL)

        result = await engine.execute_full_replay()

        assert result.status == ReplayStatus.COMPLETED
        assert result.events_replayed == 4
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_full_replay_with_handler(self):
        """Test full replay with event handler."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle, mode=ReplayMode.FULL)

        handled_events = []
        def handler(event):
            handled_events.append(event)

        result = await engine.execute_full_replay(event_handler=handler)

        assert result.status == ReplayStatus.COMPLETED
        assert len(handled_events) == 4

    @pytest.mark.asyncio
    async def test_execute_partial_replay(self):
        """Test partial replay execution."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle, mode=ReplayMode.PARTIAL)
        engine.freeze_agents(["Agent1"])

        async def live_executor(agent_name, input_data):
            return {"content": "Live response"}

        result = await engine.execute_partial_replay(live_executor)

        assert result.status in [ReplayStatus.COMPLETED, ReplayStatus.DIVERGED]

    @pytest.mark.asyncio
    async def test_execute_validation_replay(self):
        """Test validation replay execution."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle, mode=ReplayMode.VALIDATION)

        async def live_executor(agent_name, input_data):
            return {"content": "Hello!"}  # Same as recorded

        result = await engine.execute_validation_replay(
            live_executor,
            comparison_threshold=0.5,
        )

        assert result.status in [ReplayStatus.COMPLETED, ReplayStatus.DIVERGED]

    def test_reset(self):
        """Test engine reset."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle, mode=ReplayMode.FULL)

        engine.get_next_llm_response()
        engine.record_divergence(0, "a", "b", "test")

        engine.reset()

        assert engine.current_event_index == 0
        assert engine.llm_response_index == 0
        assert len(engine.divergences) == 0

    def test_compute_similarity(self):
        """Test similarity computation."""
        bundle = self._create_sample_bundle()
        engine = ReplayEngine(bundle)

        sim = engine._compute_similarity("hello world", "hello world")
        assert sim == 1.0

        sim = engine._compute_similarity("hello", "goodbye")
        assert sim < 1.0


# =============================================================================
# Integration Tests
# =============================================================================

class TestReplayIntegration:
    """Integration tests for replay module."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete record-bundle-replay workflow."""
        # 1. Record events
        recorder = ReplayRecorder(trace_id="trace-123", tenant_id="tenant-1")
        recorder.set_context(agent_name="MainAgent")

        recorder.record_llm_request(
            messages=[{"role": "user", "content": "What's the weather?"}],
            model="gpt-4",
        )
        recorder.record_llm_response(
            content="Let me check the weather for you.",
            model="gpt-4",
            tokens_used=30,
            latency_ms=200,
        )
        recorder.record_tool_call("weather_api", {"location": "NYC"})
        recorder.record_tool_response("weather_api", {"temp": 72}, 150)
        recorder.record_llm_response(
            content="It's 72 degrees in NYC.",
            model="gpt-4",
            tokens_used=20,
            latency_ms=180,
        )

        # 2. Create bundle
        bundle = ReplayBundle.from_recorder(
            trace_id="trace-123",
            tenant_id="tenant-1",
            events=recorder.get_events(),
            original_input={"query": "weather"},
            original_output={"response": "72 degrees"},
            duration_ms=530,
        )

        assert bundle.metadata.llm_call_count == 2
        assert bundle.metadata.tool_call_count == 1

        # 3. Serialize and restore
        serialized = bundle.serialize()
        restored = ReplayBundle.deserialize(serialized)

        assert restored.metadata.trace_id == "trace-123"

        # 4. Replay
        engine = ReplayEngine(restored, mode=ReplayMode.FULL)
        result = await engine.execute_full_replay()

        assert result.status == ReplayStatus.COMPLETED
        assert result.events_replayed == 5

    def test_diff_after_replay(self):
        """Test diffing original vs replay output."""
        original = "The weather in NYC is 72 degrees Fahrenheit."
        replay = "The weather in New York City is 72 degrees."

        diff = ReplayDiff()
        result = diff.compare_text(original, replay)

        assert result.similarity_score > 0.5
        assert result.diff_type in [DiffType.MINOR, DiffType.MODERATE]

    def test_imports(self):
        """Test all components are importable."""
        from app.replay import (
            ReplayRecorder,
            ReplayBundle,
            ReplayDiff,
            ReplayEngine,
        )

        assert ReplayRecorder is not None
        assert ReplayBundle is not None
        assert ReplayDiff is not None
        assert ReplayEngine is not None
