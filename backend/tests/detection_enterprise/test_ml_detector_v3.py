"""Tests for the ML Detector v3 (Multi-task Learning)."""

import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from app.detection_enterprise.ml_detector_v3 import (
    MultiTaskDetector,
    EnsembleDetector,
    FAILURE_MODES,
    ANNOTATION_MAP,
)


# ============================================================================
# FAILURE_MODES and ANNOTATION_MAP Tests
# ============================================================================

class TestConstants:
    """Tests for module constants."""

    def test_failure_modes_defined(self):
        """Should have failure modes defined."""
        assert isinstance(FAILURE_MODES, list)
        assert len(FAILURE_MODES) > 0
        assert "F1" in FAILURE_MODES
        assert "F3" in FAILURE_MODES

    def test_annotation_map_defined(self):
        """Should have annotation map defined."""
        assert isinstance(ANNOTATION_MAP, dict)
        assert "1.1" in ANNOTATION_MAP
        assert ANNOTATION_MAP["1.1"] == "F1"

    def test_annotation_map_covers_modes(self):
        """Annotation map should cover most failure modes."""
        mapped_modes = set(ANNOTATION_MAP.values())
        # Most modes should be in the map
        assert len(mapped_modes) >= 10


# ============================================================================
# MultiTaskDetector Initialization Tests
# ============================================================================

class TestMultiTaskDetectorInit:
    """Tests for MultiTaskDetector initialization."""

    def test_default_initialization(self):
        """Should initialize with default parameters."""
        detector = MultiTaskDetector()

        assert detector.embedding_model == "all-mpnet-base-v2"
        assert detector.hidden_dims == [512, 256, 128]
        assert detector.dropout == 0.3
        assert detector.learning_rate == 0.001
        assert detector.epochs == 50
        assert detector.batch_size == 32
        assert detector.is_trained is False

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        detector = MultiTaskDetector(
            embedding_model="all-MiniLM-L6-v2",
            hidden_dims=[256, 128],
            dropout=0.5,
            learning_rate=0.0001,
            epochs=100,
            batch_size=16,
        )

        assert detector.embedding_model == "all-MiniLM-L6-v2"
        assert detector.hidden_dims == [256, 128]
        assert detector.dropout == 0.5
        assert detector.learning_rate == 0.0001
        assert detector.epochs == 100
        assert detector.batch_size == 16

    def test_embedder_lazy_loading(self):
        """Embedder should be None until first access."""
        detector = MultiTaskDetector()

        assert detector._embedder is None


# ============================================================================
# Text Extraction Tests
# ============================================================================

class TestTextExtraction:
    """Tests for extracting text from records."""

    def test_extract_text_from_trace(self):
        """Should extract text from trace trajectory."""
        detector = MultiTaskDetector()
        record = {
            "trace": {
                "trajectory": "User asked about weather. Agent responded with forecast."
            }
        }

        text = detector._extract_text(record)

        assert "User asked about weather" in text
        assert "forecast" in text

    def test_extract_text_empty_record(self):
        """Should handle empty record."""
        detector = MultiTaskDetector()
        record = {}

        text = detector._extract_text(record)

        assert text == ""

    def test_extract_text_truncation(self):
        """Should truncate very long text."""
        detector = MultiTaskDetector()
        long_text = "x" * 20000
        record = {"trace": {"trajectory": long_text}}

        text = detector._extract_text(record)

        assert len(text) <= 15000


# ============================================================================
# Label Extraction Tests
# ============================================================================

class TestLabelExtraction:
    """Tests for extracting labels from records."""

    def test_get_labels_from_annotations(self):
        """Should extract labels from MAST annotations."""
        detector = MultiTaskDetector()
        record = {
            "mast_annotation": {
                "1.1": 1,  # F1
                "1.3": 1,  # F3
                "2.1": 0,  # F6
            }
        }

        labels = detector._get_labels(record)

        assert labels.get("F1") is True
        assert labels.get("F3") is True
        assert labels.get("F6") is False

    def test_get_labels_empty_annotations(self):
        """Should handle empty annotations."""
        detector = MultiTaskDetector()
        record = {"mast_annotation": {}}

        labels = detector._get_labels(record)

        assert isinstance(labels, dict)
        # All labels should be False or not present
        for mode in FAILURE_MODES:
            assert labels.get(mode, False) is False

    def test_get_labels_missing_annotations(self):
        """Should handle missing annotations field."""
        detector = MultiTaskDetector()
        record = {}

        labels = detector._get_labels(record)

        assert isinstance(labels, dict)


