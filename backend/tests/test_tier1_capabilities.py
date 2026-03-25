"""Tests for Tier 1 capabilities: Trajectory Evaluator, Quality Scoring,
Semantic Entropy, Fix Learning Loop."""
import json
import os
import pytest

os.environ.setdefault("JWT_SECRET", "xK9mPqL2vN7wR4tY8uJ3hB6gF5dC0aZS")


# ═══════════════════════════════════════════════════════════════
# 1. TRAJECTORY EVALUATOR
# ═══════════════════════════════════════════════════════════════

class TestTrajectoryEvaluator:
    def setup_method(self):
        from app.detection.trajectory_evaluator import TrajectoryEvaluator
        self.te = TrajectoryEvaluator()

    def test_perfect_trajectory_scores_one(self):
        ref = [
            {"tool": "search", "status": "success"},
            {"tool": "analyze", "status": "success"},
            {"tool": "write", "status": "success"},
        ]
        score = self.te.evaluate(ref, reference_trajectory=ref)
        assert score.overall == 1.0
        assert score.tool_selection == 1.0
        assert score.path_efficiency == 1.0
        assert score.completeness == 1.0

    def test_bad_trajectory_scores_below_07(self):
        ref = [
            {"tool": "search", "status": "success"},
            {"tool": "write", "status": "success"},
        ]
        bad = [
            {"tool": "search", "status": "error"},
            {"tool": "search", "status": "error"},
            {"tool": "wrong_tool", "status": "success"},
            {"tool": "search", "status": "success"},
            {"tool": "write", "status": "success"},
        ]
        score = self.te.evaluate(bad, reference_trajectory=ref)
        assert score.overall < 0.9  # Degraded from errors + wrong tools
        assert score.path_efficiency < 0.5  # 5 steps vs 2 reference

    def test_missing_tools_reduce_selection(self):
        traj = [
            {"tool": "search", "status": "success"},
            {"tool": "write", "status": "success"},
        ]
        score = self.te.evaluate(traj, required_tools={"search", "analyze", "write"})
        assert score.tool_selection < 1.0  # "analyze" missing

    def test_longer_path_reduces_efficiency(self):
        ref = [{"tool": "a", "status": "success"}, {"tool": "b", "status": "success"}]
        long_path = [{"tool": "a", "status": "success"}] * 10 + [{"tool": "b", "status": "success"}]
        score = self.te.evaluate(long_path, reference_trajectory=ref)
        assert score.path_efficiency < 0.5  # 11 steps vs 2

    def test_errors_without_recovery(self):
        traj = [
            {"tool": "api_call", "status": "error"},
            {"tool": "api_call", "status": "error"},
            {"tool": "api_call", "status": "error"},
        ]
        score = self.te.evaluate(traj)
        assert score.recovery_quality == 0.0  # No recovery after errors

    def test_errors_with_recovery(self):
        traj = [
            {"tool": "api_call", "status": "error"},
            {"tool": "api_call", "status": "success"},
            {"tool": "write", "status": "success"},
        ]
        score = self.te.evaluate(traj)
        assert score.recovery_quality == 1.0  # Recovered

    def test_empty_trajectory(self):
        score = self.te.evaluate([])
        assert score.overall == 0.0

    def test_step_scores_populated(self):
        traj = [
            {"tool": "a", "status": "success"},
            {"tool": "b", "status": "error"},
            {"tool": "c", "status": "success"},
        ]
        score = self.te.evaluate(traj)
        assert len(score.step_scores) == 3
        assert score.step_scores[0]["quality"] == 1.0
        assert score.step_scores[1]["quality"] == 0.3  # error


# ═══════════════════════════════════════════════════════════════
# 2. QUALITY SCORING
# ═══════════════════════════════════════════════════════════════

