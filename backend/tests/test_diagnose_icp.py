"""Tests for ICP-tier Agent Forensics diagnose endpoint.

Tests the /api/v1/diagnose/why-failed endpoint and supporting functions
without requiring enterprise features.
"""

import json
import pytest
from datetime import datetime

from app.ingestion.universal_trace import UniversalSpan, UniversalTrace, SpanType, SpanStatus
from app.ingestion.importers import import_trace, detect_format
from app.api.v1.diagnose import (
    _spans_to_turn_snapshots,
    _run_turn_aware_detectors,
    _build_error_detections,
    _pick_primary,
    _generate_root_cause,
)


# ---------------------------------------------------------------------------
# Test data factories
# ---------------------------------------------------------------------------

def _make_trace_json(spans: list[dict]) -> str:
    """Create a JSON string from a list of span dicts."""
    return json.dumps(spans)


def _healthy_trace() -> str:
    """A trace with no issues - simple agent step."""
    return _make_trace_json([
        {
            "id": "s1",
            "name": "agent.step",
            "type": "agent",
            "agent_id": "planner",
            "input": "What is the capital of France?",
            "output": "The capital of France is Paris.",
        },
        {
            "id": "s2",
            "name": "tool.call",
            "type": "tool",
            "tool_name": "lookup",
            "tool_args": {"query": "capital of France"},
            "result": "Paris",
        },
    ])


def _error_trace() -> str:
    """A trace with explicit errors."""
    return _make_trace_json([
        {
            "id": "s1",
            "name": "tool.call",
            "type": "tool",
            "tool_name": "database_query",
            "tool_args": {"sql": "SELECT * FROM users"},
            "status": "error",
            "error": "Connection refused: database unavailable",
            "error_type": "ConnectionError",
        },
        {
            "id": "s2",
            "name": "agent.step",
            "type": "agent",
            "agent_id": "executor",
            "input": "Fetch user data",
            "output": "Failed to fetch user data due to database error",
            "status": "error",
            "error": "Upstream dependency failed",
        },
    ])


def _looping_trace() -> str:
    """A trace exhibiting loop behavior."""
    spans = []
    for i in range(8):
        spans.append({
            "id": f"s{i}",
            "name": "tool.call",
            "type": "tool",
            "tool_name": "search",
            "agent_id": "agent1",
            "tool_args": {"query": "find answer"},
            "result": "No results found",
        })
    return _make_trace_json(spans)


def _multi_agent_conflict_trace() -> str:
    """A trace with communication breakdown between agents."""
    return _make_trace_json([
        {
            "id": "s1",
            "name": "agent.step",
            "type": "agent",
            "agent_id": "user1",
            "output": "Please create update delete and generate the authentication system with OAuth and JWT infrastructure deployment pipeline",
        },
        {
            "id": "s2",
            "name": "agent.step",
            "type": "agent",
            "agent_id": "agent1",
            "output": "Here is a poem about butterflies and sunshine in the meadow on a beautiful spring day",
        },
    ])


# ---------------------------------------------------------------------------
# UniversalTrace conversion tests
# ---------------------------------------------------------------------------

class TestSpanToTurnConversion:
    """Test conversion of UniversalTrace spans to TurnSnapshots."""

    def test_tool_spans_become_tool_participants(self):
        content = _healthy_trace()
        trace = import_trace(content, "raw")
        snapshots = _spans_to_turn_snapshots(trace)

        tool_turns = [s for s in snapshots if s.participant_type == "tool"]
        assert len(tool_turns) >= 1

    def test_agent_spans_become_agent_participants(self):
        content = _healthy_trace()
        trace = import_trace(content, "raw")
        snapshots = _spans_to_turn_snapshots(trace)

        agent_turns = [s for s in snapshots if s.participant_type == "agent"]
        assert len(agent_turns) >= 1

    def test_sequential_turn_numbers(self):
        content = _looping_trace()
        trace = import_trace(content, "raw")
        snapshots = _spans_to_turn_snapshots(trace)

        turn_numbers = [s.turn_number for s in snapshots]
        assert turn_numbers == list(range(len(snapshots)))

    def test_empty_trace_returns_empty(self):
        trace = UniversalTrace(trace_id="empty", spans=[])
        snapshots = _spans_to_turn_snapshots(trace)
        assert snapshots == []


# ---------------------------------------------------------------------------
# Error detection tests
# ---------------------------------------------------------------------------

class TestErrorDetection:
    """Test explicit error detection from spans."""

    def test_detect_errors_in_trace(self):
        content = _error_trace()
        trace = import_trace(content, "raw")
        results = _build_error_detections(trace)

        assert len(results) == 1
        assert results[0]["category"] == "error"
        assert results[0]["detected"] is True
        assert results[0]["confidence"] >= 0.9

    def test_no_errors_in_healthy_trace(self):
        content = _healthy_trace()
        trace = import_trace(content, "raw")
        results = _build_error_detections(trace)

        assert len(results) == 0


