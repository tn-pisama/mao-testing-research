"""Test grade boundary thresholds for quality assessment."""

import pytest
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.enterprise.quality.models import _score_to_grade


class TestGradeBoundaries:
    """Test that grade boundaries are at exact thresholds."""

    def test_score_1_00_is_grade_a(self):
        """Perfect score should be grade A."""
        assert _score_to_grade(1.0) == "A"

    def test_score_0_90_exact_is_grade_a(self):
        """Score of exactly 0.90 should be grade A."""
        assert _score_to_grade(0.90) == "A"

    def test_score_0_899_is_grade_b_plus(self):
        """Score just below 0.90 should be grade B+."""
        assert _score_to_grade(0.899) == "B+"

    def test_score_0_80_exact_is_grade_b_plus(self):
        """Score of exactly 0.80 should be grade B+."""
        assert _score_to_grade(0.80) == "B+"

    def test_score_0_799_is_grade_b(self):
        """Score just below 0.80 should be grade B."""
        assert _score_to_grade(0.799) == "B"

    def test_score_0_70_exact_is_grade_b(self):
        """Score of exactly 0.70 should be grade B."""
        assert _score_to_grade(0.70) == "B"

    def test_score_0_699_is_grade_c_plus(self):
        """Score just below 0.70 should be grade C+."""
        assert _score_to_grade(0.699) == "C+"

    def test_score_0_60_exact_is_grade_c_plus(self):
        """Score of exactly 0.60 should be grade C+."""
        assert _score_to_grade(0.60) == "C+"

    def test_score_0_599_is_grade_c(self):
        """Score just below 0.60 should be grade C."""
        assert _score_to_grade(0.599) == "C"

    def test_score_0_50_exact_is_grade_c(self):
        """Score of exactly 0.50 should be grade C."""
        assert _score_to_grade(0.50) == "C"

    def test_score_0_499_is_grade_d(self):
        """Score just below 0.50 should be grade D."""
        assert _score_to_grade(0.499) == "D"

    def test_score_0_40_exact_is_grade_d(self):
        """Score of exactly 0.40 should be grade D."""
        assert _score_to_grade(0.40) == "D"

    def test_score_0_399_is_grade_f(self):
        """Score just below 0.40 should be grade F."""
        assert _score_to_grade(0.399) == "F"

    def test_score_0_00_is_grade_f(self):
        """Score of 0.0 should be grade F."""
        assert _score_to_grade(0.0) == "F"


class TestGradeBoundaryEdgeCases:
    """Test edge cases near grade boundaries."""

    def test_score_0_9001_is_grade_a(self):
        """Score just above 0.90 should still be A."""
        assert _score_to_grade(0.9001) == "A"

    def test_score_0_8999_is_grade_b_plus(self):
        """Score very close to but below 0.90 should be B+."""
        assert _score_to_grade(0.8999) == "B+"

    def test_score_0_7001_is_grade_b(self):
        """Score just above 0.70 should be B."""
        assert _score_to_grade(0.7001) == "B"

    def test_score_0_6999_is_grade_c_plus(self):
        """Score very close to but below 0.70 should be C+."""
        assert _score_to_grade(0.6999) == "C+"

    def test_score_0_5001_is_grade_c(self):
        """Score just above 0.50 should be C."""
        assert _score_to_grade(0.5001) == "C"

    def test_score_0_4999_is_grade_d(self):
        """Score very close to but below 0.50 should be D."""
        assert _score_to_grade(0.4999) == "D"

    def test_score_0_4001_is_grade_d(self):
        """Score just above 0.40 should be D."""
        assert _score_to_grade(0.4001) == "D"

    def test_score_0_3999_is_grade_f(self):
        """Score very close to but below 0.40 should be F."""
        assert _score_to_grade(0.3999) == "F"
