"""Tests for the ML Detector v4 (Best-in-Class Multi-Label Classification)."""

import os
import random
import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from app.detection_enterprise.ml_detector_v4 import (
    MultiTaskDetectorV4,
    AdaptiveThresholder,
    ChunkedTextEncoder,
    ContrastiveFineTuner,
    FAILURE_MODES,
    ANNOTATION_MAP,
    LABEL_HIERARCHY,
    MODE_TO_CATEGORY,
    set_random_seeds,
)


# ============================================================================
# Constants Tests
# ============================================================================

class TestConstants:
    """Tests for module constants."""

    def test_failure_modes_defined(self):
        """Should have 12 failure modes (F2/F10 skipped)."""
        assert isinstance(FAILURE_MODES, list)
        assert len(FAILURE_MODES) == 12
        assert "F1" in FAILURE_MODES
        assert "F3" in FAILURE_MODES
        assert "F14" in FAILURE_MODES

    def test_failure_modes_skips_f2_f10(self):
        """F2 and F10 should be excluded (too few samples)."""
        assert "F2" not in FAILURE_MODES
        assert "F10" not in FAILURE_MODES

    def test_annotation_map_defined(self):
        """Should have 14 annotation mappings."""
        assert isinstance(ANNOTATION_MAP, dict)
        assert len(ANNOTATION_MAP) == 14
        assert ANNOTATION_MAP["1.1"] == "F1"
        assert ANNOTATION_MAP["3.3"] == "F14"

    def test_annotation_map_includes_skipped_modes(self):
        """Annotation map should include F2 and F10 even though they're skipped from FAILURE_MODES."""
        mapped_modes = set(ANNOTATION_MAP.values())
        assert "F2" in mapped_modes
        assert "F10" in mapped_modes

    def test_label_hierarchy_defined(self):
        """Should have 6 categories."""
        assert isinstance(LABEL_HIERARCHY, dict)
        assert len(LABEL_HIERARCHY) == 6
        assert "specification" in LABEL_HIERARCHY
        assert "resource" in LABEL_HIERARCHY
        assert "workflow" in LABEL_HIERARCHY
        assert "information" in LABEL_HIERARCHY
        assert "coordination" in LABEL_HIERARCHY
        assert "validation" in LABEL_HIERARCHY

    def test_label_hierarchy_groups(self):
        """Should group modes into correct categories."""
        assert LABEL_HIERARCHY["specification"] == ["F1", "F2"]
        assert LABEL_HIERARCHY["resource"] == ["F3", "F4"]
        assert LABEL_HIERARCHY["validation"] == ["F12", "F13", "F14"]

    def test_mode_to_category_reverse_mapping(self):
        """Should provide reverse mapping from mode to category."""
        assert MODE_TO_CATEGORY["F1"] == "specification"
        assert MODE_TO_CATEGORY["F14"] == "validation"
        assert MODE_TO_CATEGORY["F9"] == "coordination"

    def test_mode_to_category_covers_all_hierarchy_modes(self):
        """Every mode in LABEL_HIERARCHY should be in MODE_TO_CATEGORY."""
        for category, modes in LABEL_HIERARCHY.items():
            for mode in modes:
                assert mode in MODE_TO_CATEGORY
                assert MODE_TO_CATEGORY[mode] == category


# ============================================================================
# set_random_seeds Tests
# ============================================================================

class TestSetRandomSeeds:
    """Tests for reproducibility utility."""

    def test_numpy_seed_deterministic(self):
        """numpy random should be deterministic after seeding."""
        set_random_seeds(42)
        a = np.random.randn(5)
        set_random_seeds(42)
        b = np.random.randn(5)
        np.testing.assert_array_equal(a, b)

    def test_python_random_deterministic(self):
        """Python random should be deterministic after seeding."""
        set_random_seeds(42)
        a = random.random()
        set_random_seeds(42)
        b = random.random()
        assert a == b

    def test_hash_seed_env_set(self):
        """PYTHONHASHSEED should be set in environment."""
        set_random_seeds(42)
        assert os.environ['PYTHONHASHSEED'] == '42'

    def test_torch_seed_set(self):
        """PyTorch random should be deterministic (if available)."""
        try:
            import torch
            set_random_seeds(42)
            a = torch.randn(5)
            set_random_seeds(42)
            b = torch.randn(5)
            assert torch.equal(a, b)
        except ImportError:
            pytest.skip("PyTorch not available")


