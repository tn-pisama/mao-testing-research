"""Tests for pisama_core.injection module."""

import pytest

from pisama_core.injection.enforcement import EnforcementLevel, EnforcementEngine
from pisama_core.injection.protocol import FixInjectionProtocol


class TestEnforcementLevel:
    """Tests for EnforcementLevel enum."""

    def test_enforcement_levels(self):
        """Test enforcement level values."""
        assert EnforcementLevel.SUGGEST.value == 1
        assert EnforcementLevel.DIRECT.value == 2
        assert EnforcementLevel.BLOCK.value == 3
        assert EnforcementLevel.TERMINATE.value == 4

    def test_level_comparison(self):
        """Test level comparison."""
        assert EnforcementLevel.SUGGEST < EnforcementLevel.DIRECT
        assert EnforcementLevel.BLOCK > EnforcementLevel.DIRECT
        assert EnforcementLevel.TERMINATE > EnforcementLevel.BLOCK


class TestEnforcementEngine:
    """Tests for EnforcementEngine."""

    def test_create_engine(self):
        """Test creating enforcement engine."""
        engine = EnforcementEngine()
        assert engine is not None

    def test_get_level_low_severity(self):
        """Test getting level for low severity."""
        engine = EnforcementEngine()
        level = engine.get_level(30, "session-1")
        assert level == EnforcementLevel.SUGGEST

    def test_get_level_medium_severity(self):
        """Test getting level for medium severity."""
        engine = EnforcementEngine()
        level = engine.get_level(50, "session-1")
        assert level == EnforcementLevel.DIRECT

    def test_get_level_high_severity(self):
        """Test getting level for high severity."""
        engine = EnforcementEngine()
        level = engine.get_level(70, "session-1")
        assert level == EnforcementLevel.BLOCK

    def test_get_level_critical_severity(self):
        """Test getting level for critical severity."""
        engine = EnforcementEngine()
        level = engine.get_level(90, "session-1")
        assert level == EnforcementLevel.TERMINATE

    def test_should_block(self):
        """Test should_block check."""
        engine = EnforcementEngine()
        assert engine.should_block(EnforcementLevel.SUGGEST) is False
        assert engine.should_block(EnforcementLevel.DIRECT) is False
        assert engine.should_block(EnforcementLevel.BLOCK) is True
        assert engine.should_block(EnforcementLevel.TERMINATE) is True


class TestFixInjectionProtocol:
    """Tests for FixInjectionProtocol."""

    def test_create_protocol(self):
        """Test creating injection protocol."""
        protocol = FixInjectionProtocol()
        assert protocol is not None

    def test_format_directive_suggest(self):
        """Test formatting suggestion directive."""
        protocol = FixInjectionProtocol()
        formatted = protocol.format_directive(
            directive="Consider trying a different approach",
            level=EnforcementLevel.SUGGEST,
            severity=30,
        )
        assert "Consider" in formatted
        assert "PISAMA" in formatted or "pisama" in formatted.lower()

    def test_format_directive_block(self):
        """Test formatting block directive."""
        protocol = FixInjectionProtocol()
        formatted = protocol.format_directive(
            directive="Stop the loop immediately",
            level=EnforcementLevel.BLOCK,
            severity=70,
        )
        assert "Stop" in formatted
        assert "70" in formatted or "severity" in formatted.lower()

    def test_format_alert(self):
        """Test formatting alert message."""
        protocol = FixInjectionProtocol()
        alert = protocol.format_alert(
            issues=["Loop detected: Read repeated 5 times"],
            severity=65,
            recommendation="break_loop",
        )
        assert "Loop detected" in alert
        assert "65" in alert

    def test_format_alert_multiple_issues(self):
        """Test formatting alert with multiple issues."""
        protocol = FixInjectionProtocol()
        alert = protocol.format_alert(
            issues=[
                "Loop detected",
                "High cost detected",
                "Coordination failure",
            ],
            severity=75,
            recommendation="escalate",
        )
        assert "Loop" in alert
        assert "cost" in alert.lower() or "High" in alert

    def test_create_intervention_message(self):
        """Test creating intervention message for skill."""
        protocol = FixInjectionProtocol()
        message = protocol.create_intervention_message(
            session_id="session-1",
            severity=60,
            issues=["Test issue"],
            recommendation="break_loop",
        )
        assert "session-1" in message or "session" in message.lower()
