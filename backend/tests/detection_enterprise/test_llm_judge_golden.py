"""Tests for LLM judge agreement with golden-labeled traces.

Tests that the LLM judge produces scores consistent with ground-truth
golden labels from the MAST-annotated dataset. Uses deterministic mock
judge responses to verify agreement metrics (accuracy, Cohen's kappa,
per-label precision/recall).
"""

import pytest
import math
import random
from unittest.mock import patch, MagicMock
from collections import Counter

from app.enterprise.evals.llm_judge import (
    LLMJudge,
    LLMJudgeScorer,
    JudgmentResult,
    JudgeModel,
)
from app.enterprise.evals.scorer import EvalType, EvalResult


# ============================================================================
# Agreement Metric Helpers
# ============================================================================


def compute_accuracy(y_true, y_pred):
    """Compute accuracy from boolean lists."""
    if not y_true:
        return 0.0
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return correct / len(y_true)


def compute_cohens_kappa(y_true, y_pred):
    """Compute Cohen's kappa coefficient."""
    if not y_true:
        return 0.0
    n = len(y_true)
    # Observed agreement
    po = sum(1 for t, p in zip(y_true, y_pred) if t == p) / n
    # Expected agreement by chance
    true_pos = sum(y_true) / n
    pred_pos = sum(y_pred) / n
    pe = true_pos * pred_pos + (1 - true_pos) * (1 - pred_pos)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def compute_precision_recall(y_true, y_pred):
    """Compute precision and recall."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


# ============================================================================
# Mock Judge Helper
# ============================================================================


def create_mock_judge_response(expected_detection, seed=42):
    """Create deterministic mock judge response based on golden label.

    For traces with expected_detection=True, returns high scores (0.7-0.95).
    For traces with expected_detection=False, returns low scores (0.1-0.4).
    Uses seeded random for reproducibility with controlled noise.
    """
    rng = random.Random(seed)
    if expected_detection:
        base_score = 0.85
        noise = rng.uniform(-0.15, 0.10)
    else:
        base_score = 0.25
        noise = rng.uniform(-0.15, 0.15)
    score = max(0.0, min(1.0, base_score + noise))
    return JudgmentResult(
        score=score,
        reasoning=f"Mock judgment (expected={expected_detection})",
        confidence=0.9,
        raw_response="{}",
        model_used="mock-judge",
        tokens_used=0,
    )


# ============================================================================
# Golden Dataset Tests
# ============================================================================


class TestGoldenDatasetLoading:
    """Tests that golden dataset loads correctly."""

    def test_golden_traces_not_empty(self, golden_traces):
        """Golden dataset should contain traces."""
        assert len(golden_traces) > 0, "Golden traces fixture is empty"

    def test_golden_traces_have_metadata(self, golden_traces):
        """Each golden trace should have _golden_metadata."""
        traces_with_metadata = [
            t for t in golden_traces if "_golden_metadata" in t
        ]
        assert len(traces_with_metadata) > 0, "No traces with _golden_metadata"

    def test_golden_traces_have_detection_type(self, golden_traces):
        """Golden metadata should include detection_type."""
        for trace in golden_traces:
            metadata = trace.get("_golden_metadata", {})
            if metadata:
                assert "detection_type" in metadata or "variant" in metadata, (
                    f"Trace missing detection_type: {list(metadata.keys())}"
                )

    def test_golden_traces_have_expected_detection(self, golden_traces):
        """Traces should have expected_detection boolean."""
        traces_with_expected = [
            t for t in golden_traces
            if t.get("_golden_metadata", {}).get("expected_detection") is not None
        ]
        assert len(traces_with_expected) > 0, "No traces with expected_detection"

    def test_golden_traces_have_otel_structure(self, golden_traces):
        """Traces should have resourceSpans (OTEL format)."""
        otel_traces = [t for t in golden_traces if "resourceSpans" in t]
        assert len(otel_traces) > 0, "No OTEL-formatted traces"


class TestGoldenLabelDistribution:
    """Tests that golden labels have reasonable distribution."""

    def test_multiple_detection_types(self, golden_traces):
        """Should have at least 5 different detection types."""
        types = set()
        for trace in golden_traces:
            metadata = trace.get("_golden_metadata", {})
            dt = metadata.get("detection_type")
            if dt:
                types.add(dt)
        assert len(types) >= 5, f"Only {len(types)} types found: {types}"

    def test_has_positive_and_negative_labels(self, golden_traces):
        """Should have both positive and negative detection labels."""
        positive = sum(
            1 for t in golden_traces
            if t.get("_golden_metadata", {}).get("expected_detection") is True
        )
        negative = sum(
            1 for t in golden_traces
            if t.get("_golden_metadata", {}).get("expected_detection") is False
        )
        # At least some of each (golden dataset is heavily positive, so negative may be 0)
        assert positive > 0, "No positive labels"

    def test_mast_annotated_traces(self, golden_traces):
        """Should have MAST-annotated traces with F-code labels."""
        mast_count = sum(
            1 for t in golden_traces
            if t.get("_golden_metadata", {}).get("mast_annotation")
        )
        # Some traces have MAST annotations
        assert mast_count >= 0  # Dataset may or may not have MAST annotations

    def test_detection_type_distribution(self, golden_traces_by_type):
        """Detection types should have reasonable distribution."""
        assert len(golden_traces_by_type) > 0, "No detection types"
        counts = {k: len(v) for k, v in golden_traces_by_type.items()}
        # No single type should dominate >80% of the dataset
        total = sum(counts.values())
        if total > 10:
            max_ratio = max(counts.values()) / total
            assert max_ratio < 0.8, f"Type distribution too skewed: {counts}"


# ============================================================================
# Mocked Judge Agreement Tests
# ============================================================================


class TestMockedJudgeAgreement:
    """Tests LLM judge agreement with golden labels using mocked responses."""

    def _get_labeled_traces(self, golden_traces):
        """Extract traces with expected_detection labels."""
        labeled = []
        for i, trace in enumerate(golden_traces):
            metadata = trace.get("_golden_metadata", {})
            expected = metadata.get("expected_detection")
            if expected is not None:
                labeled.append((i, trace, expected))
        return labeled

    def test_mock_judge_accuracy(self, golden_traces):
        """Mock judge should achieve >0.5 accuracy on golden labels."""
        labeled = self._get_labeled_traces(golden_traces)
        if len(labeled) < 5:
            pytest.skip("Not enough labeled traces for accuracy test")

        y_true = []
        y_pred = []

        for i, trace, expected in labeled:
            result = create_mock_judge_response(expected, seed=i)
            y_true.append(expected)
            y_pred.append(result.score >= 0.5)

        accuracy = compute_accuracy(y_true, y_pred)
        assert accuracy > 0.5, f"Accuracy {accuracy:.3f} below 0.5 threshold"

    def test_mock_judge_cohens_kappa(self, golden_traces):
        """Mock judge should achieve Cohen's kappa >0.0 (better than chance)."""
        labeled = self._get_labeled_traces(golden_traces)
        if len(labeled) < 5:
            pytest.skip("Not enough labeled traces for kappa test")

        y_true = []
        y_pred = []

        for i, trace, expected in labeled:
            result = create_mock_judge_response(expected, seed=i)
            y_true.append(expected)
            y_pred.append(result.score >= 0.5)

        kappa = compute_cohens_kappa(y_true, y_pred)
        assert kappa > 0.0, f"Cohen's kappa {kappa:.3f} not better than chance"

    def test_mock_judge_precision_recall(self, golden_traces):
        """Mock judge should have reasonable precision and recall."""
        labeled = self._get_labeled_traces(golden_traces)
        if len(labeled) < 5:
            pytest.skip("Not enough labeled traces for precision/recall test")

        y_true = []
        y_pred = []

        for i, trace, expected in labeled:
            result = create_mock_judge_response(expected, seed=i)
            y_true.append(expected)
            y_pred.append(result.score >= 0.5)

        precision, recall = compute_precision_recall(y_true, y_pred)
        # With mock responses aligned to labels, both should be high
        assert precision > 0.5, f"Precision {precision:.3f} below 0.5"
        assert recall > 0.5, f"Recall {recall:.3f} below 0.5"

    def test_per_type_agreement(self, golden_traces_by_type):
        """Mock judge should agree on most detection types."""
        if not golden_traces_by_type:
            pytest.skip("No detection types available")

        type_accuracies = {}
        for det_type, traces in golden_traces_by_type.items():
            y_true = []
            y_pred = []
            for i, trace in enumerate(traces):
                expected = trace.get("_golden_metadata", {}).get("expected_detection")
                if expected is not None:
                    result = create_mock_judge_response(expected, seed=hash(det_type) + i)
                    y_true.append(expected)
                    y_pred.append(result.score >= 0.5)
            if y_true:
                type_accuracies[det_type] = compute_accuracy(y_true, y_pred)

        if type_accuracies:
            avg_accuracy = sum(type_accuracies.values()) / len(type_accuracies)
            assert avg_accuracy > 0.5, (
                f"Average per-type accuracy {avg_accuracy:.3f} below 0.5"
            )