# ============================================================================
# MultiTaskDetectorV4 Initialization Tests
# ============================================================================

class TestMultiTaskDetectorV4Init:
    """Tests for MultiTaskDetectorV4 initialization."""

    def test_default_initialization(self):
        """Should initialize with default parameters."""
        detector = MultiTaskDetectorV4()

        assert detector.embedding_model == "intfloat/e5-large-v2"
        assert detector.use_contrastive_finetuning is False
        assert detector.use_chunked_encoding is True
        assert detector.use_label_gcn is True
        assert detector.loss_type == "focal"
        assert detector.use_adaptive_thresholding is True
        assert detector.hidden_dims == [512, 256, 128]
        assert detector.dropout == 0.3
        assert detector.learning_rate == 0.001
        assert detector.epochs == 50
        assert detector.batch_size == 32
        assert detector.cv_folds == 5
        assert detector.random_seed == 42
        assert detector.is_trained is False

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        detector = MultiTaskDetectorV4(
            embedding_model="all-MiniLM-L6-v2",
            use_contrastive_finetuning=True,
            use_chunked_encoding=False,
            use_label_gcn=False,
            loss_type="asl",
            use_adaptive_thresholding=False,
            hidden_dims=[256, 128],
            dropout=0.5,
            learning_rate=0.0001,
            epochs=100,
            batch_size=16,
            cv_folds=3,
            random_seed=0,
        )

        assert detector.embedding_model == "all-MiniLM-L6-v2"
        assert detector.use_contrastive_finetuning is True
        assert detector.use_chunked_encoding is False
        assert detector.use_label_gcn is False
        assert detector.loss_type == "asl"
        assert detector.use_adaptive_thresholding is False
        assert detector.hidden_dims == [256, 128]

    def test_embedder_lazy_loading(self):
        """Embedder should be None until first access."""
        detector = MultiTaskDetectorV4()
        assert detector._embedder is None

    def test_components_none_after_init(self):
        """All components should be None before training."""
        detector = MultiTaskDetectorV4()
        assert detector._chunked_encoder is None
        assert detector._contrastive_finetuner is None
        assert detector._label_gcn is None
        assert detector._adaptive_thresholder is None
        assert detector.model is None
        assert detector.scaler is None

    def test_default_thresholds(self):
        """All modes should default to 0.5 threshold."""
        detector = MultiTaskDetectorV4()
        for mode in FAILURE_MODES:
            assert detector.thresholds[mode] == 0.5

    def test_loss_type_options(self):
        """Should accept all loss type options without error."""
        for loss_type in ["focal", "asl", "bce"]:
            detector = MultiTaskDetectorV4(loss_type=loss_type)
            assert detector.loss_type == loss_type


# ============================================================================
# Text Extraction Tests (V4-specific)
# ============================================================================

class TestTextExtractionV4:
    """Tests for _extract_text with V4 e5 instruction prefix."""

    def test_extract_text_from_trace(self):
        """Should extract text from trace trajectory."""
        detector = MultiTaskDetectorV4()
        record = {"trace": {"trajectory": "User asked about weather."}}
        text = detector._extract_text(record)
        assert "User asked about weather" in text

    def test_e5_instruction_prefix_added(self):
        """Default e5 model should add instruction prefix."""
        detector = MultiTaskDetectorV4()  # default: intfloat/e5-large-v2
        record = {"trace": {"trajectory": "Test trajectory"}}
        text = detector._extract_text(record)
        assert text.startswith("query: Classify failure modes in this LLM agent trace: ")

    def test_non_e5_model_no_prefix(self):
        """Non-e5 model should NOT add instruction prefix."""
        detector = MultiTaskDetectorV4(embedding_model="all-mpnet-base-v2")
        record = {"trace": {"trajectory": "Test trajectory"}}
        text = detector._extract_text(record)
        assert not text.startswith("query:")
        assert text == "Test trajectory"

    def test_chunked_encoding_no_truncation(self):
        """With chunked encoding, text should NOT be truncated."""
        detector = MultiTaskDetectorV4(use_chunked_encoding=True)
        long_text = "x" * 20000
        record = {"trace": {"trajectory": long_text}}
        text = detector._extract_text(record)
        # Should contain the full text (plus prefix)
        assert "x" * 15000 in text

    def test_legacy_truncation_without_chunking(self):
        """Without chunked encoding, text should be truncated to 15k."""
        detector = MultiTaskDetectorV4(
            use_chunked_encoding=False,
            embedding_model="all-mpnet-base-v2",  # no e5 prefix
        )
        long_text = "x" * 20000
        record = {"trace": {"trajectory": long_text}}
        text = detector._extract_text(record)
        assert len(text) <= 15000

    def test_extract_text_empty_record(self):
        """Should handle empty record."""
        detector = MultiTaskDetectorV4()
        record = {}
        text = detector._extract_text(record)
        assert isinstance(text, str)

    def test_extract_text_none_trajectory(self):
        """Should handle None trajectory."""
        detector = MultiTaskDetectorV4()
        record = {"trace": {"trajectory": None}}
        text = detector._extract_text(record)
        assert isinstance(text, str)


