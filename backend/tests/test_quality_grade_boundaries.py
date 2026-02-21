"""Test health tier boundary thresholds for quality assessment."""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality.models import _score_to_grade


class TestTierBoundaries:
    """Test that tier boundaries are at exact thresholds."""

    def test_score_1_00_is_healthy(self):
        """Perfect score should be Healthy."""
        assert _score_to_grade(1.0) == "Healthy"

    def test_score_0_90_exact_is_healthy(self):
        """Score of exactly 0.90 should be Healthy."""
        assert _score_to_grade(0.90) == "Healthy"

    def test_score_0_899_is_good(self):
        """Score just below 0.90 should be Good."""
        assert _score_to_grade(0.899) == "Good"

    def test_score_0_80_exact_is_good(self):
        """Score of exactly 0.80 should be Good."""
        assert _score_to_grade(0.80) == "Good"

    def test_score_0_799_is_needs_attention(self):
        """Score just below 0.80 should be Needs Attention."""
        assert _score_to_grade(0.799) == "Needs Attention"

    def test_score_0_70_exact_is_needs_attention(self):
        """Score of exactly 0.70 should be Needs Attention."""
        assert _score_to_grade(0.70) == "Needs Attention"

    def test_score_0_699_is_at_risk(self):
        """Score just below 0.70 should be At Risk."""
        assert _score_to_grade(0.699) == "At Risk"

    def test_score_0_60_exact_is_at_risk(self):
        """Score of exactly 0.60 should be At Risk."""
        assert _score_to_grade(0.60) == "At Risk"

    def test_score_0_50_exact_is_at_risk(self):
        """Score of exactly 0.50 should be At Risk."""
        assert _score_to_grade(0.50) == "At Risk"

    def test_score_0_499_is_critical(self):
        """Score just below 0.50 should be Critical."""
        assert _score_to_grade(0.499) == "Critical"

    def test_score_0_40_exact_is_critical(self):
        """Score of exactly 0.40 should be Critical."""
        assert _score_to_grade(0.40) == "Critical"

    def test_score_0_00_is_critical(self):
        """Score of 0.0 should be Critical."""
        assert _score_to_grade(0.0) == "Critical"


class TestTierBoundaryEdgeCases:
    """Test edge cases near tier boundaries."""

    def test_score_0_9001_is_healthy(self):
        """Score just above 0.90 should still be Healthy."""
        assert _score_to_grade(0.9001) == "Healthy"

    def test_score_0_8999_is_good(self):
        """Score very close to but below 0.90 should be Good."""
        assert _score_to_grade(0.8999) == "Good"

    def test_score_0_8001_is_good(self):
        """Score just above 0.80 should be Good."""
        assert _score_to_grade(0.8001) == "Good"

    def test_score_0_7999_is_needs_attention(self):
        """Score very close to but below 0.80 should be Needs Attention."""
        assert _score_to_grade(0.7999) == "Needs Attention"

    def test_score_0_7001_is_needs_attention(self):
        """Score just above 0.70 should be Needs Attention."""
        assert _score_to_grade(0.7001) == "Needs Attention"

    def test_score_0_6999_is_at_risk(self):
        """Score very close to but below 0.70 should be At Risk."""
        assert _score_to_grade(0.6999) == "At Risk"

    def test_score_0_5001_is_at_risk(self):
        """Score just above 0.50 should be At Risk."""
        assert _score_to_grade(0.5001) == "At Risk"

    def test_score_0_4999_is_critical(self):
        """Score very close to but below 0.50 should be Critical."""
        assert _score_to_grade(0.4999) == "Critical"

    def test_score_0_4001_is_critical(self):
        """Score just above 0.40 should be Critical."""
        assert _score_to_grade(0.4001) == "Critical"

    def test_score_0_3999_is_critical(self):
        """Score very close to but below 0.40 should be Critical."""
        assert _score_to_grade(0.3999) == "Critical"


class TestProvisionalGrade:
    """Test provisional grade override behavior."""

    def test_provisional_good_becomes_needs_data(self):
        """Good score with provisional flag should show Needs Data."""
        assert _score_to_grade(0.85, is_provisional=True) == "Needs Data"

    def test_provisional_needs_attention_becomes_needs_data(self):
        """Needs Attention score with provisional flag should show Needs Data."""
        assert _score_to_grade(0.75, is_provisional=True) == "Needs Data"

    def test_provisional_healthy_stays_healthy(self):
        """Healthy score is not overridden by provisional flag."""
        assert _score_to_grade(0.95, is_provisional=True) == "Healthy"

    def test_provisional_at_risk_stays_at_risk(self):
        """At Risk score is not overridden by provisional flag."""
        assert _score_to_grade(0.55, is_provisional=True) == "At Risk"

    def test_provisional_critical_stays_critical(self):
        """Critical score is not overridden by provisional flag."""
        assert _score_to_grade(0.3, is_provisional=True) == "Critical"

    def test_non_provisional_good_stays_good(self):
        """Good score without provisional flag stays Good."""
        assert _score_to_grade(0.85, is_provisional=False) == "Good"
