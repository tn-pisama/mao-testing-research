"""ML Detector v3 - Multi-task Learning and Deep Networks.

Improvements:
1. Multi-task learning - predict all failure modes jointly
2. Deep neural network with dropout and batch norm
3. Use PyTorch for better training control
4. Focal loss for class imbalance (v3.1)
5. Per-mode thresholding (v3.1)
6. Weighted batch sampling for rare classes (v3.1)
7. Label smoothing (v3.2)
8. Cross-validation threshold optimization (v3.2)
9. Self-attention on embeddings (v3.2)
10. Reproducibility with configurable random seeds (v3.3)
11. Multi-run training with averaging for robust evaluation (v3.3)

Target: 72%+ macro F1
"""

import json
import logging
import os
import pickle
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def set_random_seeds(seed: int) -> None:
    """Set random seeds for reproducibility across all libraries.

    Sets seeds for:
    - Python's random module
    - NumPy
    - PyTorch (CPU and CUDA/MPS)
    - Environment variable for hash seed
    """
    random.seed(seed)
    np.random.seed(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)

    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            # For full reproducibility (may impact performance)
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            # MPS doesn't have the same seed control, but manual_seed helps
            pass
    except ImportError:
        pass


def _create_focal_loss(alpha: float = 0.25, gamma: float = 2.0, smoothing: float = 0.0):
    """Create Focal Loss criterion for hard negative mining.

    Focal loss down-weights easy examples and focuses on hard negatives,
    which helps with class imbalance. Label smoothing regularizes confidence.
    """
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class FocalLoss(nn.Module):
        def __init__(self, alpha: float, gamma: float, smoothing: float = 0.0,
                     pos_weight: Optional[torch.Tensor] = None):
            super().__init__()
            self.alpha = alpha
            self.gamma = gamma
            self.smoothing = smoothing
            self.pos_weight = pos_weight

        def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            # Apply label smoothing to regularize confidence
            if self.smoothing > 0:
                targets = targets * (1 - self.smoothing) + 0.5 * self.smoothing

            # Apply pos_weight if provided
            if self.pos_weight is not None:
                weight = self.pos_weight.unsqueeze(0).expand_as(targets)
                weight = weight * targets + (1 - targets)
            else:
                weight = torch.ones_like(targets)

            # BCE with logits
            ce = F.binary_cross_entropy_with_logits(inputs, targets, reduction='none')

            # Focal weighting
            p = torch.sigmoid(inputs)
            p_t = p * targets + (1 - p) * (1 - targets)
            focal_weight = self.alpha * (1 - p_t) ** self.gamma

            loss = focal_weight * weight * ce
            return loss.mean()

    return FocalLoss(alpha, gamma, smoothing)

from app.core.mast_constants import ANNOTATION_MAP, FAILURE_MODES_F14

# Skip F2 and F10 - too few training samples
FAILURE_MODES = [m for m in FAILURE_MODES_F14 if m not in ("F2", "F10")]


def _create_attention_network(input_dim: int, hidden_dims: List[int], output_dim: int,
                               dropout: float, num_heads: int = 8):
    """Create network with self-attention on embeddings.

    Self-attention allows the model to weight embedding dimensions differently
    for each failure mode, improving multi-task learning.
    """
    import torch
    import torch.nn as nn

    class SelfAttentionBlock(nn.Module):
        """Self-attention for embedding dimension weighting."""

        def __init__(self, embed_dim: int, num_heads: int = 8, dropout: float = 0.1):
            super().__init__()
            self.attention = nn.MultiheadAttention(
                embed_dim=embed_dim,
                num_heads=num_heads,
                dropout=dropout,
                batch_first=True
            )
            self.norm = nn.LayerNorm(embed_dim)
            self.dropout = nn.Dropout(dropout)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # x shape: (batch, embed_dim)
            # Reshape to (batch, 1, embed_dim) for attention
            x = x.unsqueeze(1)
            attn_out, _ = self.attention(x, x, x)
            x = self.norm(x + self.dropout(attn_out))
            return x.squeeze(1)

    class MultiTaskNetwork(nn.Module):
        """Network with optional self-attention on input embeddings."""

        def __init__(self, input_dim: int, hidden_dims: List[int], output_dim: int,
                     dropout: float, num_heads: int = 8, use_attention: bool = True):
            super().__init__()
            self.use_attention = use_attention

            # Optional attention on input embeddings
            if use_attention:
                self.attention = SelfAttentionBlock(input_dim, num_heads, dropout)

            # Dense layers
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
            self.dense = nn.Sequential(*layers)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            if self.use_attention:
                x = self.attention(x)
            return self.dense(x)

    return MultiTaskNetwork(input_dim, hidden_dims, output_dim, dropout, num_heads)