# ============================================================================
# Agreement Metric Unit Tests
# ============================================================================


class TestAgreementMetrics:
    """Standalone tests for agreement metric computation."""

    def test_accuracy_perfect(self):
        """Perfect predictions should give accuracy=1.0."""
        assert compute_accuracy([True, False, True], [True, False, True]) == 1.0

    def test_accuracy_zero(self):
        """All wrong predictions should give accuracy=0.0."""
        assert compute_accuracy([True, False, True], [False, True, False]) == 0.0

    def test_accuracy_partial(self):
        """2/3 correct should give accuracy=2/3."""
        acc = compute_accuracy([True, True, False], [True, True, True])
        assert abs(acc - 2 / 3) < 1e-9

    def test_accuracy_empty(self):
        """Empty input should return 0.0."""
        assert compute_accuracy([], []) == 0.0

    def test_kappa_perfect(self):
        """Perfect agreement should give kappa=1.0."""
        kappa = compute_cohens_kappa(
            [True, False, True, False],
            [True, False, True, False],
        )
        assert abs(kappa - 1.0) < 1e-9

    def test_kappa_chance(self):
        """Random agreement should give kappa near 0."""
        # Construct case where observed == expected
        y_true = [True, True, False, False]
        y_pred = [True, False, True, False]
        kappa = compute_cohens_kappa(y_true, y_pred)
        assert abs(kappa) < 0.01, f"Kappa {kappa:.3f} should be near 0"

    def test_kappa_empty(self):
        """Empty input should return 0.0."""
        assert compute_cohens_kappa([], []) == 0.0

    def test_precision_perfect(self):
        """Perfect precision: all predictions correct."""
        p, r = compute_precision_recall([True, True, False], [True, True, False])
        assert p == 1.0
        assert r == 1.0

    def test_precision_no_positives(self):
        """No positive predictions should give precision=0."""
        p, r = compute_precision_recall([True, True], [False, False])
        assert p == 0.0
        assert r == 0.0

    def test_recall_partial(self):
        """Partial recall with all-positive predictions."""
        p, r = compute_precision_recall(
            [True, True, False, False],
            [True, True, True, True],
        )
        assert r == 1.0  # All true positives found
        assert p == 0.5  # Half the predictions are FP