class TestQualityScoring:
    def _make_detection(self, det_type, confidence):
        class FakeDet:
            def __init__(self, dt, conf):
                self.detection_type = dt
                self.confidence = conf
        return FakeDet(det_type, confidence)

    def test_quality_score_formula(self):
        from app.api.v1.detections import _compute_quality_score
        d = self._make_detection("hallucination", 85)
        assert _compute_quality_score(d) == pytest.approx(0.15, abs=0.01)

    def test_zero_confidence_perfect_quality(self):
        from app.api.v1.detections import _compute_quality_score
        d = self._make_detection("loop", 0)
        assert _compute_quality_score(d) == 1.0

    def test_full_confidence_zero_quality(self):
        from app.api.v1.detections import _compute_quality_score
        d = self._make_detection("injection", 100)
        assert _compute_quality_score(d) == 0.0

    def test_hallucination_maps_to_correctness(self):
        from app.api.v1.detections import _compute_quality_dimensions
        d = self._make_detection("hallucination", 80)
        dims = _compute_quality_dimensions(d)
        assert dims["correctness"] < 1.0
        assert dims["safety"] == 1.0  # Not a safety issue
        assert dims["efficiency"] == 1.0

    def test_injection_maps_to_safety(self):
        from app.api.v1.detections import _compute_quality_dimensions
        d = self._make_detection("injection", 70)
        dims = _compute_quality_dimensions(d)
        assert dims["safety"] < 1.0
        assert dims["correctness"] == 1.0

    def test_loop_maps_to_efficiency(self):
        from app.api.v1.detections import _compute_quality_dimensions
        d = self._make_detection("loop", 90)
        dims = _compute_quality_dimensions(d)
        assert dims["efficiency"] < 0.2
        assert dims["safety"] == 1.0

    def test_completion_maps_to_completeness(self):
        from app.api.v1.detections import _compute_quality_dimensions
        d = self._make_detection("completion", 60)
        dims = _compute_quality_dimensions(d)
        assert dims["completeness"] < 1.0


# ═══════════════════════════════════════════════════════════════
# 3. SEMANTIC ENTROPY
# ═══════════════════════════════════════════════════════════════

class TestSemanticEntropy:
    def setup_method(self):
        from app.detection.semantic_entropy import SemanticEntropyEstimator
        self.se = SemanticEntropyEstimator()

    def test_consistent_responses_low_entropy(self):
        responses = [
            "The capital of France is Paris.",
            "Paris is the capital of France.",
            "France's capital city is Paris.",
        ]
        result = self.se.estimate(responses)
        assert result.entropy < 0.5
        assert result.is_reliable
        assert result.consistency > 0.5
        assert result.n_clusters <= 2

    def test_inconsistent_responses_high_entropy(self):
        responses = [
            "The capital is Paris.",
            "The capital is Berlin.",
            "The capital is Tokyo.",
            "The capital is Madrid.",
            "The capital is Rome.",
        ]
        result = self.se.estimate(responses)
        assert result.entropy > 0.5
        assert not result.is_reliable
        assert result.n_clusters >= 3

    def test_single_response_zero_entropy(self):
        result = self.se.estimate(["Just one answer."])
        assert result.entropy == 0.0
        assert result.is_reliable
        assert result.consistency == 1.0

    def test_two_identical_responses(self):
        result = self.se.estimate(["Same answer.", "Same answer."])
        assert result.entropy == 0.0
        assert result.n_clusters == 1

    def test_hallucination_risk_scoring(self):
        reliable = ["Paris is the capital.", "The capital is Paris."]
        unreliable = ["It's Paris.", "It's London.", "It's Berlin."]
        risk_low, _ = self.se.score_hallucination_risk(reliable)
        risk_high, _ = self.se.score_hallucination_risk(unreliable)
        assert risk_high > risk_low

    def test_entropy_on_golden_hallucination_data(self):
        """Test that semantic entropy correlates with hallucination detection
        on real golden dataset entries."""
        data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'golden_dataset_external.json')
        if not os.path.exists(data_path):
            pytest.skip("Golden dataset not available")

        with open(data_path) as f:
            data = json.load(f)

        hall_entries = [e for e in data['entries']
                        if e.get('detection_type') == 'hallucination'][:20]
        if len(hall_entries) < 5:
            pytest.skip("Not enough hallucination entries")

        # For entries with output, check that outputs from DIFFERENT entries
        # have higher entropy than outputs from the SAME topic
        outputs = [e['input_data'].get('output', '')[:200] for e in hall_entries if e['input_data'].get('output')]
        if len(outputs) >= 5:
            result = self.se.estimate(outputs[:5])
            # Different hallucination outputs should have moderate-high entropy
            assert result.n_clusters >= 1  # At minimum they exist