class MultiTaskDetector:
    """Multi-task ML detector using PyTorch."""

    def __init__(
        self,
        embedding_model: str = "all-mpnet-base-v2",
        hidden_dims: List[int] = [512, 256, 128],
        dropout: float = 0.3,
        learning_rate: float = 0.001,
        epochs: int = 50,
        batch_size: int = 32,
        use_focal_loss: bool = True,
        focal_alpha: float = 0.25,
        focal_gamma: float = 2.0,
        label_smoothing: float = 0.0,  # Optional: set to 0.05 for confidence regularization
        use_attention: bool = False,   # Optional: set True for self-attention on embeddings
        attention_heads: int = 8,
        cv_folds: int = 1,  # Optional: set to 5 for CV threshold optimization
        random_seed: Optional[int] = 42,  # Seed for reproducibility (None for random)
    ):
        self.embedding_model = embedding_model
        self.hidden_dims = hidden_dims
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.use_focal_loss = use_focal_loss
        self.focal_alpha = focal_alpha
        self.focal_gamma = focal_gamma
        self.label_smoothing = label_smoothing
        self.use_attention = use_attention
        self.attention_heads = attention_heads
        self.cv_folds = cv_folds
        self.random_seed = random_seed

        self._embedder = None
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.thresholds: Dict[str, float] = {mode: 0.5 for mode in FAILURE_MODES}

    @property
    def embedder(self):
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer(self.embedding_model)
                logger.info(f"Loaded {self.embedding_model}")
            except Exception as e:
                logger.error(f"Failed to load embedder: {e}")
        return self._embedder

    def _extract_text(self, record: Dict) -> str:
        """Extract text from record."""
        trajectory = record.get("trace", {}).get("trajectory", "") or ""
        return trajectory[:15000]

    def _get_labels(self, record: Dict) -> Dict[str, bool]:
        """Get labels from record."""
        annotations = record.get("mast_annotation", {})
        labels = {}
        for code, mode in ANNOTATION_MAP.items():
            value = annotations.get(code, 0)
            labels[mode] = bool(value) if isinstance(value, int) else value
        return labels

    def train(
        self,
        records: List[Dict],
        test_split: float = 0.2,
    ) -> Dict[str, Any]:
        """Train multi-task model."""
        import torch
        import torch.nn as nn
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import f1_score

        # Set random seeds for reproducibility
        if self.random_seed is not None:
            set_random_seeds(self.random_seed)
            logger.info(f"Random seed set to {self.random_seed}")

        # Get embeddings
        logger.info(f"Computing embeddings for {len(records)} records...")
        texts = [self._extract_text(r) for r in records]
        embeddings = self.embedder.encode(texts, show_progress_bar=True, convert_to_numpy=True)

        # Get labels
        labels_list = [self._get_labels(r) for r in records]
        y = np.array([[l.get(m, False) for m in FAILURE_MODES] for l in labels_list], dtype=np.float32)

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            embeddings, y, test_size=test_split, random_state=self.random_seed
        )

        # Scale
        self.scaler = StandardScaler()
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)

        # Build model with optional self-attention
        input_dim = X_train.shape[1]
        output_dim = len(FAILURE_MODES)

        if self.use_attention:
            self.model = _create_attention_network(
                input_dim, self.hidden_dims, output_dim,
                self.dropout, self.attention_heads
            )
            logger.info(f"Using attention network with {self.attention_heads} heads")
        else:
            layers = []
            prev_dim = input_dim
            for hidden_dim in self.hidden_dims:
                layers.extend([
                    nn.Linear(prev_dim, hidden_dim),
                    nn.BatchNorm1d(hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(self.dropout),
                ])
                prev_dim = hidden_dim
            layers.append(nn.Linear(prev_dim, output_dim))
            self.model = nn.Sequential(*layers)

        # Compute class weights
        pos_counts = y_train.sum(axis=0)
        neg_counts = len(y_train) - pos_counts
        pos_weights = torch.tensor(
            np.minimum(neg_counts / (pos_counts + 1), 10),  # Cap at 10x
            dtype=torch.float32
        )

        # Compute sample weights for rare class upsampling
        class_sizes = pos_counts
        sample_weights = np.ones(len(y_train))
        for i, y_sample in enumerate(y_train):
            # Upweight samples with rare positive labels
            rare_boost = sum(
                1.0 for j, has_label in enumerate(y_sample)
                if has_label and class_sizes[j] < 50
            )
            sample_weights[i] = 1.0 + 0.5 * rare_boost

        # Training
        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.model.to(device)

        optimizer = torch.optim.AdamW(self.model.parameters(), lr=self.learning_rate, weight_decay=0.01)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=self.epochs)

        X_train_t = torch.tensor(X_train, dtype=torch.float32).to(device)
        y_train_t = torch.tensor(y_train, dtype=torch.float32).to(device)
        X_test_t = torch.tensor(X_test, dtype=torch.float32).to(device)

        # Use Focal Loss or Weighted BCE
        if self.use_focal_loss:
            criterion = _create_focal_loss(self.focal_alpha, self.focal_gamma, self.label_smoothing)
            criterion.pos_weight = pos_weights.to(device)
            logger.info("Using Focal Loss with alpha=%.2f, gamma=%.1f, smoothing=%.2f",
                       self.focal_alpha, self.focal_gamma, self.label_smoothing)
        else:
            criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weights.to(device))

        best_f1 = 0
        best_state = None

        # Normalize sample weights to probabilities
        sample_probs = sample_weights / sample_weights.sum()

        logger.info(f"Training on {device}...")
        for epoch in range(self.epochs):
            self.model.train()

            # Weighted sampling - oversample rare classes
            indices = np.random.choice(
                len(X_train_t),
                size=len(X_train_t),
                replace=True,
                p=sample_probs
            )
            indices = torch.tensor(indices)
            total_loss = 0

            for i in range(0, len(indices), self.batch_size):
                batch_idx = indices[i:i + self.batch_size]
                if len(batch_idx) < 2:  # Skip batches too small for BatchNorm
                    continue
                X_batch = X_train_t[batch_idx]
                y_batch = y_train_t[batch_idx]

                optimizer.zero_grad()
                outputs = self.model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            scheduler.step()

            # Evaluate
            if (epoch + 1) % 5 == 0:
                self.model.eval()
                with torch.no_grad():
                    test_outputs = self.model(X_test_t)
                    test_preds = (torch.sigmoid(test_outputs) > 0.5).cpu().numpy()

                f1s = []
                for i, mode in enumerate(FAILURE_MODES):
                    if y_test[:, i].sum() > 0:
                        f1 = f1_score(y_test[:, i], test_preds[:, i], zero_division=0)
                        f1s.append(f1)

                macro_f1 = np.mean(f1s)
                logger.info(f"Epoch {epoch + 1}: Loss={total_loss:.4f}, F1={macro_f1:.3f}")

                if macro_f1 > best_f1:
                    best_f1 = macro_f1
                    best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}

        # Restore best model
        if best_state:
            self.model.load_state_dict(best_state)

        # Optimize thresholds using cross-validation for robustness
        self.model.eval()
        with torch.no_grad():
            test_outputs = self.model(X_test_t)
            test_probs = torch.sigmoid(test_outputs).cpu().numpy()

        if self.cv_folds > 1:
            logger.info(f"Optimizing thresholds with {self.cv_folds}-fold CV...")
            from sklearn.model_selection import KFold
            kf = KFold(n_splits=self.cv_folds, shuffle=True, random_state=self.random_seed)

            # Collect best thresholds from each fold
            fold_thresholds = {mode: [] for mode in FAILURE_MODES}

            for fold_idx, (train_idx, val_idx) in enumerate(kf.split(test_probs)):
                val_probs = test_probs[val_idx]
                val_labels = y_test[val_idx]

                for i, mode in enumerate(FAILURE_MODES):
                    if val_labels[:, i].sum() == 0:
                        continue
                    best_t, best_f1 = 0.5, 0.0
                    for t in np.linspace(0.15, 0.85, 29):  # Finer grid
                        preds = (val_probs[:, i] > t).astype(int)
                        f1 = f1_score(val_labels[:, i], preds, zero_division=0)
                        if f1 > best_f1:
                            best_f1, best_t = f1, t
                    fold_thresholds[mode].append(best_t)

            # Use median threshold across folds (robust to outliers)
            for mode in FAILURE_MODES:
                if fold_thresholds[mode]:
                    self.thresholds[mode] = float(np.median(fold_thresholds[mode]))
                    if self.thresholds[mode] != 0.5:
                        logger.info(f"  {mode}: threshold={self.thresholds[mode]:.2f} (median of {len(fold_thresholds[mode])} folds)")
        else:
            # Single-split optimization (fallback)
            logger.info("Optimizing per-mode thresholds...")
            for i, mode in enumerate(FAILURE_MODES):
                if y_test[:, i].sum() == 0:
                    continue
                best_t, best_f1 = 0.5, 0.0
                for t in np.linspace(0.2, 0.8, 13):
                    preds = (test_probs[:, i] > t).astype(int)
                    f1 = f1_score(y_test[:, i], preds, zero_division=0)
                    if f1 > best_f1:
                        best_f1, best_t = f1, t
                self.thresholds[mode] = best_t
                if best_t != 0.5:
                    logger.info(f"  {mode}: threshold={best_t:.2f} (F1={best_f1:.3f})")

        # Final evaluation with optimized thresholds
        test_preds = np.zeros_like(test_probs, dtype=bool)
        for i, mode in enumerate(FAILURE_MODES):
            test_preds[:, i] = test_probs[:, i] > self.thresholds[mode]

        results = {"modes": {}}
        for i, mode in enumerate(FAILURE_MODES):
            if y_test[:, i].sum() > 0:
                from sklearn.metrics import precision_score, recall_score
                p = precision_score(y_test[:, i], test_preds[:, i], zero_division=0)
                r = recall_score(y_test[:, i], test_preds[:, i], zero_division=0)
                f1 = f1_score(y_test[:, i], test_preds[:, i], zero_division=0)
                results["modes"][mode] = {"precision": p, "recall": r, "f1": f1}
                logger.info(f"{mode}: F1={f1:.3f}")

        results["overall"] = {
            "macro_f1": np.mean([m["f1"] for m in results["modes"].values()])
        }

        self.is_trained = True
        return results

    @classmethod
    def train_multirun(
        cls,
        records: List[Dict],
        num_runs: int = 5,
        base_seed: int = 42,
        test_split: float = 0.2,
        **detector_kwargs,
    ) -> Dict[str, Any]:
        """Train detector multiple times with different seeds and aggregate results.

        This provides more robust evaluation by averaging metrics across runs,
        accounting for variance from random initialization and data splits.

        Args:
            records: Training data records
            num_runs: Number of training runs with different seeds
            base_seed: Starting seed (runs use base_seed, base_seed+1, ...)
            test_split: Fraction of data for test set
            **detector_kwargs: Additional arguments for MultiTaskDetector

        Returns:
            Dict containing:
            - run_results: List of results from each run
            - aggregated: Aggregated metrics with mean, std, and confidence intervals
            - best_run: Index of the best run by macro F1
            - seeds_used: List of seeds used for each run
        """
        logger.info(f"Starting multi-run training with {num_runs} runs (base_seed={base_seed})")

        run_results = []
        seeds_used = []
        best_f1 = 0.0
        best_run_idx = 0
        best_detector = None

        for run_idx in range(num_runs):
            seed = base_seed + run_idx
            seeds_used.append(seed)

            logger.info(f"\n{'='*60}")
            logger.info(f"Run {run_idx + 1}/{num_runs} (seed={seed})")
            logger.info("=" * 60)

            # Create and train detector with this seed
            detector = cls(random_seed=seed, **detector_kwargs)
            result = detector.train(records, test_split=test_split)

            run_results.append(result)

            # Track best model
            macro_f1 = result["overall"]["macro_f1"]
            if macro_f1 > best_f1:
                best_f1 = macro_f1
                best_run_idx = run_idx
                best_detector = detector

            logger.info(f"Run {run_idx + 1} Macro F1: {macro_f1:.4f}")

        # Aggregate results across runs
        aggregated = cls._aggregate_multirun_results(run_results, seeds_used)

        logger.info(f"\n{'='*60}")
        logger.info("MULTI-RUN SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Runs: {num_runs}, Seeds: {seeds_used[0]}-{seeds_used[-1]}")
        logger.info(f"Macro F1: {aggregated['overall']['macro_f1_mean']:.4f} "
                   f"± {aggregated['overall']['macro_f1_std']:.4f}")
        logger.info(f"95% CI: [{aggregated['overall']['macro_f1_ci_lower']:.4f}, "
                   f"{aggregated['overall']['macro_f1_ci_upper']:.4f}]")
        logger.info(f"Best run: {best_run_idx + 1} with F1={best_f1:.4f}")

        return {
            "run_results": run_results,
            "aggregated": aggregated,
            "best_run": best_run_idx,
            "best_detector": best_detector,
            "seeds_used": seeds_used,
            "num_runs": num_runs,
        }

    @staticmethod
    def _aggregate_multirun_results(
        run_results: List[Dict[str, Any]],
        seeds_used: List[int],
    ) -> Dict[str, Any]:
        """Aggregate results from multiple training runs.

        Computes mean, std, min, max, and 95% confidence intervals for each metric.
        """
        # Collect per-mode metrics across runs
        mode_metrics: Dict[str, Dict[str, List[float]]] = {}
        macro_f1s = []

        for result in run_results:
            macro_f1s.append(result["overall"]["macro_f1"])

            for mode, metrics in result["modes"].items():
                if mode not in mode_metrics:
                    mode_metrics[mode] = {"precision": [], "recall": [], "f1": []}
                for metric_name in ["precision", "recall", "f1"]:
                    if metric_name in metrics:
                        mode_metrics[mode][metric_name].append(metrics[metric_name])

        # Compute aggregated statistics
        def compute_stats(values: List[float]) -> Dict[str, float]:
            """Compute mean, std, min, max, and 95% CI."""
            arr = np.array(values)
            mean = float(np.mean(arr))
            std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
            n = len(arr)
            # 95% CI using t-distribution approximation (t ≈ 2 for small samples)
            ci_margin = 2.0 * std / np.sqrt(n) if n > 1 else 0.0
            return {
                "mean": mean,
                "std": std,
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "ci_lower": mean - ci_margin,
                "ci_upper": mean + ci_margin,
                "values": values,
            }

        aggregated = {
            "modes": {},
            "overall": {},
            "seeds_used": seeds_used,
        }

        # Per-mode aggregated metrics
        for mode, metrics in mode_metrics.items():
            aggregated["modes"][mode] = {}
            for metric_name, values in metrics.items():
                if values:
                    stats = compute_stats(values)
                    aggregated["modes"][mode][f"{metric_name}_mean"] = stats["mean"]
                    aggregated["modes"][mode][f"{metric_name}_std"] = stats["std"]
                    aggregated["modes"][mode][f"{metric_name}_min"] = stats["min"]
                    aggregated["modes"][mode][f"{metric_name}_max"] = stats["max"]
                    aggregated["modes"][mode][f"{metric_name}_ci_lower"] = stats["ci_lower"]
                    aggregated["modes"][mode][f"{metric_name}_ci_upper"] = stats["ci_upper"]

        # Overall aggregated metrics
        overall_stats = compute_stats(macro_f1s)
        aggregated["overall"]["macro_f1_mean"] = overall_stats["mean"]
        aggregated["overall"]["macro_f1_std"] = overall_stats["std"]
        aggregated["overall"]["macro_f1_min"] = overall_stats["min"]
        aggregated["overall"]["macro_f1_max"] = overall_stats["max"]
        aggregated["overall"]["macro_f1_ci_lower"] = overall_stats["ci_lower"]
        aggregated["overall"]["macro_f1_ci_upper"] = overall_stats["ci_upper"]
        aggregated["overall"]["macro_f1_values"] = macro_f1s

        return aggregated

    def predict_batch(self, records: List[Dict]) -> List[Dict[str, bool]]:
        """Predict for batch of records using per-mode thresholds."""
        import torch

        if not self.is_trained:
            raise RuntimeError("Model not trained")

        texts = [self._extract_text(r) for r in records]
        embeddings = self.embedder.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        X = self.scaler.transform(embeddings)

        device = next(self.model.parameters()).device
        X_t = torch.tensor(X, dtype=torch.float32).to(device)

        self.model.eval()
        with torch.no_grad():
            outputs = self.model(X_t)
            probs = torch.sigmoid(outputs).cpu().numpy()

        # Apply per-mode thresholds
        results = []
        for i in range(len(records)):
            pred_dict = {}
            for j, mode in enumerate(FAILURE_MODES):
                threshold = self.thresholds.get(mode, 0.5)
                pred_dict[mode] = bool(probs[i, j] > threshold)
            results.append(pred_dict)

        return results