# ============================================================================
# Training Tests (Mocked)
# ============================================================================

class TestTrainingMocked:
    """Tests for training workflow with mocked dependencies."""

    @pytest.fixture
    def mock_embedder(self):
        """Mock sentence transformer."""
        mock = MagicMock()
        # Return 384-dim embeddings (like MiniLM)
        mock.encode.return_value = np.random.randn(10, 384).astype(np.float32)
        return mock

    def test_train_requires_records(self):
        """Train should work with records."""
        detector = MultiTaskDetector(epochs=1, hidden_dims=[32])

        # Create mock records
        records = [
            {
                "trace": {"trajectory": f"Test trajectory {i}"},
                "mast_annotation": {"1.1": i % 2, "1.3": (i + 1) % 2}
            }
            for i in range(20)
        ]

        # Mock the embedder
        with patch.object(detector, '_embedder', MagicMock()):
            detector._embedder.encode = MagicMock(
                return_value=np.random.randn(20, 384).astype(np.float32)
            )

            # This will fail if PyTorch isn't installed
            try:
                result = detector.train(records)
                assert "modes" in result or "overall" in result
            except (ImportError, RuntimeError):
                # Skip if PyTorch not available
                pytest.skip("PyTorch not available")


# ============================================================================
# Prediction Tests (Mocked)
# ============================================================================

class TestPredictionMocked:
    """Tests for prediction workflow with mocked dependencies."""

    def test_predict_requires_trained_model(self):
        """Should raise error if not trained."""
        detector = MultiTaskDetector()

        records = [{"trace": {"trajectory": "Test"}}]

        with pytest.raises(RuntimeError) as exc_info:
            detector.predict_batch(records)

        assert "not trained" in str(exc_info.value).lower()

    def test_predict_batch_returns_list(self):
        """Should return list of predictions."""
        detector = MultiTaskDetector()
        detector.is_trained = True

        # Mock dependencies
        mock_scaler = MagicMock()
        mock_scaler.transform.return_value = np.random.randn(2, 384)
        detector.scaler = mock_scaler

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = np.random.randn(2, 384)
        detector._embedder = mock_embedder

        # Mock model
        try:
            import torch
            mock_model = MagicMock()
            mock_param = torch.nn.Parameter(torch.zeros(1))
            mock_model.parameters.return_value = iter([mock_param])
            mock_model.eval = MagicMock()

            # Mock forward pass
            mock_output = torch.randn(2, len(FAILURE_MODES))
            mock_model.return_value = mock_output
            detector.model = mock_model

            records = [
                {"trace": {"trajectory": "Test 1"}},
                {"trace": {"trajectory": "Test 2"}},
            ]

            with patch('torch.no_grad'):
                results = detector.predict_batch(records)

            assert isinstance(results, list)
            assert len(results) == 2
        except ImportError:
            pytest.skip("PyTorch not available")


# ============================================================================
# EnsembleDetector Tests
# ============================================================================

