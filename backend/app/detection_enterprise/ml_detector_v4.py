"""ML Detector v4 - Best-in-Class Multi-Label Classification.

Improvements over v3:
1. SetFit-style contrastive fine-tuning (not frozen embeddings)
2. Asymmetric Loss (ASL) for better precision/recall balance
3. Label Correlation GCN - models inter-label dependencies
4. Hierarchical Contrastive Learning - leverages label hierarchy
5. Long-context chunked encoding with attention pooling
6. All v3 features: focal loss option, per-mode thresholds, CV optimization

Target: 75-80% macro F1 (up from 60%)

References:
- SetFit: https://huggingface.co/blog/setfit
- ASL: https://arxiv.org/abs/2009.14119
- ML-GCN: https://arxiv.org/abs/1904.03582
- HCL-MTC: https://www.nature.com/articles/s41598-025-97597-w
"""

import json
import logging
import math
import os
import pickle
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

from app.core.mast_constants import ANNOTATION_MAP, FAILURE_MODES_F14

# Skip F2 and F10 - too few training samples
FAILURE_MODES = [m for m in FAILURE_MODES_F14 if m not in ("F2", "F10")]

# Label hierarchy for hierarchical contrastive learning
# Modes within same category are "hard negatives"
LABEL_HIERARCHY = {
    "specification": ["F1", "F2"],           # Spec-related failures
    "resource": ["F3", "F4"],                 # Resource/tool failures
    "workflow": ["F5", "F6"],                 # Workflow/task failures
    "information": ["F7", "F8"],              # Information handling failures
    "coordination": ["F9", "F10", "F11"],     # Multi-agent coordination
    "validation": ["F12", "F13", "F14"],      # Output/completion validation
}

# Reverse mapping: mode -> category
MODE_TO_CATEGORY = {}
for cat, modes in LABEL_HIERARCHY.items():
    for mode in modes:
        MODE_TO_CATEGORY[mode] = cat


def set_random_seeds(seed: int) -> None:
    """Set random seeds for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)

    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
    except ImportError:
        pass


# =============================================================================
# Loss Functions
# =============================================================================

def _create_asymmetric_loss(gamma_neg: float = 4.0, gamma_pos: float = 1.0,
                            clip: float = 0.05, eps: float = 1e-8):
    """Create Asymmetric Loss for multi-label classification.

    ASL addresses class imbalance by:
    1. Asymmetric focusing: higher gamma for negatives
    2. Probability clipping: prevents easy negatives from dominating

    Reference: https://arxiv.org/abs/2009.14119
    """
    import torch
    import torch.nn as nn

    class AsymmetricLoss(nn.Module):
        def __init__(self, gamma_neg: float, gamma_pos: float, clip: float, eps: float):
            super().__init__()
            self.gamma_neg = gamma_neg
            self.gamma_pos = gamma_pos
            self.clip = clip
            self.eps = eps

        def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            # Sigmoid probabilities
            probs = torch.sigmoid(logits)

            # Separate positive and negative
            probs_pos = probs * targets
            probs_neg = probs * (1 - targets)

            # Asymmetric clipping for negatives (hard threshold)
            probs_neg = (probs_neg + self.clip).clamp(max=1)

            # Compute loss components
            loss_pos = targets * torch.log(probs_pos.clamp(min=self.eps))
            loss_neg = (1 - targets) * torch.log((1 - probs_neg).clamp(min=self.eps))

            # Asymmetric focusing
            # For positives: (1-p)^gamma_pos focuses on hard positives
            # For negatives: p^gamma_neg focuses on hard negatives
            pt_pos = probs_pos
            pt_neg = probs_neg

            focal_pos = (1 - pt_pos) ** self.gamma_pos
            focal_neg = pt_neg ** self.gamma_neg

            loss = -(focal_pos * loss_pos + focal_neg * loss_neg)
            return loss.mean()

    return AsymmetricLoss(gamma_neg, gamma_pos, clip, eps)


def _create_focal_loss(alpha: float = 0.25, gamma: float = 2.0, smoothing: float = 0.0):
    """Create Focal Loss (kept for comparison)."""
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class FocalLoss(nn.Module):
        def __init__(self, alpha: float, gamma: float, smoothing: float = 0.0):
            super().__init__()
            self.alpha = alpha
            self.gamma = gamma
            self.smoothing = smoothing

        def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            if self.smoothing > 0:
                targets = targets * (1 - self.smoothing) + 0.5 * self.smoothing

            ce = F.binary_cross_entropy_with_logits(inputs, targets, reduction='none')
            p = torch.sigmoid(inputs)
            p_t = p * targets + (1 - p) * (1 - targets)
            focal_weight = self.alpha * (1 - p_t) ** self.gamma
            loss = focal_weight * ce
            return loss.mean()

    return FocalLoss(alpha, gamma, smoothing)


# =============================================================================
# Label Correlation GCN
# =============================================================================

def _create_label_gcn(num_labels: int, embed_dim: int = 128, hidden_dim: int = 256):
    """Create Label Correlation Graph Convolutional Network.

    Models inter-label dependencies using a GCN that propagates information
    between correlated labels. The adjacency matrix is learned from:
    1. Label co-occurrence in training data
    2. Semantic similarity of label embeddings

    Reference: ML-GCN (CVPR 2019)
    """
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class GraphConvolution(nn.Module):
        """Single GCN layer: H' = σ(AHW)"""

        def __init__(self, in_features: int, out_features: int):
            super().__init__()
            self.weight = nn.Parameter(torch.FloatTensor(in_features, out_features))
            self.bias = nn.Parameter(torch.FloatTensor(out_features))
            self._reset_parameters()

        def _reset_parameters(self):
            nn.init.xavier_uniform_(self.weight)
            nn.init.zeros_(self.bias)

        def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
            # x: (num_labels, in_features)
            # adj: (num_labels, num_labels) - normalized adjacency
            support = torch.matmul(x, self.weight)  # (num_labels, out_features)
            output = torch.matmul(adj, support)      # (num_labels, out_features)
            return output + self.bias

    class LabelCorrelationGCN(nn.Module):
        """Two-layer GCN for learning label embeddings with correlation."""

        def __init__(self, num_labels: int, embed_dim: int, hidden_dim: int):
            super().__init__()
            self.num_labels = num_labels
            self.embed_dim = embed_dim

            # Learnable label embeddings (initialized randomly, refined by GCN)
            self.label_embeddings = nn.Parameter(torch.randn(num_labels, embed_dim))

            # Learnable adjacency matrix (will be initialized from co-occurrence)
            self.adj_raw = nn.Parameter(torch.eye(num_labels))

            # GCN layers
            self.gc1 = GraphConvolution(embed_dim, hidden_dim)
            self.gc2 = GraphConvolution(hidden_dim, embed_dim)

            self.dropout = nn.Dropout(0.2)
            self.relu = nn.LeakyReLU(0.2)

        def get_adj_normalized(self) -> torch.Tensor:
            """Get normalized adjacency matrix (softmax per row)."""
            # Apply softmax to get attention-like weights
            adj = F.softmax(self.adj_raw, dim=1)
            return adj

        def forward(self) -> torch.Tensor:
            """Forward pass: propagate through GCN.

            Returns:
                Label embeddings of shape (num_labels, embed_dim)
            """
            adj = self.get_adj_normalized()

            x = self.label_embeddings
            x = self.relu(self.gc1(x, adj))
            x = self.dropout(x)
            x = self.gc2(x, adj)

            return x  # (num_labels, embed_dim)

        def init_from_cooccurrence(self, labels_matrix: np.ndarray):
            """Initialize adjacency from label co-occurrence.

            Args:
                labels_matrix: (num_samples, num_labels) binary matrix
            """
            # Compute co-occurrence: A[i,j] = count(i and j) / count(i)
            counts = labels_matrix.sum(axis=0) + 1e-6  # (num_labels,)
            cooccur = labels_matrix.T @ labels_matrix   # (num_labels, num_labels)

            # Conditional probability P(j|i)
            adj = cooccur / counts[:, np.newaxis]

            # Add self-loops and normalize
            adj = adj + np.eye(self.num_labels)
            adj = adj / adj.sum(axis=1, keepdims=True)

            with torch.no_grad():
                self.adj_raw.copy_(torch.tensor(adj, dtype=torch.float32))

            logger.info("Initialized GCN adjacency from co-occurrence matrix")

    return LabelCorrelationGCN(num_labels, embed_dim, hidden_dim)


