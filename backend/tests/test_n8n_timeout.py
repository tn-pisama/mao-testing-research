"""
Tests for N8NTimeoutDetector
============================

Tests timeout detection in n8n workflows including:
- Workflow duration timeouts
- Webhook response timeouts
- Individual node timeouts
- Stalled execution detection
"""

import pytest
from datetime import datetime, timedelta
from app.detection.n8n.timeout_detector import N8NTimeoutDetector
from app.detection.turn_aware._base import TurnSnapshot, TurnAwareSeverity


class TestN8NTimeoutDetector:
    def test_no_timeout_detected(self):
        """Test that normal execution doesn't trigger timeout."""
        detector = N8NTimeoutDetector(
            max_workflow_duration_ms=300_000,  # 5 min
            max_webhook_wait_ms=30_000,  # 30s
        )

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Start",
                content="Workflow started",
                turn_metadata={
                    "timestamp": datetime.now().isoformat(),
                    "execution_time_ms": 100,
                    "node_type": "n8n-nodes-base.webhook",
                },
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Process",
                content="Processing data",
                turn_metadata={
                    "timestamp": (datetime.now() + timedelta(seconds=1)).isoformat(),
                    "execution_time_ms": 500,
                    "node_type": "n8n-nodes-base.function",
                },
            ),
        ]

        metadata = {"workflow_duration_ms": 5_000}  # 5 seconds

        result = detector.detect(turns, metadata)
        assert result.detected is False
        assert result.severity == TurnAwareSeverity.NONE

    def test_workflow_timeout_detected(self):
        """Test detection of workflow exceeding duration threshold."""
        detector = N8NTimeoutDetector(max_workflow_duration_ms=60_000)  # 1 min

        turns = [
            TurnSnapshot(
                turn_number=i,
                participant_type="node",
                participant_id=f"Node{i}",
                content=f"Processing step {i}",
                turn_metadata={"execution_time_ms": 1000},
            )
            for i in range(10)
        ]

        metadata = {"workflow_duration_ms": 400_000}  # 6.67 minutes

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.severity == TurnAwareSeverity.SEVERE
        assert result.failure_mode == "F13"
        assert "400000" in str(result.evidence) or "400.0" in result.explanation

    def test_webhook_timeout_detected(self):
        """Test detection of webhook execution exceeding 30s."""
        detector = N8NTimeoutDetector(max_webhook_wait_ms=30_000)

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Webhook",
                content="Webhook triggered",
                turn_metadata={"node_type": "n8n-nodes-base.webhook"},
            )
        ]

        metadata = {
            "workflow_mode": "webhook",
            "workflow_duration_ms": 45_000,  # 45 seconds
        }

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.severity == TurnAwareSeverity.SEVERE
        assert result.failure_mode == "F13"
        assert "webhook" in result.explanation.lower()

    def test_node_timeout_detected(self):
        """Test detection of individual node exceeding its threshold."""
        detector = N8NTimeoutDetector()

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="HTTP Request",
                content="Fetching data",
                turn_metadata={
                    "execution_time_ms": 45_000,  # 45 seconds
                    "node_type": "n8n-nodes-base.httpRequest",
                },
            ),
        ]

        metadata = {"workflow_duration_ms": 50_000}

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.severity == TurnAwareSeverity.MODERATE
        assert result.failure_mode == "F13"
        assert "node(s) exceeded" in result.explanation

    def test_stalled_execution_detected(self):
        """Test detection of stalled workflow with large gaps."""
        detector = N8NTimeoutDetector(stall_threshold_ms=60_000)

        base_time = datetime.now()
        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Start",
                content="Started",
                turn_metadata={"timestamp": base_time.isoformat()},
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Stalled",
                content="Waiting...",
                turn_metadata={
                    "timestamp": (base_time + timedelta(seconds=120)).isoformat()
                },  # 2 min gap
            ),
        ]

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.failure_mode == "F13"
        assert "stall" in result.explanation.lower()

    def test_suggested_fixes_workflow_timeout(self):
        """Test that appropriate fixes are suggested for workflow timeout."""
        detector = N8NTimeoutDetector(max_workflow_duration_ms=10_000)

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Node",
                content="Data",
                turn_metadata={},
            )
        ]

        metadata = {"workflow_duration_ms": 350_000}

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.suggested_fix is not None
        assert "workflow" in result.suggested_fix.lower()

    def test_suggested_fixes_webhook_timeout(self):
        """Test that async pattern is suggested for webhook timeout."""
        detector = N8NTimeoutDetector(max_webhook_wait_ms=20_000)

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Webhook",
                content="Start",
                turn_metadata={},
            )
        ]

        metadata = {"workflow_mode": "webhook", "workflow_duration_ms": 35_000}

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.suggested_fix is not None
        assert "async" in result.suggested_fix.lower() or "callback" in result.suggested_fix.lower()

    def test_multiple_timeout_issues(self):
        """Test detection when multiple timeout issues present."""
        detector = N8NTimeoutDetector(
            max_workflow_duration_ms=60_000, max_webhook_wait_ms=30_000
        )

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Webhook",
                content="Start",
                turn_metadata={
                    "node_type": "n8n-nodes-base.webhook",
                    "execution_time_ms": 100,
                },
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Slow API",
                content="Fetching",
                turn_metadata={
                    "node_type": "n8n-nodes-base.httpRequest",
                    "execution_time_ms": 90_000,  # 90 seconds - exceeds threshold
                },
            ),
        ]

        metadata = {
            "workflow_mode": "webhook",
            "workflow_duration_ms": 95_000,  # Both workflow and webhook timeout
        }

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.severity == TurnAwareSeverity.SEVERE
        # Should detect multiple issues
        assert len(result.evidence.get("issues", [])) >= 2

    def test_empty_turns_list(self):
        """Test handling of empty turns list."""
        detector = N8NTimeoutDetector()
        result = detector.detect([], None)
        assert result.detected is False
        assert "Need at least 1" in result.explanation
