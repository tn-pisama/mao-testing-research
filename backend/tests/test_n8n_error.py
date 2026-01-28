"""
Tests for N8NErrorDetector
==========================

Tests error handling detection in n8n workflows including:
- Hidden failures (continueOnFail=true)
- Invalid data propagation
- High error rates
- Success despite failures
"""

import pytest
from app.detection.n8n.error_detector import N8NErrorDetector
from app.detection.turn_aware._base import TurnSnapshot, TurnAwareSeverity


class TestN8NErrorDetector:
    def test_no_errors_detected(self):
        """Test that workflows without errors pass."""
        detector = N8NErrorDetector()

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Start",
                content="Workflow started successfully",
                turn_metadata={"has_error": False},
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Process",
                content="Data processed successfully",
                turn_metadata={"has_error": False},
            ),
        ]

        metadata = {"workflow_status": "success"}

        result = detector.detect(turns, metadata)
        assert result.detected is False
        assert result.severity == TurnAwareSeverity.NONE

    def test_hidden_failure_detected(self):
        """Test detection of error with continueOnFail=true."""
        detector = N8NErrorDetector()

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="API Call",
                content="Error: HTTP 500 Server Error",
                turn_metadata={
                    "has_error": True,
                    "continue_on_fail": True,
                    "node_type": "n8n-nodes-base.httpRequest",
                },
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Next Node",
                content="Continued processing",
                turn_metadata={"has_error": False},
            ),
        ]

        metadata = {"workflow_status": "success"}

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.severity == TurnAwareSeverity.SEVERE
        assert result.failure_mode == "F14"
        assert "continued execution" in result.explanation.lower()

    def test_invalid_data_propagation(self):
        """Test detection of invalid data flowing to downstream nodes."""
        detector = N8NErrorDetector(check_downstream_data=True)

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Fetch Data",
                content="Error: Failed to fetch",
                turn_metadata={"has_error": True, "continue_on_fail": True},
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Transform",
                content="Received null data, cannot proceed",
                turn_metadata={"has_error": False},
            ),
        ]

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.failure_mode == "F14"
        assert "invalid data" in result.explanation.lower() or "downstream" in result.explanation.lower()

    def test_high_error_rate_detected(self):
        """Test detection of high error rate exceeding threshold."""
        detector = N8NErrorDetector(max_error_rate=0.10)  # 10%

        turns = [
            TurnSnapshot(
                turn_number=i,
                participant_type="node",
                participant_id=f"Node{i}",
                content="Error: Failed" if i % 3 == 0 else "Success",
                turn_metadata={"has_error": i % 3 == 0},
            )
            for i in range(10)  # 4 out of 10 failed = 40%
        ]

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.failure_mode == "F14"
        assert "error rate" in result.explanation.lower()
        assert "40" in result.explanation or "0.4" in result.explanation

    def test_success_despite_failures(self):
        """Test detection of workflow marked successful despite node failures."""
        detector = N8NErrorDetector()

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Node1",
                content="Success",
                turn_metadata={"has_error": False},
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Node2",
                content="Error: Operation failed",
                turn_metadata={"has_error": True},
            ),
            TurnSnapshot(
                turn_number=2,
                participant_type="node",
                participant_id="Node3",
                content="Success",
                turn_metadata={"has_error": False},
            ),
        ]

        metadata = {"workflow_status": "success"}

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.severity == TurnAwareSeverity.SEVERE
        assert result.failure_mode == "F14"
        assert "successful" in result.explanation.lower()

    def test_workflow_failed_status_no_detection(self):
        """Test that workflow marked as failed doesn't trigger success_despite_failures."""
        detector = N8NErrorDetector()

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Node",
                content="Error: Failed",
                turn_metadata={"has_error": True},
            )
        ]

        metadata = {"workflow_status": "failed"}

        result = detector.detect(turns, metadata)
        # Should detect errors but not "success despite failures"
        if result.detected:
            issues = result.evidence.get("issues", [])
            issue_types = [issue["type"] for issue in issues]
            assert "success_despite_failures" not in issue_types

    def test_suggested_fixes_hidden_failure(self):
        """Test that appropriate fixes are suggested for hidden failures."""
        detector = N8NErrorDetector()

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="API",
                content="Error: Failed",
                turn_metadata={"has_error": True, "continue_on_fail": True},
            )
        ]

        metadata = {"workflow_status": "success"}

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.suggested_fix is not None
        assert "continueonfail" in result.suggested_fix.lower().replace("_", "").replace(" ", "")

    def test_suggested_fixes_invalid_data(self):
        """Test that data validation is suggested for invalid data propagation."""
        detector = N8NErrorDetector(check_downstream_data=True)

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Fetch",
                content="Error: Failed",
                turn_metadata={"has_error": True, "continue_on_fail": True},
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Process",
                content="Received null data",
                turn_metadata={},
            ),
        ]

        result = detector.detect(turns, None)
        assert result.detected is True
        assert result.suggested_fix is not None
        assert "validation" in result.suggested_fix.lower()

    def test_multiple_error_issues(self):
        """Test detection when multiple error handling issues present."""
        detector = N8NErrorDetector(max_error_rate=0.10)

        turns = [
            TurnSnapshot(
                turn_number=i,
                participant_type="node",
                participant_id=f"Node{i}",
                content="Error: Failed" if i % 2 == 0 else "Success",
                turn_metadata={
                    "has_error": i % 2 == 0,
                    "continue_on_fail": i % 2 == 0,
                },
            )
            for i in range(10)  # 5 failures with continueOnFail, 50% error rate
        ]

        metadata = {"workflow_status": "success"}

        result = detector.detect(turns, metadata)
        assert result.detected is True
        assert result.severity == TurnAwareSeverity.SEVERE
        # Should detect multiple issues
        assert len(result.evidence.get("issues", [])) >= 2

    def test_skip_downstream_check(self):
        """Test that downstream data check can be disabled."""
        detector = N8NErrorDetector(check_downstream_data=False)

        turns = [
            TurnSnapshot(
                turn_number=0,
                participant_type="node",
                participant_id="Fetch",
                content="Error: Failed",
                turn_metadata={"has_error": True, "continue_on_fail": True},
            ),
            TurnSnapshot(
                turn_number=1,
                participant_type="node",
                participant_id="Process",
                content="Received null data",
                turn_metadata={},
            ),
        ]

        result = detector.detect(turns, None)
        if result.detected:
            issues = result.evidence.get("issues", [])
            issue_types = [issue["type"] for issue in issues]
            assert "invalid_data_propagation" not in issue_types

    def test_empty_turns_list(self):
        """Test handling of empty turns list."""
        detector = N8NErrorDetector()
        result = detector.detect([], None)
        assert result.detected is False
        assert "Need at least 1" in result.explanation