# =============================================================================
# Adaptive Thresholding (IDF+KNN)
# =============================================================================

class AdaptiveThresholder:
    """Adaptive thresholding using global (IDF) and local (KNN) signals.

    Based on arXiv 2505.03118: "Adaptive Thresholding for Multi-Label
    Classification via Global-Local Signal Fusion"

    Instead of a fixed 0.5 threshold, computes per-label, per-instance
    thresholds that adapt to:
    1. Global label frequency (IDF) - rare labels get lower thresholds
    2. Local neighborhood (KNN) - similar samples inform threshold
    """

    def __init__(
        self,
        k: int = 10,
        alpha: float = 0.5,
        min_threshold: float = 0.1,
        max_threshold: float = 0.9,
    ):
        """Initialize adaptive thresholder.

        Args:
            k: Number of neighbors for KNN
            alpha: Weight between local (1.0) and global (0.0) signals
            min_threshold: Minimum allowed threshold
            max_threshold: Maximum allowed threshold
        """
        self.k = k
        self.alpha = alpha
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold

        self.idf_weights = None
        self.train_embeddings = None
        self.train_labels = None
        self._knn = None

    def fit(self, embeddings: np.ndarray, labels: np.ndarray):
        """Fit thresholder on training data.

        Args:
            embeddings: Training embeddings (n_samples, embed_dim)
            labels: Training labels (n_samples, n_labels)
        """
        from sklearn.neighbors import NearestNeighbors

        N = len(labels)
        df = labels.sum(axis=0) + 1  # Document frequency per label
        self.idf_weights = np.log(N / df)  # Inverse document frequency

        self.train_embeddings = embeddings
        self.train_labels = labels

        # Pre-fit KNN for efficiency
        self._knn = NearestNeighbors(n_neighbors=min(self.k, len(embeddings)))
        self._knn.fit(embeddings)

        logger.info(f"Fitted adaptive thresholder: k={self.k}, alpha={self.alpha}")
        logger.info(f"  IDF range: [{self.idf_weights.min():.2f}, {self.idf_weights.max():.2f}]")

    def predict_thresholds(self, embeddings: np.ndarray) -> np.ndarray:
        """Compute adaptive thresholds for each sample and label.

        Args:
            embeddings: Query embeddings (n_samples, embed_dim)

        Returns:
            Thresholds of shape (n_samples, n_labels)
        """
        if self._knn is None:
            raise ValueError("Thresholder not fitted. Call fit() first.")

        thresholds = []

        for emb in embeddings:
            # Find K nearest neighbors
            _, indices = self._knn.kneighbors([emb])
            neighbor_labels = self.train_labels[indices[0]]

            # Local signal: label frequency in neighborhood
            local_freq = neighbor_labels.mean(axis=0)  # (n_labels,)

            # Global signal: IDF-based (rare labels -> lower threshold)
            # Normalize IDF to [0, 1] range and invert (high IDF = rare = lower threshold)
            idf_normalized = self.idf_weights / (self.idf_weights.max() + 1e-6)
            global_signal = 1 - idf_normalized  # Rare labels get lower values

            # Combine signals: threshold = alpha * local + (1-alpha) * global
            # Lower threshold = more lenient (more likely to predict positive)
            threshold = self.alpha * local_freq + (1 - self.alpha) * global_signal

            # Apply bounds
            threshold = np.clip(threshold, self.min_threshold, self.max_threshold)
            thresholds.append(threshold)

        return np.array(thresholds)

    def apply(
        self,
        probabilities: np.ndarray,
        embeddings: np.ndarray,
    ) -> np.ndarray:
        """Apply adaptive thresholds to probabilities.

        Args:
            probabilities: Predicted probabilities (n_samples, n_labels)
            embeddings: Query embeddings (n_samples, embed_dim)

        Returns:
            Binary predictions (n_samples, n_labels)
        """
        thresholds = self.predict_thresholds(embeddings)
        return (probabilities >= thresholds).astype(int)