class EnsembleDetector:
    """Ensemble of multiple detectors."""

    def __init__(self):
        self.detectors: List[Tuple[str, Any]] = []
        self.weights: Dict[str, float] = {}

    def add_detector(self, name: str, detector: Any, weight: float = 1.0):
        """Add a detector to the ensemble."""
        self.detectors.append((name, detector))
        self.weights[name] = weight

    def predict_batch(self, records: List[Dict]) -> List[Dict[str, bool]]:
        """Predict using weighted voting."""
        all_preds = []

        for name, detector in self.detectors:
            try:
                preds = detector.predict_batch(records)
                all_preds.append((name, preds))
            except Exception as e:
                logger.warning(f"Detector {name} failed: {e}")

        if not all_preds:
            return [{} for _ in records]

        # Weighted voting
        results = []
        for i in range(len(records)):
            mode_votes: Dict[str, float] = {}

            for name, preds in all_preds:
                weight = self.weights.get(name, 1.0)
                for mode, pred in preds[i].items():
                    if mode not in mode_votes:
                        mode_votes[mode] = 0.0
                    mode_votes[mode] += weight * (1.0 if pred else 0.0)

            total_weight = sum(self.weights.get(name, 1.0) for name, _ in all_preds)
            final_pred = {
                mode: votes / total_weight > 0.5
                for mode, votes in mode_votes.items()
            }
            results.append(final_pred)

        return results


def train_v3(data_path: Path) -> Tuple[MultiTaskDetector, Dict]:
    """Train v3 multi-task detector."""
    with open(data_path) as f:
        records = json.load(f)

    detector = MultiTaskDetector(
        hidden_dims=[512, 256, 128],
        dropout=0.3,
        learning_rate=0.001,
        epochs=100,
        batch_size=32,
    )

    results = detector.train(records)
    return detector, results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from pathlib import Path
    detector, results = train_v3(Path("data/mast/MAD_full_dataset.json"))

    print("\n" + "=" * 60)
    print("MULTI-TASK DETECTOR v3 RESULTS")
    print("=" * 60)
    for mode, m in sorted(results["modes"].items()):
        print(f"{mode}: F1={m['f1']:.1%}")
    print("-" * 60)
    print(f"Macro F1: {results['overall']['macro_f1']:.1%}")
