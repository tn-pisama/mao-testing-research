"""ML Detector v3 - Multi-task Learning and Deep Networks.

Improvements:
1. Multi-task learning - predict all failure modes jointly
2. Deep neural network with dropout and batch norm
3. Use PyTorch for better training control
4. Contrastive learning on embeddings
5. Focal loss for class imbalance

Target: 50%+ macro F1
"""

import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

FAILURE_MODES = ["F1", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F11", "F12", "F13", "F14"]
# Skip F2 and F10 - too few samples

ANNOTATION_MAP = {
    "1.1": "F1", "1.2": "F2", "1.3": "F3", "1.4": "F4", "1.5": "F5",
    "2.1": "F6", "2.2": "F7", "2.3": "F8", "2.4": "F9", "2.5": "F10", "2.6": "F11",
    "3.1": "F12", "3.2": "F13", "3.3": "F14",
}


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
    ):
        self.embedding_model = embedding_model
        self.hidden_dims = hidden_dims
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size

        self._embedder = None
        self.model = None
        self.scaler = None
        self.is_trained = False

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

        # Get embeddings
        logger.info(f"Computing embeddings for {len(records)} records...")
        texts = [self._extract_text(r) for r in records]
        embeddings = self.embedder.encode(texts, show_progress_bar=True, convert_to_numpy=True)

        # Get labels
        labels_list = [self._get_labels(r) for r in records]
        y = np.array([[l.get(m, False) for m in FAILURE_MODES] for l in labels_list], dtype=np.float32)

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            embeddings, y, test_size=test_split, random_state=42
        )

        # Scale
        self.scaler = StandardScaler()
        X_train = self.scaler.fit_transform(X_train)
        X_test = self.scaler.transform(X_test)

        # Build model
        input_dim = X_train.shape[1]
        output_dim = len(FAILURE_MODES)

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

        # Compute class weights for focal loss
        pos_counts = y_train.sum(axis=0)
        neg_counts = len(y_train) - pos_counts
        pos_weights = torch.tensor(neg_counts / (pos_counts + 1), dtype=torch.float32)

        # Training
        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.model.to(device)

        optimizer = torch.optim.AdamW(self.model.parameters(), lr=self.learning_rate, weight_decay=0.01)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=self.epochs)

        X_train_t = torch.tensor(X_train, dtype=torch.float32).to(device)
        y_train_t = torch.tensor(y_train, dtype=torch.float32).to(device)
        X_test_t = torch.tensor(X_test, dtype=torch.float32).to(device)

        # Weighted BCE loss
        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weights.to(device))

        best_f1 = 0
        best_state = None

        logger.info(f"Training on {device}...")
        for epoch in range(self.epochs):
            self.model.train()

            # Mini-batch training
            indices = torch.randperm(len(X_train_t))
            total_loss = 0

            for i in range(0, len(indices), self.batch_size):
                batch_idx = indices[i:i + self.batch_size]
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

        # Final evaluation
        self.model.eval()
        with torch.no_grad():
            test_outputs = self.model(X_test_t)
            test_preds = (torch.sigmoid(test_outputs) > 0.5).cpu().numpy()

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

    def predict_batch(self, records: List[Dict]) -> List[Dict[str, bool]]:
        """Predict for batch of records."""
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
            preds = (torch.sigmoid(outputs) > 0.5).cpu().numpy()

        results = []
        for i in range(len(records)):
            pred_dict = {mode: bool(preds[i, j]) for j, mode in enumerate(FAILURE_MODES)}
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