# ============================================================================
# Label Extraction Tests
# ============================================================================

class TestLabelExtractionV4:
    """Tests for _get_labels."""

    def test_get_labels_from_annotations(self):
        """Should extract labels from MAST annotations."""
        detector = MultiTaskDetectorV4()
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
        detector = MultiTaskDetectorV4()
        record = {"mast_annotation": {}}
        labels = detector._get_labels(record)
        assert isinstance(labels, dict)

    def test_get_labels_missing_annotations(self):
        """Should handle missing annotations field."""
        detector = MultiTaskDetectorV4()
        record = {}
        labels = detector._get_labels(record)
        assert isinstance(labels, dict)

    def test_get_labels_boolean_values(self):
        """Should handle boolean annotation values."""
        detector = MultiTaskDetectorV4()
        record = {"mast_annotation": {"1.1": True, "1.3": False}}
        labels = detector._get_labels(record)
        assert labels.get("F1") is True
        assert labels.get("F3") is False

    def test_get_labels_full_mast_record(self):
        """Should handle all annotation codes."""
        detector = MultiTaskDetectorV4()
        record = {
            "mast_annotation": {
                code: 1 if i % 2 == 0 else 0
                for i, code in enumerate(ANNOTATION_MAP.keys())
            }
        }
        labels = detector._get_labels(record)
        assert isinstance(labels, dict)
        # Verify at least some labels are True and some False
        values = list(labels.values())
        assert any(v is True for v in values)
        assert any(v is False for v in values)


# ============================================================================
# AdaptiveThresholder Tests
# ============================================================================

