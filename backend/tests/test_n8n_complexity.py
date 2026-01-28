"""
Tests for N8NComplexityDetector
===============================

Tests complexity detection in n8n workflows including:
- Excessive node count
- Deep branching
- High cyclomatic complexity
- Long execution times
- Multiple concerns in single workflow
"""

import pytest
from datetime import datetime, timedelta
from app.detection.n8n.complexity_detector import N8NComplexityDetector
from app.detection.turn_aware._base import TurnSnapshot, TurnAwareSeverity


class TestN8NComplexityDetector:
    def test_no_complexity_issues(self):
        """Test that simple workflows don't trigger complexity detection."""
        detector = N8NComplexityDetector()

        turns = [
            TurnSnapshot(
                turn_number=i,
                participant_type="node",
                participant_id=f"Node{i}",
                content=f"Processing step {i}",
                turn_metadata={"node_type": "n8n-nodes-base.function"},
            )
            for i in range(5)  # Only 5 nodes
        ]

        metadata = {"workflow_duration_ms": 10_000}  # 10 seconds

        result = detector.detect(turns, metadata)
        assert result.detected is False
        assert result.severity == TurnAwareSeverity.NONE

    def test_excessive_nodes_detected(self):
        """Test detection of workflow with too many nodes."""
        detector = N8NComplexityDetector(max_node_count=50)

        turns = [
            TurnSnapshot(
                turn_number=i,
                participant_type="node",
                participant_id=f"Node{i}",
                content=f"Step {i}",
                turn_metadata={"node_type": "n8n-nodes-base.function"},
            )
            for i in range(75)  # 75 nodes exceeds threshold
        ]

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.severity in [TurnAwareSeverity.MODERATE, TurnAwareSeverity.SEVERE]
        assert result.failure_mode == "F15"
        assert "75" in result.explanation

    def test_deep_branching_detected(self):
        """Test detection of deeply nested branches."""
        detector = N8NComplexityDetector(max_branch_depth=3)

        # Create deeply nested IF statements
        turns = []
        for i in range(6):  # 6 nested IFs
            turns.append(
                TurnSnapshot(
                    turn_number=i * 2,
                    participant_type="node",
                    participant_id=f"IF{i}",
                    content=f"Condition {i}",
                    turn_metadata={"node_type": "n8n-nodes-base.if"},
                )
            )
            turns.append(
                TurnSnapshot(
                    turn_number=i * 2 + 1,
                    participant_type="node",
                    participant_id=f"Action{i}",
                    content=f"Action {i}",
                    turn_metadata={"node_type": "n8n-nodes-base.function"},
                )
            )

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.failure_mode == "F15"
        assert "branch" in result.explanation.lower()

    def test_high_cyclomatic_complexity(self):
        """Test detection of high cyclomatic complexity."""
        detector = N8NComplexityDetector(max_cyclomatic_complexity=5)

        # Create workflow with many branches
        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Start",
                content="Start",
                turn_metadata={"node_type": "n8n-nodes-base.webhook"},
            )
        ]

        # Add 10 IF nodes (each adds 1 to complexity)
        for i in range(10):
            turns.append(
                TurnSnapshot(
                    turn_number=i + 1,
                    participant_type="node",
                    participant_id=f"IF{i}",
                    content=f"Condition {i}",
                    turn_metadata={"node_type": "n8n-nodes-base.if"},
                )
            )

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.failure_mode == "F15"
        assert "complexity" in result.explanation.lower()

    def test_long_execution_time(self):
        """Test detection of consistently long execution times."""
        detector = N8NComplexityDetector(max_execution_time_ms=60_000)  # 1 min

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
                participant_id="End",
                content="Completed",
                turn_metadata={
                    "timestamp": (base_time + timedelta(minutes=10)).isoformat()
                },
            ),
        ]

        metadata = {"workflow_duration_ms": 600_000}  # 10 minutes

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.failure_mode == "F15"
        assert "600" in result.explanation or "600.0" in result.explanation

    def test_multiple_concerns_detected(self):
        """Test detection of workflow handling multiple unrelated concerns."""
        detector = N8NComplexityDetector()

        # Create workflow with 4+ different functional categories
        turns = [
            # Data fetch
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="API Call",
                content="Fetch data",
                turn_metadata={"node_type": "n8n-nodes-base.httpRequest"},
            ),
            # Transform
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Transform",
                content="Process",
                turn_metadata={"node_type": "n8n-nodes-base.function"},
            ),
            # Validation
            TurnSnapshot(
                turn_number=2,
                participant_type="node",
                participant_id="Validate",
                content="Check",
                turn_metadata={"node_type": "n8n-nodes-base.if"},
            ),
            # Notification
            TurnSnapshot(
                turn_number=3,
                participant_type="node",
                participant_id="Notify",
                content="Send email",
                turn_metadata={"node_type": "n8n-nodes-base.emailSend"},
            ),
            # AI processing
            TurnSnapshot(
                turn_number=4,
                participant_type="node",
                participant_id="AI",
                content="Analyze",
                turn_metadata={"node_type": "n8n-nodes-base.openAi"},
            ),
        ]

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.failure_mode == "F15"
        assert "concerns" in result.explanation.lower() or "categories" in result.explanation.lower()

    def test_suggested_fixes_excessive_nodes(self):
        """Test that sub-workflow split is suggested for excessive nodes."""
        detector = N8NComplexityDetector(max_node_count=10)

        turns = [
            TurnSnapshot(
                turn_number=i,
                participant_type="node",
                participant_id=f"Node{i}",
                content=f"Step {i}",
                turn_metadata={},
            )
            for i in range(20)
        ]

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.suggested_fix is not None
        assert "sub-workflow" in result.suggested_fix.lower() or "split" in result.suggested_fix.lower()

    def test_suggested_fixes_deep_branching(self):
        """Test that branching simplification is suggested."""
        detector = N8NComplexityDetector(max_branch_depth=2)

        turns = []
        for i in range(5):  # 5 nested IFs
            turns.append(
                TurnSnapshot(
                    turn_number=i,
                    participant_type="node",
                    participant_id=f"IF{i}",
                    content=f"Condition {i}",
                    turn_metadata={"node_type": "n8n-nodes-base.if"},
                )
            )

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.suggested_fix is not None
        assert "switch" in result.suggested_fix.lower() or "branching" in result.suggested_fix.lower()

    def test_multiple_complexity_issues_severe(self):
        """Test that multiple complexity indicators increase severity."""
        detector = N8NComplexityDetector(
            max_node_count=10, max_branch_depth=3, max_cyclomatic_complexity=5
        )

        # Create workflow with multiple issues
        turns = []
        # Many nodes
        for i in range(25):
            # Add branching nodes to increase complexity
            node_type = (
                "n8n-nodes-base.if"
                if i % 3 == 0
                else "n8n-nodes-base.function"
            )
            turns.append(
                TurnSnapshot(
                    turn_number=i,
                    participant_type="node",
                    participant_id=f"Node{i}",
                    content=f"Step {i}",
                    turn_metadata={"node_type": node_type},
                )
            )

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.severity == TurnAwareSeverity.SEVERE
        # Should detect multiple issues
        assert len(result.evidence.get("issues", [])) >= 2

    def test_switch_node_cyclomatic_complexity(self):
        """Test that switch nodes with multiple cases increase complexity."""
        detector = N8NComplexityDetector(max_cyclomatic_complexity=5)

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Start",
                content="Start",
                turn_metadata={"node_type": "n8n-nodes-base.webhook"},
            ),
            # Switch with 5 cases adds more to complexity than simple IF
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Route",
                content="Route based on type",
                turn_metadata={
                    "node_type": "n8n-nodes-base.switch",
                    "switch_cases": 5,
                },
            ),
        ]

        result = detector.detect(turns, None)
        # With 5 switch cases, complexity should be high enough to trigger
        # Base = 1, Switch adds 1 + (5-2) = 4, total = 5, at threshold
        assert result.detected is False or result.confidence < 0.9

        # Add more branching to push over threshold
        turns.append(
            TurnSnapshot(
                turn_number=2,
                participant_type="node",
                participant_id="Check",
                content="Validate",
                turn_metadata={"node_type": "n8n-nodes-base.if"},
            )
        )

        result = detector.detect(turns, None)
        assert result.detected is True

    def test_minimum_turns_requirement(self):
        """Test that at least 2 nodes are required."""
        detector = N8NComplexityDetector()
        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Node",
                content="Single node",
                turn_metadata={},
            )
        ]
        result = detector.detect(turns, None)
        assert result.detected is False
        assert "at least 2" in result.explanation.lower()

    def test_empty_turns_list(self):
        """Test handling of empty turns list."""
        detector = N8NComplexityDetector()
        result = detector.detect([], None)
        assert result.detected is False
        assert "at least 2" in result.explanation.lower()