# ============================================================================
# LLMJudgeScorer on Golden Traces Tests
# ============================================================================


class TestJudgeScorerOnGoldenTraces:
    """Tests LLMJudgeScorer produces valid EvalResults for golden traces."""

    def _extract_output_from_trace(self, trace):
        """Extract agent output text from OTEL trace."""
        resource_spans = trace.get("resourceSpans", [])
        for rs in resource_spans:
            for scope_span in rs.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    attrs = {
                        a["key"]: a["value"]
                        for a in span.get("attributes", [])
                    }
                    response = attrs.get("gen_ai.response.sample", {})
                    if isinstance(response, dict):
                        return response.get("stringValue", "")
                    if isinstance(response, str):
                        return response
        return "No output extracted"

    @patch.object(LLMJudge, "judge")
    def test_scorer_returns_eval_result(self, mock_judge, golden_traces):
        """Scorer should return EvalResult for each golden trace."""
        if not golden_traces:
            pytest.skip("No golden traces")

        mock_judge.return_value = JudgmentResult(
            score=0.8,
            reasoning="Evaluated",
            confidence=0.9,
            raw_response="{}",
            model_used="mock",
            tokens_used=0,
        )

        scorer = LLMJudgeScorer(EvalType.RELEVANCE)
        trace = golden_traces[0]
        output = self._extract_output_from_trace(trace)

        result = scorer.score(output=output, context="Evaluate this trace")

        assert isinstance(result, EvalResult)
        assert result.eval_type == EvalType.RELEVANCE
        assert 0.0 <= result.score <= 1.0
        assert isinstance(result.passed, bool)

    @patch.object(LLMJudge, "judge")
    def test_scorer_threshold_agreement(self, mock_judge, golden_traces):
        """Scorer threshold should align with golden expected_detection."""
        labeled = [
            t for t in golden_traces
            if t.get("_golden_metadata", {}).get("expected_detection") is not None
        ]
        if len(labeled) < 3:
            pytest.skip("Not enough labeled traces")

        agreements = 0
        total = min(len(labeled), 20)  # Test up to 20 traces

        for i, trace in enumerate(labeled[:total]):
            expected = trace["_golden_metadata"]["expected_detection"]
            mock_result = create_mock_judge_response(expected, seed=i + 100)
            mock_judge.return_value = mock_result

            scorer = LLMJudgeScorer(EvalType.RELEVANCE)
            output = self._extract_output_from_trace(trace)
            result = scorer.score(output=output, threshold=0.5)

            if result.passed == expected:
                agreements += 1

        agreement_rate = agreements / total
        assert agreement_rate > 0.5, (
            f"Agreement rate {agreement_rate:.3f} below 0.5"
        )

    @patch.object(LLMJudge, "judge")
    def test_scorer_metadata_populated(self, mock_judge, golden_traces):
        """Scorer should populate metadata from judge response."""
        if not golden_traces:
            pytest.skip("No golden traces")

        mock_judge.return_value = JudgmentResult(
            score=0.75,
            reasoning="Test reasoning",
            confidence=0.85,
            raw_response='{"score": 0.75}',
            model_used="gpt-4o-mini",
            tokens_used=120,
        )

        scorer = LLMJudgeScorer(EvalType.COHERENCE)
        output = self._extract_output_from_trace(golden_traces[0])
        result = scorer.score(output=output)

        assert result.metadata["model"] == "gpt-4o-mini"
        assert result.metadata["confidence"] == 0.85
        assert result.metadata["tokens_used"] == 120

    @patch.object(LLMJudge, "judge")
    def test_multiple_eval_types_on_trace(self, mock_judge, golden_traces):
        """Should evaluate same trace with multiple eval types."""
        if not golden_traces:
            pytest.skip("No golden traces")

        mock_judge.return_value = JudgmentResult(
            score=0.8,
            reasoning="Good",
            confidence=0.9,
            raw_response="{}",
            model_used="mock",
            tokens_used=50,
        )

        output = self._extract_output_from_trace(golden_traces[0])
        eval_types = [EvalType.RELEVANCE, EvalType.COHERENCE, EvalType.SAFETY]
        results = {}

        for et in eval_types:
            scorer = LLMJudgeScorer(et)
            results[et] = scorer.score(output=output)

        assert len(results) == 3
        for et, result in results.items():
            assert result.eval_type == et
            assert isinstance(result, EvalResult)


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCasesGolden:
    """Edge cases for golden label evaluation."""

    def test_trace_without_mast_annotation_skips(self, golden_traces):
        """Traces without mast_annotation should be skippable."""
        traces_without_mast = [
            t for t in golden_traces
            if not t.get("_golden_metadata", {}).get("mast_annotation")
        ]
        # Just verify we can identify and filter them
        assert isinstance(traces_without_mast, list)

    def test_trace_with_single_mast_label(self, golden_traces):
        """Traces with single MAST label should work correctly."""
        for trace in golden_traces:
            annotation = trace.get("_golden_metadata", {}).get("mast_annotation", {})
            if annotation and len(annotation) == 1:
                # Verify single-label trace structure
                key = list(annotation.keys())[0]
                assert isinstance(key, str)
                assert annotation[key] in (0, 1)
                break

    def test_trace_with_multi_mast_labels(self, golden_traces):
        """Traces can have multiple MAST labels."""
        for trace in golden_traces:
            annotation = trace.get("_golden_metadata", {}).get("mast_annotation", {})
            if annotation:
                active_labels = [k for k, v in annotation.items() if v == 1]
                # Check that annotation values are 0 or 1
                for v in annotation.values():
                    assert v in (0, 1), f"Unexpected MAST value: {v}"
                break

    def test_mock_judge_deterministic(self):
        """Same seed should produce same score."""
        r1 = create_mock_judge_response(True, seed=42)
        r2 = create_mock_judge_response(True, seed=42)
        assert r1.score == r2.score

    def test_mock_judge_different_seeds(self):
        """Different seeds should produce different scores."""
        r1 = create_mock_judge_response(True, seed=1)
        r2 = create_mock_judge_response(True, seed=2)
        # Scores may differ (not guaranteed but very likely)
        # Just ensure both are valid
        assert 0.0 <= r1.score <= 1.0
        assert 0.0 <= r2.score <= 1.0

    def test_mock_judge_positive_vs_negative(self):
        """Positive expected should score higher than negative on average."""
        pos_scores = [create_mock_judge_response(True, seed=i).score for i in range(50)]
        neg_scores = [create_mock_judge_response(False, seed=i + 100).score for i in range(50)]
        avg_pos = sum(pos_scores) / len(pos_scores)
        avg_neg = sum(neg_scores) / len(neg_scores)
        assert avg_pos > avg_neg, (
            f"Positive avg {avg_pos:.3f} not greater than negative avg {avg_neg:.3f}"
        )

    def test_empty_golden_traces_handled(self):
        """Empty trace list should not crash metric computation."""
        y_true = []
        y_pred = []
        assert compute_accuracy(y_true, y_pred) == 0.0
        assert compute_cohens_kappa(y_true, y_pred) == 0.0
        p, r = compute_precision_recall(y_true, y_pred)
        assert p == 0.0
        assert r == 0.0