class TestAdaptiveThresholder:
    """Tests for AdaptiveThresholder class."""

    def test_init_defaults(self):
        """Should have sensible defaults."""
        thresholder = AdaptiveThresholder()
        assert thresholder.k == 10
        assert thresholder.alpha == 0.5
        assert thresholder.min_threshold == 0.1
        assert thresholder.max_threshold == 0.9

    def test_init_custom(self):
        """Should accept custom parameters."""
        thresholder = AdaptiveThresholder(k=5, alpha=0.3, min_threshold=0.2, max_threshold=0.8)
        assert thresholder.k == 5
        assert thresholder.alpha == 0.3

    def test_predict_thresholds_not_fitted_raises(self):
        """Should raise ValueError when not fitted."""
        thresholder = AdaptiveThresholder()
        with pytest.raises(ValueError, match="not fitted"):
            thresholder.predict_thresholds(np.random.randn(5, 384))

    def test_fit_stores_data(self):
        """After fit, internal state should be populated."""
        try:
            from sklearn.neighbors import NearestNeighbors
        except ImportError:
            pytest.skip("sklearn not available")

        thresholder = AdaptiveThresholder(k=5)
        embeddings = np.random.randn(50, 384).astype(np.float32)
        labels = np.random.randint(0, 2, (50, 12)).astype(np.float32)

        thresholder.fit(embeddings, labels)

        assert thresholder.idf_weights is not None
        assert thresholder.train_embeddings is not None
        assert thresholder._knn is not None

    def test_idf_weights_shape(self):
        """IDF weights should match number of labels."""
        try:
            from sklearn.neighbors import NearestNeighbors
        except ImportError:
            pytest.skip("sklearn not available")

        thresholder = AdaptiveThresholder(k=5)
        n_labels = 12
        embeddings = np.random.randn(50, 384).astype(np.float32)
        labels = np.random.randint(0, 2, (50, n_labels)).astype(np.float32)

        thresholder.fit(embeddings, labels)

        assert thresholder.idf_weights.shape == (n_labels,)

    def test_predict_thresholds_shape(self):
        """Thresholds should have shape (n_samples, n_labels)."""
        try:
            from sklearn.neighbors import NearestNeighbors
        except ImportError:
            pytest.skip("sklearn not available")

        thresholder = AdaptiveThresholder(k=5)
        n_labels = 12
        embeddings = np.random.randn(50, 384).astype(np.float32)
        labels = np.random.randint(0, 2, (50, n_labels)).astype(np.float32)

        thresholder.fit(embeddings, labels)
        thresholds = thresholder.predict_thresholds(np.random.randn(10, 384).astype(np.float32))

        assert thresholds.shape == (10, n_labels)

    def test_predict_thresholds_bounded(self):
        """All thresholds should be within [min_threshold, max_threshold]."""
        try:
            from sklearn.neighbors import NearestNeighbors
        except ImportError:
            pytest.skip("sklearn not available")

        thresholder = AdaptiveThresholder(k=5, min_threshold=0.15, max_threshold=0.85)
        embeddings = np.random.randn(50, 384).astype(np.float32)
        labels = np.random.randint(0, 2, (50, 12)).astype(np.float32)

        thresholder.fit(embeddings, labels)
        thresholds = thresholder.predict_thresholds(np.random.randn(10, 384).astype(np.float32))

        assert np.all(thresholds >= 0.15)
        assert np.all(thresholds <= 0.85)

    def test_apply_returns_binary(self):
        """apply() should return binary 0/1 array."""
        try:
            from sklearn.neighbors import NearestNeighbors
        except ImportError:
            pytest.skip("sklearn not available")

        thresholder = AdaptiveThresholder(k=5)
        n_labels = 12
        embeddings = np.random.randn(50, 384).astype(np.float32)
        labels = np.random.randint(0, 2, (50, n_labels)).astype(np.float32)

        thresholder.fit(embeddings, labels)

        probs = np.random.rand(10, n_labels).astype(np.float32)
        query_embs = np.random.randn(10, 384).astype(np.float32)
        result = thresholder.apply(probs, query_embs)

        assert result.shape == (10, n_labels)
        assert set(np.unique(result)).issubset({0, 1})


# ============================================================================
# ChunkedTextEncoder Tests
# ============================================================================

class TestChunkedTextEncoder:
    """Tests for ChunkedTextEncoder."""

    def test_init_defaults(self):
        """Should initialize with correct defaults."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        encoder = ChunkedTextEncoder(device="cpu")
        assert encoder.chunk_size == 6000
        assert encoder.chunk_overlap == 1000
        assert encoder.max_chunks == 10
        assert encoder.pooling == "attention"

    def test_split_short_text(self):
        """Short text should produce 1 chunk."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        encoder = ChunkedTextEncoder(device="cpu")
        text = "Short text for testing." * 20  # ~460 chars
        chunks = encoder._split_into_chunks(text)
        assert len(chunks) == 1

    def test_split_long_text(self):
        """Long text should produce multiple chunks."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        encoder = ChunkedTextEncoder(chunk_size=6000, chunk_overlap=1000, device="cpu")
        text = "x" * 20000
        chunks = encoder._split_into_chunks(text)
        assert len(chunks) > 1
        assert len(chunks) <= 10

    def test_split_max_chunks_limit(self):
        """Should not exceed max_chunks."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        encoder = ChunkedTextEncoder(chunk_size=1000, chunk_overlap=100, max_chunks=3, device="cpu")
        text = "x" * 50000
        chunks = encoder._split_into_chunks(text)
        assert len(chunks) <= 3

    def test_encode_with_mock_embedder(self):
        """encode() should return correct shape with mocked embedder."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        encoder = ChunkedTextEncoder(device="cpu", pooling="mean")
        mock_embedder = MagicMock()
        mock_embedder.encode.return_value = np.random.randn(1, 384).astype(np.float32)
        encoder._embedder = mock_embedder

        result = encoder.encode(["Short text"], show_progress_bar=False)
        assert result.shape == (1, 384)

    def test_mean_pooling(self):
        """Mean pooling should average chunk embeddings."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        encoder = ChunkedTextEncoder(device="cpu", pooling="mean", chunk_size=100, chunk_overlap=10)
        mock_embedder = MagicMock()

        # Two chunks, return known embeddings
        chunk_embeds = np.array([[1.0, 2.0, 3.0], [3.0, 4.0, 5.0]], dtype=np.float32)
        mock_embedder.encode.return_value = chunk_embeds
        encoder._embedder = mock_embedder

        result = encoder.encode(["x" * 200], show_progress_bar=False)
        expected = chunk_embeds.mean(axis=0)
        np.testing.assert_array_almost_equal(result[0], expected)