# ---------------------------------------------------------------------------
# Turn-aware detection tests
# ---------------------------------------------------------------------------

class TestTurnAwareDetection:
    """Test turn-aware detectors via the diagnose pipeline."""

    def test_healthy_trace_no_detections(self):
        content = _healthy_trace()
        trace = import_trace(content, "raw")
        results = _run_turn_aware_detectors(trace)

        # A simple 2-span healthy trace should have very few or no detections
        # (may have minor ones depending on thresholds)
        severe = [r for r in results if r["severity"] == "severe"]
        assert len(severe) == 0

    def test_single_span_returns_empty(self):
        content = json.dumps([{"id": "s1", "name": "step", "type": "agent", "output": "done"}])
        trace = import_trace(content, "raw")
        results = _run_turn_aware_detectors(trace)
        assert results == []


# ---------------------------------------------------------------------------
# Result ranking tests
# ---------------------------------------------------------------------------

class TestResultRanking:
    """Test primary failure selection and root cause generation."""

    def test_pick_primary_by_severity(self):
        detections = [
            {"severity": "minor", "confidence": 0.9, "title": "Minor Issue"},
            {"severity": "severe", "confidence": 0.7, "title": "Critical Issue"},
            {"severity": "moderate", "confidence": 0.8, "title": "Medium Issue"},
        ]
        primary = _pick_primary(detections)
        assert primary["title"] == "Critical Issue"

    def test_pick_primary_by_confidence_when_same_severity(self):
        detections = [
            {"severity": "moderate", "confidence": 0.6, "title": "Issue A"},
            {"severity": "moderate", "confidence": 0.9, "title": "Issue B"},
        ]
        primary = _pick_primary(detections)
        assert primary["title"] == "Issue B"

    def test_pick_primary_empty(self):
        assert _pick_primary([]) is None

    def test_generate_root_cause(self):
        primary = {
            "title": "Loop Detected",
            "description": "Agent repeats same action",
            "suggested_fix": "Add exit condition",
        }
        explanation = _generate_root_cause(primary, [primary])
        assert "Loop Detected" in explanation
        assert "exit condition" in explanation

    def test_generate_root_cause_multiple_issues(self):
        primary = {
            "title": "Error",
            "description": "Connection failed",
            "suggested_fix": "Check network",
        }
        other = {
            "title": "Context Overflow",
            "description": "Too many tokens",
            "suggested_fix": None,
        }
        explanation = _generate_root_cause(primary, [primary, other])
        assert "Error" in explanation
        assert "Context Overflow" in explanation

    def test_generate_root_cause_none(self):
        assert _generate_root_cause(None, []) is None


# ---------------------------------------------------------------------------
# Format detection tests
# ---------------------------------------------------------------------------

class TestFormatDetection:
    """Test auto-format detection for trace content."""

    def test_detect_raw_json(self):
        content = json.dumps([{"id": "1", "name": "test"}])
        fmt = detect_format(content)
        assert fmt == "generic"

    def test_detect_otel_format(self):
        content = json.dumps({"resourceSpans": [{"scopeSpans": []}]})
        fmt = detect_format(content)
        assert fmt == "otel"

    def test_detect_langsmith_format(self):
        content = json.dumps([{"run_type": "llm", "name": "ChatModel"}])
        fmt = detect_format(content)
        assert fmt == "langsmith"


# ---------------------------------------------------------------------------
# End-to-end import + detect pipeline
# ---------------------------------------------------------------------------

class TestDiagnosePipeline:
    """Test the full diagnose pipeline: import → detect → rank."""

    def test_error_trace_pipeline(self):
        """Error trace should detect errors as primary failure."""
        content = _error_trace()
        trace = import_trace(content, "raw")

        all_detections = []
        all_detections.extend(_build_error_detections(trace))
        all_detections.extend(_run_turn_aware_detectors(trace))

        assert len(all_detections) >= 1
        primary = _pick_primary(all_detections)
        assert primary is not None
        # Errors should be high confidence
        assert primary["confidence"] >= 0.7

    def test_healthy_trace_pipeline(self):
        """Healthy trace should have no severe issues."""
        content = _healthy_trace()
        trace = import_trace(content, "raw")

        all_detections = []
        all_detections.extend(_build_error_detections(trace))
        all_detections.extend(_run_turn_aware_detectors(trace))

        severe = [d for d in all_detections if d["severity"] == "severe"]
        assert len(severe) == 0

    def test_import_jsonl_trace(self):
        """Test JSONL (newline-delimited) import."""
        lines = [
            json.dumps({"id": "1", "name": "step1", "type": "agent", "output": "Planning..."}),
            json.dumps({"id": "2", "name": "step2", "type": "tool", "tool_name": "search", "result": "Found it"}),
        ]
        content = "\n".join(lines)
        trace = import_trace(content, "raw")
        assert len(trace.spans) == 2