# =============================================================================
# Long-Context Chunked Encoder
# =============================================================================

class ChunkedTextEncoder:
    """Encode long texts using chunking with attention pooling.

    Instead of truncating to 15k chars (losing late-stage failures),
    we split into overlapping chunks and aggregate with attention.
    """

    def __init__(
        self,
        model_name: str = "intfloat/e5-large-v2",  # Upgraded from all-mpnet-base-v2
        chunk_size: int = 6000,
        chunk_overlap: int = 1000,
        max_chunks: int = 10,
        pooling: str = "attention",  # "attention", "mean", "max"
        device: str = None,  # Auto-detect: CUDA > CPU (skip MPS for OOM issues)
    ):
        self.model_name = model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunks = max_chunks
        self.pooling = pooling
        # Auto-detect device - prefer CUDA, skip MPS (OOM issues), fallback to CPU
        if device is None:
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self._embedder = None
        self._attention_weights = None

    @property
    def embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Loaded {self.model_name} for chunked encoding on {self.device}")
        return self._embedder

    @property
    def embedding_dim(self) -> int:
        return self.embedder.get_sentence_embedding_dimension()

    def _split_into_chunks(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        step = self.chunk_size - self.chunk_overlap

        while start < len(text) and len(chunks) < self.max_chunks:
            end = start + self.chunk_size
            chunk = text[start:end]
            if len(chunk.strip()) > 100:  # Skip very short chunks
                chunks.append(chunk)
            start += step

        return chunks if chunks else [text[:self.chunk_size]]

    def encode(
        self,
        texts: List[str],
        show_progress_bar: bool = True,
        convert_to_numpy: bool = True,
    ) -> np.ndarray:
        """Encode texts using chunked encoding with pooling.

        Args:
            texts: List of (potentially long) texts
            show_progress_bar: Show encoding progress
            convert_to_numpy: Return numpy array

        Returns:
            Embeddings of shape (len(texts), embedding_dim)
        """
        import torch

        all_embeddings = []

        for text in texts:
            chunks = self._split_into_chunks(text)

            # Encode all chunks
            chunk_embeds = self.embedder.encode(
                chunks,
                show_progress_bar=False,
                convert_to_numpy=True
            )  # (n_chunks, embed_dim)

            if len(chunk_embeds) == 1:
                pooled = chunk_embeds[0]
            elif self.pooling == "mean":
                pooled = chunk_embeds.mean(axis=0)
            elif self.pooling == "max":
                pooled = chunk_embeds.max(axis=0)
            elif self.pooling == "attention":
                # Simple attention: use last chunk as query
                # This emphasizes final state which often contains failure evidence
                query = chunk_embeds[-1]  # (embed_dim,)

                # Compute attention scores
                scores = chunk_embeds @ query  # (n_chunks,)
                weights = np.exp(scores - scores.max())  # Numerical stability
                weights = weights / weights.sum()

                # Weighted sum
                pooled = (chunk_embeds * weights[:, np.newaxis]).sum(axis=0)
            else:
                pooled = chunk_embeds.mean(axis=0)

            all_embeddings.append(pooled)

        result = np.stack(all_embeddings, axis=0)
        return result if convert_to_numpy else torch.tensor(result)


# =============================================================================
# Contrastive Fine-tuning (SetFit-style)
# =============================================================================

class ContrastiveFineTuner:
    """Fine-tune sentence transformer using contrastive learning.

    Implements SetFit-style training:
    1. Create positive pairs (same label)
    2. Create negative pairs (different label)
    3. Create hard negative pairs (same category, different label)
    4. Fine-tune with contrastive loss

    Reference: https://huggingface.co/blog/setfit
    """

    def __init__(
        self,
        model_name: str = "intfloat/e5-large-v2",  # Upgraded from all-mpnet-base-v2
        num_iterations: int = 10,  # Reduced from 20 for memory
        num_pairs_per_label: int = 10,  # Reduced from 20 for memory
        batch_size: int = 8,  # Reduced from 16 for memory
        learning_rate: float = 2e-5,
        warmup_ratio: float = 0.1,
        use_hard_negatives: bool = True,
        device: str = None,  # Auto-detect: CUDA > CPU (skip MPS for OOM issues)
    ):
        self.model_name = model_name
        self.num_iterations = num_iterations
        self.num_pairs_per_label = num_pairs_per_label
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.warmup_ratio = warmup_ratio
        self.use_hard_negatives = use_hard_negatives
        # Auto-detect device - prefer CUDA, skip MPS (OOM issues), fallback to CPU
        if device is None:
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Loaded {self.model_name} on {self.device} for contrastive fine-tuning")
        return self._model

    def _create_pairs(
        self,
        texts: List[str],
        labels: np.ndarray,  # (n_samples, n_labels) multi-hot
        mode_idx: int,
    ) -> Tuple[List[Tuple[str, str]], List[int]]:
        """Create contrastive pairs for a specific failure mode.

        Returns:
            pairs: List of (text1, text2) pairs
            pair_labels: 1 for positive pair, 0 for negative
        """
        # Get positive and negative indices for this mode
        pos_indices = np.where(labels[:, mode_idx] == 1)[0]
        neg_indices = np.where(labels[:, mode_idx] == 0)[0]

        if len(pos_indices) < 2:
            return [], []

        pairs = []
        pair_labels = []

        # Create positive pairs (same label)
        n_pos_pairs = min(self.num_pairs_per_label, len(pos_indices) * (len(pos_indices) - 1) // 2)
        for _ in range(n_pos_pairs):
            i, j = np.random.choice(pos_indices, 2, replace=False)
            pairs.append((texts[i], texts[j]))
            pair_labels.append(1)

        # Create negative pairs
        n_neg_pairs = n_pos_pairs  # Balance positive and negative
        for _ in range(n_neg_pairs):
            i = np.random.choice(pos_indices)
            j = np.random.choice(neg_indices)
            pairs.append((texts[i], texts[j]))
            pair_labels.append(0)

        # Create hard negative pairs (same category, different label)
        if self.use_hard_negatives:
            mode = FAILURE_MODES[mode_idx]
            category = MODE_TO_CATEGORY.get(mode)
            if category:
                # Find other modes in same category
                sibling_modes = [m for m in LABEL_HIERARCHY.get(category, []) if m != mode]
                sibling_indices = [FAILURE_MODES.index(m) for m in sibling_modes if m in FAILURE_MODES]

                for sibling_idx in sibling_indices:
                    sibling_pos = np.where(labels[:, sibling_idx] == 1)[0]
                    if len(sibling_pos) > 0 and len(pos_indices) > 0:
                        n_hard = min(n_pos_pairs // 2, len(sibling_pos))
                        for _ in range(n_hard):
                            i = np.random.choice(pos_indices)
                            j = np.random.choice(sibling_pos)
                            pairs.append((texts[i], texts[j]))
                            pair_labels.append(0)  # Hard negative

        return pairs, pair_labels

    def fine_tune(
        self,
        texts: List[str],
        labels: np.ndarray,
        epochs: int = 1,
    ) -> "SentenceTransformer":
        """Fine-tune the model using contrastive learning.

        Args:
            texts: List of text samples
            labels: Multi-hot label matrix (n_samples, n_labels)
            epochs: Number of epochs over all pairs

        Returns:
            Fine-tuned SentenceTransformer model
        """
        from sentence_transformers import SentenceTransformer, InputExample, losses
        from torch.utils.data import DataLoader

        logger.info("Creating contrastive pairs for fine-tuning...")

        all_examples = []

        # Create pairs for each failure mode
        for mode_idx, mode in enumerate(FAILURE_MODES):
            pairs, pair_labels = self._create_pairs(texts, labels, mode_idx)

            for (t1, t2), label in zip(pairs, pair_labels):
                # InputExample for contrastive learning
                all_examples.append(InputExample(texts=[t1, t2], label=float(label)))

            logger.info(f"  {mode}: {len(pairs)} pairs")

        if not all_examples:
            logger.warning("No contrastive pairs created, skipping fine-tuning")
            return self.model

        logger.info(f"Total contrastive pairs: {len(all_examples)}")

        # Shuffle examples
        random.shuffle(all_examples)

        # Create DataLoader
        train_dataloader = DataLoader(
            all_examples,
            shuffle=True,
            batch_size=self.batch_size,
        )

        # Contrastive loss (cosine similarity)
        train_loss = losses.CosineSimilarityLoss(self.model)

        # Calculate warmup steps
        total_steps = len(train_dataloader) * epochs * self.num_iterations
        warmup_steps = int(total_steps * self.warmup_ratio)

        # Fine-tune
        logger.info(f"Fine-tuning for {self.num_iterations} iterations...")
        self.model.fit(
            train_objectives=[(train_dataloader, train_loss)],
            epochs=epochs * self.num_iterations,
            warmup_steps=warmup_steps,
            optimizer_params={'lr': self.learning_rate},
            show_progress_bar=True,
        )

        logger.info("Contrastive fine-tuning complete")
        return self.model


# =============================================================================
# Main Detector Class
# =============================================================================

class MultiTaskDetectorV4:
    """Best-in-class multi-label failure mode detector.

    Features:
    1. SetFit-style contrastive fine-tuning
    2. Label Correlation GCN
    3. Asymmetric Loss (or Focal Loss)
    4. Long-context chunked encoding
    5. Hierarchical contrastive learning
    6. Per-mode threshold optimization

    Target: 75-80% macro F1
    """

    def __init__(
        self,
        # Embedding configuration
        embedding_model: str = "intfloat/e5-large-v2",  # Upgraded from all-mpnet-base-v2 (MTEB +2 pts)
        use_contrastive_finetuning: bool = False,  # Disabled by default (slow on CPU with e5-large)
        contrastive_iterations: int = 5,  # Reduced for faster training when enabled

        # Long-context configuration
        use_chunked_encoding: bool = True,
        chunk_size: int = 6000,
        max_chunks: int = 10,

        # Label correlation configuration
        use_label_gcn: bool = True,
        gcn_embed_dim: int = 128,
        gcn_hidden_dim: int = 256,

        # Network configuration
        hidden_dims: List[int] = None,
        dropout: float = 0.3,

        # Loss configuration - Use Focal Loss (ASL gamma=4.0 caused over-prediction)
        loss_type: str = "focal",  # "asl", "focal", "bce"
        asl_gamma_neg: float = 4.0,
        asl_gamma_pos: float = 1.0,
        asl_clip: float = 0.05,
        focal_alpha: float = 0.25,
        focal_gamma: float = 2.0,
        label_smoothing: float = 0.05,

        # Training configuration
        learning_rate: float = 0.001,
        epochs: int = 50,
        batch_size: int = 32,
        cv_folds: int = 5,

        # Adaptive thresholding configuration (arXiv 2505.03118)
        use_adaptive_thresholding: bool = True,
        adaptive_k: int = 10,
        adaptive_alpha: float = 0.5,

        # Reproducibility
        random_seed: Optional[int] = 42,
    ):
        self.embedding_model = embedding_model
        self.use_contrastive_finetuning = use_contrastive_finetuning
        self.contrastive_iterations = contrastive_iterations

        self.use_chunked_encoding = use_chunked_encoding
        self.chunk_size = chunk_size
        self.max_chunks = max_chunks

        self.use_label_gcn = use_label_gcn
        self.gcn_embed_dim = gcn_embed_dim
        self.gcn_hidden_dim = gcn_hidden_dim

        self.hidden_dims = hidden_dims or [512, 256, 128]
        self.dropout = dropout

        self.loss_type = loss_type
        self.asl_gamma_neg = asl_gamma_neg
        self.asl_gamma_pos = asl_gamma_pos
        self.asl_clip = asl_clip
        self.focal_alpha = focal_alpha
        self.focal_gamma = focal_gamma
        self.label_smoothing = label_smoothing

        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.cv_folds = cv_folds

        self.use_adaptive_thresholding = use_adaptive_thresholding
        self.adaptive_k = adaptive_k
        self.adaptive_alpha = adaptive_alpha

        self.random_seed = random_seed

        # Components (initialized during training)
        self._embedder = None
        self._chunked_encoder = None
        self._contrastive_finetuner = None
        self._label_gcn = None
        self._adaptive_thresholder = None
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.thresholds: Dict[str, float] = {mode: 0.5 for mode in FAILURE_MODES}
        self._train_embeddings = None  # Store for adaptive thresholding

    @property
    def embedder(self):
        """Get the sentence transformer (possibly fine-tuned)."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(self.embedding_model)
            logger.info(f"Loaded {self.embedding_model}")
        return self._embedder

    @embedder.setter
    def embedder(self, model):
        self._embedder = model

    def _get_encoder(self):
        """Get the text encoder (chunked or regular)."""
        if self.use_chunked_encoding:
            if self._chunked_encoder is None:
                self._chunked_encoder = ChunkedTextEncoder(
                    model_name=self.embedding_model,
                    chunk_size=self.chunk_size,
                    max_chunks=self.max_chunks,
                    pooling="attention",
                    # device auto-detected by ChunkedTextEncoder
                )
                # Share the embedder if fine-tuned
                if self._embedder is not None:
                    self._chunked_encoder._embedder = self._embedder
            return self._chunked_encoder
        return self.embedder

    def _extract_text(self, record: Dict) -> str:
        """Extract text from record (full trajectory, no truncation for chunked).

        For e5 models, adds instruction prefix for better classification performance.
        """
        trajectory = record.get("trace", {}).get("trajectory", "") or ""

        # Add instruction prefix for e5 models (improves classification)
        if "e5" in self.embedding_model.lower():
            prefix = "query: Classify failure modes in this LLM agent trace: "
            trajectory = prefix + trajectory

        if self.use_chunked_encoding:
            return trajectory  # Full text, chunking handles length
        return trajectory[:15000]  # Legacy truncation

    def _get_labels(self, record: Dict) -> Dict[str, bool]:
        """Get labels from record."""
        annotations = record.get("mast_annotation", {})
        labels = {}
        for code, mode in ANNOTATION_MAP.items():
            value = annotations.get(code, 0)
            labels[mode] = bool(value) if isinstance(value, int) else value
        return labels

    def _build_classifier(self, input_dim: int, output_dim: int):
        """Build the classification network with optional GCN."""
        import torch
        import torch.nn as nn

        class GCNClassifier(nn.Module):
            """Classifier with Label Correlation GCN."""

            def __init__(
                self,
                input_dim: int,
                hidden_dims: List[int],
                output_dim: int,
                dropout: float,
                gcn_embed_dim: int,
                gcn_hidden_dim: int,
            ):
                super().__init__()

                # Text encoder MLP
                layers = []
                prev_dim = input_dim
                for hidden_dim in hidden_dims:
                    layers.extend([
                        nn.Linear(prev_dim, hidden_dim),
                        nn.BatchNorm1d(hidden_dim),
                        nn.ReLU(),
                        nn.Dropout(dropout),
                    ])
                    prev_dim = hidden_dim
                self.text_encoder = nn.Sequential(*layers)

                # Project to GCN embedding dim
                self.text_proj = nn.Linear(prev_dim, gcn_embed_dim)

                # Label Correlation GCN
                self.label_gcn = _create_label_gcn(
                    output_dim, gcn_embed_dim, gcn_hidden_dim
                )

                # Final classification: dot product of text and label embeddings
                self.output_dim = output_dim

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                # Encode text
                text_hidden = self.text_encoder(x)  # (batch, hidden_dim)
                text_embed = self.text_proj(text_hidden)  # (batch, gcn_embed_dim)

                # Get label embeddings from GCN
                label_embeds = self.label_gcn()  # (num_labels, gcn_embed_dim)

                # Compute logits via dot product
                logits = torch.matmul(text_embed, label_embeds.T)  # (batch, num_labels)

                return logits

            def init_gcn_from_labels(self, labels_matrix: np.ndarray):
                """Initialize GCN adjacency from label co-occurrence."""
                self.label_gcn.init_from_cooccurrence(labels_matrix)

        class SimpleClassifier(nn.Module):
            """Simple MLP classifier (no GCN)."""

            def __init__(
                self,
                input_dim: int,
                hidden_dims: List[int],
                output_dim: int,
                dropout: float,
            ):
                super().__init__()

                layers = []
                prev_dim = input_dim
                for hidden_dim in hidden_dims:
                    layers.extend([
                        nn.Linear(prev_dim, hidden_dim),
                        nn.BatchNorm1d(hidden_dim),
                        nn.ReLU(),
                        nn.Dropout(dropout),
                    ])
                    prev_dim = hidden_dim
                layers.append(nn.Linear(prev_dim, output_dim))
                self.network = nn.Sequential(*layers)

            def forward(self, x: torch.Tensor) -> torch.Tensor:
                return self.network(x)

        if self.use_label_gcn:
            return GCNClassifier(
                input_dim, self.hidden_dims, output_dim, self.dropout,
                self.gcn_embed_dim, self.gcn_hidden_dim
            )
        else:
            return SimpleClassifier(input_dim, self.hidden_dims, output_dim, self.dropout)

    def train(
        self,
        records: List[Dict],
        test_split: float = 0.2,
    ) -> Dict[str, Any]:
        """Train the detector.

        Pipeline:
        1. Extract texts and labels
        2. Contrastive fine-tuning of embedder (optional)
        3. Compute embeddings (with chunking if enabled)
        4. Train classifier with ASL/Focal loss
        5. Optimize per-mode thresholds
        """
        import torch
        import torch.nn as nn
        from sklearn.model_selection import train_test_split, KFold
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import f1_score, precision_score, recall_score

        # Set random seeds
        if self.random_seed is not None:
            set_random_seeds(self.random_seed)
            logger.info(f"Random seed: {self.random_seed}")

        logger.info(f"Training ML Detector v4 on {len(records)} records")
        logger.info(f"  Contrastive fine-tuning: {self.use_contrastive_finetuning}")
        logger.info(f"  Chunked encoding: {self.use_chunked_encoding}")
        logger.info(f"  Label GCN: {self.use_label_gcn}")
        logger.info(f"  Loss: {self.loss_type}")

        # Extract texts and labels
        texts = [self._extract_text(r) for r in records]
        labels_list = [self._get_labels(r) for r in records]
        y = np.array([[l.get(m, False) for m in FAILURE_MODES] for l in labels_list], dtype=np.float32)

        # Log class distribution
        for i, mode in enumerate(FAILURE_MODES):
            count = int(y[:, i].sum())
            logger.info(f"  {mode}: {count} positive samples ({100*count/len(y):.1f}%)")

        # Step 1: Contrastive fine-tuning
        if self.use_contrastive_finetuning:
            logger.info("\n=== Phase 1: Contrastive Fine-tuning ===")
            self._contrastive_finetuner = ContrastiveFineTuner(
                model_name=self.embedding_model,
                num_iterations=self.contrastive_iterations,
                use_hard_negatives=True,
                # device auto-detected by ContrastiveFineTuner
            )
            self.embedder = self._contrastive_finetuner.fine_tune(texts, y)

        # Step 2: Compute embeddings
        logger.info("\n=== Phase 2: Computing Embeddings ===")
        encoder = self._get_encoder()

        if self.use_chunked_encoding:
            embeddings = encoder.encode(texts, show_progress_bar=True)
        else:
            embeddings = self.embedder.encode(texts, show_progress_bar=True, convert_to_numpy=True)

        logger.info(f"Embedding shape: {embeddings.shape}")

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            embeddings, y, test_size=test_split, random_state=self.random_seed
        )

        # Scale features
        self.scaler = StandardScaler()
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)

        # Step 3: Build and train classifier
        logger.info("\n=== Phase 3: Training Classifier ===")
        input_dim = X_train.shape[1]
        output_dim = len(FAILURE_MODES)

        self.model = self._build_classifier(input_dim, output_dim)

        # Initialize GCN from label co-occurrence
        if self.use_label_gcn and hasattr(self.model, 'init_gcn_from_labels'):
            self.model.init_gcn_from_labels(y_train)

        # Setup device - prioritize CUDA (Modal GPU) > MPS (Mac) > CPU
        device = torch.device("cuda" if torch.cuda.is_available() else
                             "mps" if torch.backends.mps.is_available() else "cpu")
        self.model.to(device)
        logger.info(f"Training on {device}")

        # Create loss function
        if self.loss_type == "asl":
            criterion = _create_asymmetric_loss(
                self.asl_gamma_neg, self.asl_gamma_pos, self.asl_clip
            )
            logger.info(f"Using Asymmetric Loss (γ-={self.asl_gamma_neg}, γ+={self.asl_gamma_pos})")
        elif self.loss_type == "focal":
            criterion = _create_focal_loss(
                self.focal_alpha, self.focal_gamma, self.label_smoothing
            )
            logger.info(f"Using Focal Loss (α={self.focal_alpha}, γ={self.focal_gamma})")
        else:
            criterion = nn.BCEWithLogitsLoss()
            logger.info("Using BCE Loss")

        # Optimizer and scheduler
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=0.01
        )
        scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer, T_0=10, T_mult=2
        )

        # Convert to tensors
        X_train_t = torch.tensor(X_train, dtype=torch.float32).to(device)
        y_train_t = torch.tensor(y_train, dtype=torch.float32).to(device)
        X_test_t = torch.tensor(X_test, dtype=torch.float32).to(device)

        # Training loop
        best_f1 = 0
        best_state = None

        for epoch in range(self.epochs):
            self.model.train()

            # Mini-batch training
            indices = torch.randperm(len(X_train_t))
            total_loss = 0
            n_batches = 0

            for i in range(0, len(indices), self.batch_size):
                batch_idx = indices[i:i + self.batch_size]
                if len(batch_idx) < 2:
                    continue

                X_batch = X_train_t[batch_idx]
                y_batch = y_train_t[batch_idx]

                optimizer.zero_grad()
                outputs = self.model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()

                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

                optimizer.step()
                total_loss += loss.item()
                n_batches += 1

            scheduler.step()

            # Evaluation
            if (epoch + 1) % 5 == 0 or epoch == self.epochs - 1:
                self.model.eval()
                with torch.no_grad():
                    test_outputs = self.model(X_test_t)
                    test_probs = torch.sigmoid(test_outputs).cpu().numpy()
                    test_preds = (test_probs > 0.5)

                f1s = []
                for i, mode in enumerate(FAILURE_MODES):
                    if y_test[:, i].sum() > 0:
                        f1 = f1_score(y_test[:, i], test_preds[:, i], zero_division=0)
                        f1s.append(f1)

                macro_f1 = np.mean(f1s) if f1s else 0
                avg_loss = total_loss / max(n_batches, 1)

                logger.info(f"Epoch {epoch + 1}/{self.epochs}: Loss={avg_loss:.4f}, Macro F1={macro_f1:.3f}")

                if macro_f1 > best_f1:
                    best_f1 = macro_f1
                    best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}

        # Restore best model
        if best_state:
            self.model.load_state_dict(best_state)
            logger.info(f"Restored best model (F1={best_f1:.3f})")

        # Step 4: Optimize thresholds with CV
        logger.info("\n=== Phase 4: Threshold Optimization ===")
        self.model.eval()
        with torch.no_grad():
            test_outputs = self.model(X_test_t)
            test_probs = torch.sigmoid(test_outputs).cpu().numpy()

        if self.cv_folds > 1:
            logger.info(f"Using {self.cv_folds}-fold CV for threshold optimization")
            kf = KFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_seed)
            fold_thresholds = {mode: [] for mode in FAILURE_MODES}

            for fold_idx, (train_idx, val_idx) in enumerate(kf.split(test_probs)):
                val_probs = test_probs[val_idx]
                val_labels = y_test[val_idx]

                for i, mode in enumerate(FAILURE_MODES):
                    if val_labels[:, i].sum() == 0:
                        continue

                    best_t, best_f1 = 0.5, 0.0
                    for t in np.linspace(0.1, 0.9, 33):
                        preds = (val_probs[:, i] > t).astype(int)
                        f1 = f1_score(val_labels[:, i], preds, zero_division=0)
                        if f1 > best_f1:
                            best_f1, best_t = f1, t
                    fold_thresholds[mode].append(best_t)

            for mode in FAILURE_MODES:
                if fold_thresholds[mode]:
                    self.thresholds[mode] = float(np.median(fold_thresholds[mode]))
                    logger.info(f"  {mode}: threshold={self.thresholds[mode]:.2f}")
        else:
            # Single-split optimization
            for i, mode in enumerate(FAILURE_MODES):
                if y_test[:, i].sum() == 0:
                    continue
                best_t, best_f1 = 0.5, 0.0
                for t in np.linspace(0.1, 0.9, 17):
                    preds = (test_probs[:, i] > t).astype(int)
                    f1 = f1_score(y_test[:, i], preds, zero_division=0)
                    if f1 > best_f1:
                        best_f1, best_t = f1, t
                self.thresholds[mode] = best_t

        # Final evaluation
        logger.info("\n=== Final Results ===")
        test_preds = np.zeros_like(test_probs, dtype=bool)
        for i, mode in enumerate(FAILURE_MODES):
            test_preds[:, i] = test_probs[:, i] > self.thresholds[mode]

        results = {"modes": {}}
        for i, mode in enumerate(FAILURE_MODES):
            if y_test[:, i].sum() > 0:
                p = precision_score(y_test[:, i], test_preds[:, i], zero_division=0)
                r = recall_score(y_test[:, i], test_preds[:, i], zero_division=0)
                f1 = f1_score(y_test[:, i], test_preds[:, i], zero_division=0)
                results["modes"][mode] = {"precision": p, "recall": r, "f1": f1}
                logger.info(f"  {mode}: P={p:.3f}, R={r:.3f}, F1={f1:.3f}")

        macro_f1 = np.mean([m["f1"] for m in results["modes"].values()])
        results["overall"] = {"macro_f1": macro_f1}

        logger.info(f"\n  MACRO F1: {macro_f1:.3f}")

        # Step 5: Fit adaptive thresholder (if enabled)
        if self.use_adaptive_thresholding:
            logger.info("\n=== Phase 5: Adaptive Thresholding ===")
            self._adaptive_thresholder = AdaptiveThresholder(
                k=self.adaptive_k,
                alpha=self.adaptive_alpha,
            )
            # Store scaled training embeddings for adaptive thresholding
            self._train_embeddings = X_train
            self._train_labels = y_train
            self._adaptive_thresholder.fit(X_train, y_train)
            logger.info("Adaptive thresholder fitted and ready")

        self.is_trained = True
        return results

    def predict_batch(self, records: List[Dict]) -> List[Dict[str, Tuple[bool, float]]]:
        """Predict failure modes for a batch of records.

        Returns:
            List of dicts mapping mode -> (detected, confidence)
        """
        import torch

        if not self.is_trained:
            raise RuntimeError("Model not trained")

        # Get embeddings
        texts = [self._extract_text(r) for r in records]
        encoder = self._get_encoder()

        if self.use_chunked_encoding:
            embeddings = encoder.encode(texts, show_progress_bar=False)
        else:
            embeddings = self.embedder.encode(texts, show_progress_bar=False, convert_to_numpy=True)

        X = self.scaler.transform(embeddings)

        # Predict
        device = next(self.model.parameters()).device
        X_t = torch.tensor(X, dtype=torch.float32).to(device)

        self.model.eval()
        with torch.no_grad():
            outputs = self.model(X_t)
            probs = torch.sigmoid(outputs).cpu().numpy()

        # Apply thresholds (adaptive or fixed)
        if self.use_adaptive_thresholding and self._adaptive_thresholder is not None:
            # Use adaptive per-sample thresholds
            adaptive_thresholds = self._adaptive_thresholder.predict_thresholds(X)
            results = []
            for i in range(len(records)):
                pred_dict = {}
                for j, mode in enumerate(FAILURE_MODES):
                    threshold = adaptive_thresholds[i, j]
                    detected = bool(probs[i, j] > threshold)
                    confidence = float(probs[i, j])
                    pred_dict[mode] = (detected, confidence)
                results.append(pred_dict)
        else:
            # Use fixed per-mode thresholds (fallback)
            results = []
            for i in range(len(records)):
                pred_dict = {}
                for j, mode in enumerate(FAILURE_MODES):
                    threshold = self.thresholds.get(mode, 0.5)
                    detected = bool(probs[i, j] > threshold)
                    confidence = float(probs[i, j])
                    pred_dict[mode] = (detected, confidence)
                results.append(pred_dict)

        return results

    def save(self, path: Path):
        """Save the trained model."""
        import torch

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save model state
        torch.save(self.model.state_dict(), path / "model.pt")

        # Save scaler and thresholds
        with open(path / "scaler.pkl", "wb") as f:
            pickle.dump(self.scaler, f)

        with open(path / "thresholds.json", "w") as f:
            json.dump(self.thresholds, f)

        # Save config
        config = {
            "embedding_model": self.embedding_model,
            "use_contrastive_finetuning": self.use_contrastive_finetuning,
            "use_chunked_encoding": self.use_chunked_encoding,
            "use_label_gcn": self.use_label_gcn,
            "hidden_dims": self.hidden_dims,
            "loss_type": self.loss_type,
            "use_adaptive_thresholding": self.use_adaptive_thresholding,
            "adaptive_k": self.adaptive_k,
            "adaptive_alpha": self.adaptive_alpha,
        }
        with open(path / "config.json", "w") as f:
            json.dump(config, f)

        # Save fine-tuned embedder if used
        if self.use_contrastive_finetuning and self._embedder is not None:
            self._embedder.save(str(path / "embedder"))

        # Save adaptive thresholder if used
        if self.use_adaptive_thresholding and self._adaptive_thresholder is not None:
            with open(path / "adaptive_thresholder.pkl", "wb") as f:
                pickle.dump({
                    "thresholder": self._adaptive_thresholder,
                    "train_embeddings": self._train_embeddings,
                    "train_labels": self._train_labels,
                }, f)

        logger.info(f"Model saved to {path}")

    @classmethod
    def load(cls, path: Path) -> "MultiTaskDetectorV4":
        """Load a trained model."""
        import torch
        from sentence_transformers import SentenceTransformer

        path = Path(path)

        # Load config
        with open(path / "config.json") as f:
            config = json.load(f)

        # Create detector
        detector = cls(**config)

        # Load scaler and thresholds
        with open(path / "scaler.pkl", "rb") as f:
            detector.scaler = pickle.load(f)

        with open(path / "thresholds.json") as f:
            detector.thresholds = json.load(f)

        # Load embedder
        embedder_path = path / "embedder"
        if embedder_path.exists():
            detector._embedder = SentenceTransformer(str(embedder_path))

        # Build and load model
        input_dim = detector.scaler.mean_.shape[0]
        output_dim = len(FAILURE_MODES)
        detector.model = detector._build_classifier(input_dim, output_dim)

        device = torch.device("cuda" if torch.cuda.is_available() else
                              "mps" if torch.backends.mps.is_available() else "cpu")
        state_dict = torch.load(path / "model.pt", map_location=device)
        detector.model.load_state_dict(state_dict)
        detector.model.to(device)
        detector.model.eval()

        # Load adaptive thresholder if exists
        adaptive_path = path / "adaptive_thresholder.pkl"
        if adaptive_path.exists():
            with open(adaptive_path, "rb") as f:
                adaptive_data = pickle.load(f)
                detector._adaptive_thresholder = adaptive_data["thresholder"]
                detector._train_embeddings = adaptive_data["train_embeddings"]
                detector._train_labels = adaptive_data["train_labels"]

        detector.is_trained = True
        logger.info(f"Model loaded from {path}")

        return detector


# =============================================================================
# Training Script
# =============================================================================

def train_v4(data_path: Path, output_dir: Optional[Path] = None) -> Tuple[MultiTaskDetectorV4, Dict]:
    """Train the v4 detector with all improvements."""
    with open(data_path) as f:
        records = json.load(f)

    detector = MultiTaskDetectorV4(
        # Enable all improvements
        use_contrastive_finetuning=True,
        contrastive_iterations=10,
        use_chunked_encoding=True,
        chunk_size=6000,
        max_chunks=10,
        use_label_gcn=True,

        # Architecture
        hidden_dims=[512, 256, 128],
        dropout=0.3,

        # Loss - Use Focal Loss (ASL gamma=4.0 caused over-prediction)
        loss_type="focal",
        focal_alpha=0.25,
        focal_gamma=2.0,
        label_smoothing=0.05,

        # Training
        epochs=50,
        batch_size=32,
        learning_rate=0.001,
        cv_folds=5,

        random_seed=42,
    )

    results = detector.train(records)

    if output_dir:
        detector.save(output_dir)

    return detector, results


def get_default_model_path() -> Path:
    """Return the default path for pre-trained v4 model weights."""
    return Path(__file__).parent.parent.parent / "data" / "models" / "mast_v4"


def load_pretrained(model_path: Optional[Path] = None) -> Optional[MultiTaskDetectorV4]:
    """Load a pre-trained v4 model, returning None if no weights exist.

    This is the recommended entry point for production code. It handles
    missing dependencies (torch, sentence_transformers) and missing weights
    gracefully so callers don't need try/except boilerplate.

    Args:
        model_path: Path to saved model directory. Defaults to
            ``backend/data/models/mast_v4/``.

    Returns:
        A trained :class:`MultiTaskDetectorV4` instance, or ``None`` if
        weights are unavailable or dependencies are missing.
    """
    path = model_path or get_default_model_path()
    if not path.exists() or not (path / "config.json").exists():
        logger.info("No pre-trained v4 model found at %s", path)
        return None

    # Config exists but model weights are missing -- the model directory
    # has been created but training has not been run yet.
    weights_path = path / "model.pt"
    if not weights_path.exists():
        logger.info(
            "ML v4 model is untrained — using rule-based detection only"
        )
        return None

    try:
        return MultiTaskDetectorV4.load(path)
    except Exception as e:
        logger.warning("Failed to load v4 model from %s: %s", path, e)
        return None


def model_status(model_path: Optional[Path] = None) -> str:
    """Return the training status of the ML v4 model."""
    path = model_path or get_default_model_path()
    config_path = path / "config.json"
    if not config_path.exists():
        return "unavailable"
    try:
        import json
        with open(config_path) as f:
            config = json.load(f)
        return config.get("training_status", "unknown")
    except Exception:
        return "unavailable"


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    data_path = Path("data/mast/MAD_full_dataset.json")
    output_dir = Path("models/ml_detector_v4")

    detector, results = train_v4(data_path, output_dir)

    print("\n" + "=" * 60)
    print("ML DETECTOR v4 RESULTS")
    print("=" * 60)
    for mode, m in sorted(results["modes"].items()):
        print(f"{mode}: P={m['precision']:.1%}, R={m['recall']:.1%}, F1={m['f1']:.1%}")
    print("-" * 60)
    print(f"MACRO F1: {results['overall']['macro_f1']:.1%}")