# ============================================================================
# ContrastiveFineTuner Tests
# ============================================================================

class TestContrastiveFineTuner:
    """Tests for ContrastiveFineTuner."""

    def test_init_defaults(self):
        """Should initialize with correct defaults."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        finetuner = ContrastiveFineTuner(device="cpu")
        assert finetuner.model_name == "intfloat/e5-large-v2"
        assert finetuner.num_iterations == 10
        assert finetuner.batch_size == 8
        assert finetuner.learning_rate == 2e-5
        assert finetuner.use_hard_negatives is True

    def test_create_pairs_positive(self):
        """Should create positive pairs from same-label samples."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        finetuner = ContrastiveFineTuner(device="cpu", num_pairs_per_label=5, use_hard_negatives=False)
        np.random.seed(42)

        texts = [f"Text {i}" for i in range(20)]
        labels = np.zeros((20, 12), dtype=np.float32)
        labels[:10, 0] = 1  # First 10 samples positive for mode 0

        pairs, pair_labels = finetuner._create_pairs(texts, labels, mode_idx=0)

        assert len(pairs) > 0
        assert 1 in pair_labels  # Should have positive pairs

    def test_create_pairs_negative(self):
        """Should create negative pairs."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        finetuner = ContrastiveFineTuner(device="cpu", num_pairs_per_label=5, use_hard_negatives=False)
        np.random.seed(42)

        texts = [f"Text {i}" for i in range(20)]
        labels = np.zeros((20, 12), dtype=np.float32)
        labels[:10, 0] = 1

        pairs, pair_labels = finetuner._create_pairs(texts, labels, mode_idx=0)

        assert 0 in pair_labels  # Should have negative pairs

    def test_create_pairs_insufficient_positives(self):
        """Should return empty for insufficient positive samples."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        finetuner = ContrastiveFineTuner(device="cpu")

        texts = [f"Text {i}" for i in range(20)]
        labels = np.zeros((20, 12), dtype=np.float32)
        labels[0, 0] = 1  # Only 1 positive — need at least 2

        pairs, pair_labels = finetuner._create_pairs(texts, labels, mode_idx=0)

        assert pairs == []
        assert pair_labels == []


# ============================================================================
# Loss Function Tests
# ============================================================================

class TestLossFunctions:
    """Tests for loss function factories."""

    def test_create_asymmetric_loss(self):
        """ASL should produce a scalar loss tensor."""
        try:
            import torch
            from app.detection_enterprise.ml_detector_v4 import _create_asymmetric_loss
        except ImportError:
            pytest.skip("PyTorch not available")

        loss_fn = _create_asymmetric_loss()
        logits = torch.randn(8, 12)
        targets = torch.randint(0, 2, (8, 12)).float()
        loss = loss_fn(logits, targets)

        assert loss.dim() == 0  # scalar
        assert loss.item() >= 0

    def test_create_focal_loss(self):
        """Focal loss should produce a scalar loss tensor."""
        try:
            import torch
            from app.detection_enterprise.ml_detector_v4 import _create_focal_loss
        except ImportError:
            pytest.skip("PyTorch not available")

        loss_fn = _create_focal_loss()
        logits = torch.randn(8, 12)
        targets = torch.randint(0, 2, (8, 12)).float()
        loss = loss_fn(logits, targets)

        assert loss.dim() == 0
        assert loss.item() >= 0

    def test_create_label_gcn(self):
        """Label GCN should output correct shape."""
        try:
            import torch
            from app.detection_enterprise.ml_detector_v4 import _create_label_gcn
        except ImportError:
            pytest.skip("PyTorch not available")

        gcn = _create_label_gcn(num_labels=12, embed_dim=128, hidden_dim=256)
        output = gcn()

        assert output.shape == (12, 128)

    def test_label_gcn_cooccurrence_init(self):
        """GCN adjacency should be initializable from co-occurrence."""
        try:
            import torch
            from app.detection_enterprise.ml_detector_v4 import _create_label_gcn
        except ImportError:
            pytest.skip("PyTorch not available")

        gcn = _create_label_gcn(num_labels=12, embed_dim=128, hidden_dim=256)
        labels_matrix = np.random.randint(0, 2, (100, 12)).astype(np.float32)

        gcn.init_from_cooccurrence(labels_matrix)

        # Adjacency should have been updated
        adj = gcn.adj_raw.detach().numpy()
        assert adj.shape == (12, 12)

    def test_focal_loss_with_label_smoothing(self):
        """Focal loss with smoothing should differ from without."""
        try:
            import torch
            from app.detection_enterprise.ml_detector_v4 import _create_focal_loss
        except ImportError:
            pytest.skip("PyTorch not available")

        loss_no_smooth = _create_focal_loss(smoothing=0.0)
        loss_smooth = _create_focal_loss(smoothing=0.1)

        torch.manual_seed(42)
        logits = torch.randn(8, 12)
        targets = torch.randint(0, 2, (8, 12)).float()

        l1 = loss_no_smooth(logits, targets).item()
        l2 = loss_smooth(logits, targets).item()

        # They should produce different values
        assert l1 != l2


