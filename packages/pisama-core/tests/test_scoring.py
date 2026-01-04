"""Tests for pisama_core.scoring module."""

import pytest

from pisama_core.scoring.engine import ScoringEngine
from pisama_core.scoring.thresholds import Thresholds, SeverityLevel
from pisama_core.detection.result import DetectionResult


class TestThresholds:
    """Tests for Thresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = Thresholds()
        assert thresholds.warning == 40
        assert thresholds.block == 60
        assert thresholds.terminate == 80

    def test_get_level_info(self):
        """Test getting severity level for score."""
        thresholds = Thresholds()

        assert thresholds.get_level(10) == SeverityLevel.INFO
        assert thresholds.get_level(50) == SeverityLevel.WARNING
        assert thresholds.get_level(70) == SeverityLevel.BLOCK
        assert thresholds.get_level(90) == SeverityLevel.TERMINATE

    def test_should_block(self):
        """Test block threshold check."""
        thresholds = Thresholds()
        assert thresholds.should_block(59) is False
        assert thresholds.should_block(60) is True
        assert thresholds.should_block(100) is True

    def test_should_terminate(self):
        """Test terminate threshold check."""
        thresholds = Thresholds()
        assert thresholds.should_terminate(79) is False
        assert thresholds.should_terminate(80) is True


class TestScoringEngine:
    """Tests for ScoringEngine."""

    def test_create_engine(self):
        """Test creating scoring engine."""
        engine = ScoringEngine()
        assert engine.thresholds is not None

    def test_calculate_severity_empty(self):
        """Test severity calculation with no results."""
        engine = ScoringEngine()
        severity = engine.calculate_severity([])
        assert severity == 0

    def test_calculate_severity_single(self):
        """Test severity calculation with single result."""
        engine = ScoringEngine()
        result = DetectionResult.issue_found("test", severity=50, summary="test")
        severity = engine.calculate_severity([result])
        assert severity == 50

    def test_calculate_severity_multiple(self):
        """Test severity calculation with multiple results."""
        engine = ScoringEngine()
        results = [
            DetectionResult.issue_found("test1", severity=40, summary="issue 1"),
            DetectionResult.issue_found("test2", severity=60, summary="issue 2"),
            DetectionResult.no_issue("test3"),
        ]
        severity = engine.calculate_severity(results)
        # Should be max of detected issues
        assert severity == 60

    def test_calculate_severity_only_no_issues(self):
        """Test severity with only no-issue results."""
        engine = ScoringEngine()
        results = [
            DetectionResult.no_issue("test1"),
            DetectionResult.no_issue("test2"),
        ]
        severity = engine.calculate_severity(results)
        assert severity == 0

    def test_get_action_level(self):
        """Test getting action level from severity."""
        engine = ScoringEngine()

        assert engine.get_action_level(30) == SeverityLevel.INFO
        assert engine.get_action_level(50) == SeverityLevel.WARNING
        assert engine.get_action_level(70) == SeverityLevel.BLOCK
        assert engine.get_action_level(90) == SeverityLevel.TERMINATE

    def test_should_block(self):
        """Test should_block check."""
        engine = ScoringEngine()
        results = [
            DetectionResult.issue_found("test", severity=65, summary="test"),
        ]
        assert engine.should_block(results) is True

    def test_should_not_block(self):
        """Test should_block returns False for low severity."""
        engine = ScoringEngine()
        results = [
            DetectionResult.issue_found("test", severity=40, summary="test"),
        ]
        assert engine.should_block(results) is False