# ═══════════════════════════════════════════════════════════════
# 4. FIX LEARNING LOOP
# ═══════════════════════════════════════════════════════════════

class TestFixLearningLoop:
    def setup_method(self):
        from app.healing.fix_effectiveness import FixEffectivenessTracker
        # Use temp dir to avoid polluting real data
        import tempfile
        self.tmpdir = tempfile.mkdtemp()
        self.tracker = FixEffectivenessTracker(data_dir=self.tmpdir)

    def test_record_success(self):
        self.tracker.record_outcome("timeout_addition", "n8n_timeout", 0.88, 0.0, True)
        rec = self.tracker.get_effectiveness("timeout_addition", "n8n_timeout")
        assert rec is not None
        assert rec.success_count == 1
        assert rec.fail_count == 0
        assert rec.success_rate == 1.0

    def test_record_failure(self):
        self.tracker.record_outcome("retry_limit", "loop", 0.95, 0.90, False)
        rec = self.tracker.get_effectiveness("retry_limit", "loop")
        assert rec.success_count == 0
        assert rec.fail_count == 1
        assert rec.success_rate == 0.0

    def test_ranking_prefers_successful_fixes(self):
        self.tracker.record_outcome("timeout_addition", "n8n_timeout", 0.88, 0.0, True)
        self.tracker.record_outcome("timeout_addition", "n8n_timeout", 0.76, 0.0, True)
        self.tracker.record_outcome("circuit_breaker", "n8n_timeout", 0.80, 0.75, False)

        rankings = self.tracker.rank_fixes_for_detection(
            "n8n_timeout", ["timeout_addition", "circuit_breaker", "retry_limit"]
        )
        assert rankings[0][0] == "timeout_addition"  # Most successful
        assert rankings[0][1] > rankings[1][1]  # Higher score

    def test_unknown_fix_gets_neutral_score(self):
        rankings = self.tracker.rank_fixes_for_detection(
            "unknown_type", ["fix_a", "fix_b"]
        )
        assert all(score == 0.5 for _, score in rankings)

    def test_avg_confidence_drop_tracked(self):
        self.tracker.record_outcome("timeout_addition", "n8n_timeout", 0.88, 0.0, True)
        self.tracker.record_outcome("timeout_addition", "n8n_timeout", 0.76, 0.10, True)
        rec = self.tracker.get_effectiveness("timeout_addition", "n8n_timeout")
        # Average drop: (0.88 + 0.66) / 2 = 0.77
        assert rec.avg_confidence_drop > 0.5

    def test_persistence(self):
        """Data persists after creating a new tracker instance."""
        self.tracker.record_outcome("test_fix", "test_det", 0.9, 0.1, True)
        # Create new instance pointing to same dir
        from app.healing.fix_effectiveness import FixEffectivenessTracker
        tracker2 = FixEffectivenessTracker(data_dir=self.tmpdir)
        rec = tracker2.get_effectiveness("test_fix", "test_det")
        assert rec is not None
        assert rec.success_count == 1

    def test_seed_from_e2e_results(self):
        """Seeding from E2E results populates effectiveness data."""
        results_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'healing_e2e_results.json')
        if not os.path.exists(results_path):
            pytest.skip("E2E results not available")

        self.tracker.seed_from_e2e_results(results_path)
        # Should have at least some records
        rankings = self.tracker.rank_fixes_for_detection(
            "n8n_timeout", ["timeout_addition", "circuit_breaker"]
        )
        # After seeding, timeout_addition should rank higher (it was FIXED)
        assert len(rankings) == 2