# ============================================================================
# Training Tests (Mocked)
# ============================================================================

class TestTrainingMockedV4:
    """Tests for training workflow with mocked dependencies."""

    @pytest.fixture
    def mock_records(self):
        """Create mock training records."""
        return [
            {
                "trace": {"trajectory": f"Test trajectory {i} with agent actions"},
                "mast_annotation": {
                    "1.1": i % 2,
                    "1.3": (i + 1) % 2,
                    "2.1": i % 3 == 0,
                }
            }
            for i in range(20)
        ]

    def test_train_sets_is_trained(self, mock_records):
        """After training, is_trained should be True."""
        try:
            import torch
        except ImportError:
            pytest.skip("PyTorch not available")

        detector = MultiTaskDetectorV4(
            epochs=1,
            hidden_dims=[32],
            use_label_gcn=False,
            use_contrastive_finetuning=False,
            use_adaptive_thresholding=False,
            cv_folds=2,
        )

        with patch.object(detector, '_get_encoder') as mock_encoder:
            mock_enc = MagicMock()
            mock_enc.encode = MagicMock(
                return_value=np.random.randn(20, 384).astype(np.float32)
            )
            mock_encoder.return_value = mock_enc

            try:
                result = detector.train(mock_records)
                assert detector.is_trained is True
                assert isinstance(result, dict)
            except (RuntimeError, Exception) as e:
                if "not enough" in str(e).lower() or "empty" in str(e).lower():
                    pytest.skip(f"Training data insufficient: {e}")
                raise

    def test_predict_requires_trained_model(self):
        """Should raise error if not trained."""
        detector = MultiTaskDetectorV4()
        records = [{"trace": {"trajectory": "Test"}}]

        with pytest.raises(RuntimeError, match="not trained"):
            detector.predict_batch(records)


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCasesV4:
    """Tests for edge cases specific to V4."""

    def test_empty_trajectory(self):
        """Should handle empty trajectory."""
        detector = MultiTaskDetectorV4()
        record = {"trace": {"trajectory": ""}}
        text = detector._extract_text(record)
        assert isinstance(text, str)

    def test_none_trajectory(self):
        """Should handle None trajectory."""
        detector = MultiTaskDetectorV4()
        record = {"trace": {"trajectory": None}}
        text = detector._extract_text(record)
        assert isinstance(text, str)

    def test_string_annotation_values(self):
        """Should handle string annotation values."""
        detector = MultiTaskDetectorV4()
        record = {"mast_annotation": {"1.1": "1", "1.3": "0"}}
        labels = detector._get_labels(record)
        assert isinstance(labels, dict)

    def test_v4_default_model_is_e5(self):
        """V4 should default to e5-large-v2 (not mpnet like V3)."""
        detector = MultiTaskDetectorV4()
        assert "e5" in detector.embedding_model
        assert detector.embedding_model == "intfloat/e5-large-v2"

    def test_v4_default_loss_is_focal(self):
        """V4 should default to focal loss (not ASL — ASL caused over-prediction)."""
        detector = MultiTaskDetectorV4()
        assert detector.loss_type == "focal"