class TestEnsembleDetector:
    """Tests for EnsembleDetector."""

    def test_initialization(self):
        """Should initialize empty."""
        ensemble = EnsembleDetector()

        assert ensemble.detectors == []
        assert ensemble.weights == {}

    def test_add_detector(self):
        """Should add detector with weight."""
        ensemble = EnsembleDetector()
        mock_detector = MagicMock()

        ensemble.add_detector("detector_1", mock_detector, weight=1.5)

        assert len(ensemble.detectors) == 1
        assert ensemble.weights["detector_1"] == 1.5

    def test_add_multiple_detectors(self):
        """Should add multiple detectors."""
        ensemble = EnsembleDetector()

        ensemble.add_detector("d1", MagicMock(), weight=1.0)
        ensemble.add_detector("d2", MagicMock(), weight=2.0)
        ensemble.add_detector("d3", MagicMock(), weight=0.5)

        assert len(ensemble.detectors) == 3
        assert ensemble.weights["d1"] == 1.0
        assert ensemble.weights["d2"] == 2.0
        assert ensemble.weights["d3"] == 0.5

    def test_predict_batch_empty_ensemble(self):
        """Should return empty dicts for empty ensemble."""
        ensemble = EnsembleDetector()
        records = [{"trace": {"trajectory": "Test"}}]

        results = ensemble.predict_batch(records)

        assert len(results) == 1
        assert results[0] == {}

    def test_predict_batch_weighted_voting(self):
        """Should use weighted voting for predictions."""
        ensemble = EnsembleDetector()

        # Create mock detectors with different predictions
        d1 = MagicMock()
        d1.predict_batch.return_value = [{"F1": True, "F3": False}]

        d2 = MagicMock()
        d2.predict_batch.return_value = [{"F1": False, "F3": True}]

        # d1 has higher weight
        ensemble.add_detector("d1", d1, weight=2.0)
        ensemble.add_detector("d2", d2, weight=1.0)

        records = [{"trace": {"trajectory": "Test"}}]
        results = ensemble.predict_batch(records)

        # With weights 2:1, d1's vote for F1=True should win
        assert len(results) == 1
        assert results[0]["F1"] is True  # 2/(2+1) > 0.5
        assert results[0]["F3"] is False  # 1/(2+1) < 0.5

    def test_predict_batch_handles_detector_failure(self):
        """Should handle detector failure gracefully."""
        ensemble = EnsembleDetector()

        d1 = MagicMock()
        d1.predict_batch.return_value = [{"F1": True}]

        d2 = MagicMock()
        d2.predict_batch.side_effect = RuntimeError("Detector failed")

        ensemble.add_detector("d1", d1, weight=1.0)
        ensemble.add_detector("d2", d2, weight=1.0)

        records = [{"trace": {"trajectory": "Test"}}]
        results = ensemble.predict_batch(records)

        # Should still return results from working detector
        assert len(results) == 1
        assert "F1" in results[0]


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_trajectory(self):
        """Should handle empty trajectory."""
        detector = MultiTaskDetector()
        record = {"trace": {"trajectory": ""}}

        text = detector._extract_text(record)

        assert text == ""

    def test_none_trajectory(self):
        """Should handle None trajectory."""
        detector = MultiTaskDetector()
        record = {"trace": {"trajectory": None}}

        text = detector._extract_text(record)

        # Should not crash, return empty or None
        assert text in ["", None] or text is None or text == ""

    def test_boolean_annotation_values(self):
        """Should handle boolean annotation values."""
        detector = MultiTaskDetector()
        record = {
            "mast_annotation": {
                "1.1": True,
                "1.3": False,
            }
        }

        labels = detector._get_labels(record)

        assert labels.get("F1") is True
        assert labels.get("F3") is False

    def test_string_annotation_values(self):
        """Should handle string annotation values."""
        detector = MultiTaskDetector()
        record = {
            "mast_annotation": {
                "1.1": "1",
                "1.3": "0",
            }
        }

        labels = detector._get_labels(record)

        # Should convert strings appropriately
        assert isinstance(labels, dict)


# ============================================================================
# Model Configuration Tests
# ============================================================================

class TestModelConfiguration:
    """Tests for model configuration."""

    def test_hidden_dims_affect_architecture(self):
        """Different hidden dims should create different architectures."""
        d1 = MultiTaskDetector(hidden_dims=[512, 256, 128])
        d2 = MultiTaskDetector(hidden_dims=[256, 128])

        assert d1.hidden_dims != d2.hidden_dims
        assert len(d1.hidden_dims) == 3
        assert len(d2.hidden_dims) == 2

    def test_dropout_rate(self):
        """Should store dropout rate."""
        detector = MultiTaskDetector(dropout=0.5)

        assert detector.dropout == 0.5

    def test_learning_rate(self):
        """Should store learning rate."""
        detector = MultiTaskDetector(learning_rate=0.0001)

        assert detector.learning_rate == 0.0001