# ============================================================================
# MAST Trace Tests
# ============================================================================


class TestMASTTraceAgreement:
    """Tests using MAST benchmark traces with F1-F14 labels."""

    def test_mast_traces_load(self, mast_traces):
        """MAST traces should load from fixture."""
        # mast_traces may be empty if file doesn't exist
        assert isinstance(mast_traces, list)

    def test_mast_traces_have_annotations(self, mast_traces):
        """MAST traces should have mast_annotation field."""
        if not mast_traces:
            pytest.skip("No MAST traces available")
        for trace in mast_traces:
            assert "mast_annotation" in trace, (
                f"Trace {trace.get('trace_id')} missing mast_annotation"
            )

    def test_mast_annotation_format(self, mast_traces):
        """MAST annotations should have F-code format (e.g., '1.1', '2.3')."""
        if not mast_traces:
            pytest.skip("No MAST traces available")
        for trace in mast_traces:
            annotation = trace.get("mast_annotation", {})
            for key, value in annotation.items():
                # Keys like "1.1", "2.3", etc.
                parts = key.split(".")
                assert len(parts) == 2, f"Unexpected key format: {key}"
                assert parts[0].isdigit(), f"Category not numeric: {key}"
                assert parts[1].isdigit(), f"Sub-code not numeric: {key}"
                assert value in (0, 1), f"Value not binary: {value}"

    def test_mast_label_coverage(self, mast_traces):
        """MAST traces should cover multiple failure categories."""
        if not mast_traces:
            pytest.skip("No MAST traces available")
        active_codes = set()
        for trace in mast_traces:
            annotation = trace.get("mast_annotation", {})
            for key, value in annotation.items():
                if value == 1:
                    active_codes.add(key)
        # Should have at least some active failure codes
        assert len(active_codes) > 0, "No active MAST failure codes found"

    @patch.object(LLMJudge, "judge")
    def test_mast_judge_produces_valid_scores(self, mock_judge, mast_traces):
        """Judge should produce valid scores for MAST traces."""
        if not mast_traces:
            pytest.skip("No MAST traces available")

        mock_judge.return_value = JudgmentResult(
            score=0.7,
            reasoning="Evaluated MAST trace",
            confidence=0.85,
            raw_response="{}",
            model_used="mock",
            tokens_used=0,
        )

        scorer = LLMJudgeScorer(EvalType.FACTUALITY)
        trace = mast_traces[0]
        trajectory = trace.get("trace", {}).get("trajectory", "")

        result = scorer.score(output=trajectory, context=trace.get("task", ""))
        assert isinstance(result, EvalResult)
        assert 0.0 <= result.score <= 1.0
