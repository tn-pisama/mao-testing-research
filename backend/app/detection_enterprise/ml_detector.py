"""ML-based failure detection trained on MAST annotations.

This module implements machine learning classifiers for detecting
agent failures, trained directly on UC Berkeley MAST-Data annotations.

Approach:
1. Extract features from conversation traces (text, structure, patterns)
2. Train multi-label classifiers for each failure mode (F1-F14)
3. Use ensemble of classifiers with calibrated probabilities

Features:
- Text embeddings (e5-large-v2 via centralized EmbeddingService)
- Structural features (turn counts, participant patterns)
- Pattern features (repetition, topic drift indicators)
- Lexical features (TF-IDF on key terms)
"""

import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Use centralized embedding service (e5-large-v2) instead of legacy MiniLM
from app.core.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# Failure modes we train on (matching MAST annotations)
FAILURE_MODES = [
    "F1", "F2", "F3", "F4", "F5",  # Planning failures
    "F6", "F7", "F8", "F9", "F10", "F11",  # Execution failures
    "F12", "F13", "F14",  # Verification failures
]

# MAST annotation code mapping
ANNOTATION_MAP = {
    "1.1": "F1", "1.2": "F2", "1.3": "F3", "1.4": "F4", "1.5": "F5",
    "2.1": "F6", "2.2": "F7", "2.3": "F8", "2.4": "F9", "2.5": "F10", "2.6": "F11",
    "3.1": "F12", "3.2": "F13", "3.3": "F14",
}


@dataclass
class TraceFeatures:
    """Extracted features from a conversation trace."""
    trace_id: str

    # Text features
    full_text: str = ""
    task_text: str = ""

    # Structural features
    num_turns: int = 0
    num_agent_turns: int = 0
    num_user_turns: int = 0
    num_tool_turns: int = 0
    num_unique_participants: int = 0
    avg_turn_length: float = 0.0
    max_turn_length: int = 0

    # Pattern features
    repetition_ratio: float = 0.0  # Duplicate content ratio
    question_count: int = 0
    error_mention_count: int = 0
    code_block_count: int = 0

    # Computed embeddings (filled by feature extractor)
    text_embedding: Optional[np.ndarray] = None
    task_embedding: Optional[np.ndarray] = None

    # Ground truth labels
    labels: Dict[str, bool] = field(default_factory=dict)


class FeatureExtractor:
    """Extract features from MAST conversation traces."""

    def __init__(self, use_embeddings: bool = True):
        self.use_embeddings = use_embeddings
        self._embedding_service = None

    @property
    def embedding_service(self) -> Optional[EmbeddingService]:
        """Lazy-load centralized embedding service (e5-large-v2)."""
        if self._embedding_service is None and self.use_embeddings:
            try:
                self._embedding_service = EmbeddingService.get_instance()
                logger.info(f"Using centralized embedding service (e5-large-v2, {self._embedding_service.dimensions}d)")
            except Exception as e:
                logger.warning(f"Embedding service not available: {e}")
                self.use_embeddings = False
        return self._embedding_service

    @property
    def embedder(self):
        """Backward-compatible alias for embedding_service."""
        return self.embedding_service

    def extract_features(self, record: Dict[str, Any]) -> TraceFeatures:
        """Extract features from a MAST record.

        Args:
            record: Raw MAST data record

        Returns:
            TraceFeatures with extracted features
        """
        trace_id = str(record.get("trace_id", "unknown"))
        trajectory = record.get("trace", {}).get("trajectory", "")
        annotations = record.get("mast_annotation", {})

        features = TraceFeatures(trace_id=trace_id)

        # Parse trajectory into turns
        turns = self._parse_turns(trajectory, record.get("mas_name", ""))

        # Text features
        features.full_text = trajectory[:50000]  # Limit for memory
        features.task_text = self._extract_task(trajectory, record)

        # Structural features
        features.num_turns = len(turns)
        features.num_agent_turns = sum(1 for t in turns if t["role"] == "agent")
        features.num_user_turns = sum(1 for t in turns if t["role"] == "user")
        features.num_tool_turns = sum(1 for t in turns if t["role"] == "tool")

        participants = set(t.get("participant", "") for t in turns)
        features.num_unique_participants = len(participants)

        turn_lengths = [len(t.get("content", "")) for t in turns]
        if turn_lengths:
            features.avg_turn_length = np.mean(turn_lengths)
            features.max_turn_length = max(turn_lengths)

        # Pattern features
        features.repetition_ratio = self._compute_repetition_ratio(turns)
        features.question_count = trajectory.count("?")
        features.error_mention_count = sum(
            trajectory.lower().count(w)
            for w in ["error", "exception", "failed", "traceback", "bug"]
        )
        features.code_block_count = trajectory.count("```")

        # Labels from annotations
        for code, mode in ANNOTATION_MAP.items():
            value = annotations.get(code, 0)
            features.labels[mode] = bool(value) if isinstance(value, int) else value

        return features

    def compute_embeddings(self, features_list: List[TraceFeatures]) -> None:
        """Compute embeddings for a batch of features using e5-large-v2.

        Args:
            features_list: List of TraceFeatures to update with embeddings
        """
        if not self.use_embeddings or not self.embedding_service:
            return

        # Batch encode texts (truncate for model context window)
        texts = [f.full_text[:8000] for f in features_list]
        tasks = [f.task_text[:1000] for f in features_list]

        logger.info(f"Computing embeddings for {len(texts)} traces using e5-large-v2...")

        # Use centralized embedding service with batch encoding
        text_embeddings = self.embedding_service.encode(
            texts,
            batch_size=32,
            show_progress=True,
            normalize=True,
        )
        task_embeddings = self.embedding_service.encode(
            tasks,
            batch_size=32,
            show_progress=False,
            normalize=True,
        )

        for i, features in enumerate(features_list):
            features.text_embedding = text_embeddings[i]
            features.task_embedding = task_embeddings[i]

    def _parse_turns(self, trajectory: str, framework: str) -> List[Dict[str, Any]]:
        """Parse trajectory into turns based on framework."""
        turns = []

        # Framework-specific parsing
        if framework == "ChatDev":
            turns = self._parse_chatdev(trajectory)
        elif framework == "MetaGPT":
            turns = self._parse_metagpt(trajectory)
        elif framework in ("AG2", "AutoGen"):
            turns = self._parse_autogen(trajectory)
        else:
            # Generic parsing
            turns = self._parse_generic(trajectory)

        return turns

    def _parse_chatdev(self, trajectory: str) -> List[Dict[str, Any]]:
        """Parse ChatDev trajectory format."""
        import re
        turns = []

        # ChatDev format: [timestamp INFO] **role** content
        pattern = r'\[[\d\-\s:]+\s+\w+\]\s*\*\*([^*]+)\*\*[:\s]*(.+?)(?=\[\d|\Z)'
        matches = re.findall(pattern, trajectory, re.DOTALL)

        for i, (role_part, content) in enumerate(matches):
            role = "agent"  # Default to agent
            participant = role_part.strip()

            if any(w in participant.lower() for w in ["user", "human", "customer"]):
                role = "user"
            elif any(w in participant.lower() for w in ["system", "config"]):
                role = "system"

            turns.append({
                "role": role,
                "participant": participant,
                "content": content.strip()[:5000],
            })

        return turns if turns else [{"role": "agent", "participant": "agent", "content": trajectory[:5000]}]

    def _parse_metagpt(self, trajectory: str) -> List[Dict[str, Any]]:
        """Parse MetaGPT trajectory format."""
        import re
        turns = []

        # MetaGPT format: [timestamp] FROM: X TO: Y ACTION: Z CONTENT: ...
        pattern = r'\[[\d\-\s:]+\]\s*(?:FROM:\s*(\w+))?\s*(?:TO:\s*[^\n]+)?\s*(?:ACTION:\s*[^\n]+)?\s*(?:CONTENT:\s*)?(.+?)(?=\[\d{4}|\Z)'
        matches = re.findall(pattern, trajectory, re.DOTALL)

        for i, (sender, content) in enumerate(matches):
            role = "user" if sender.lower() == "human" else "agent"
            turns.append({
                "role": role,
                "participant": sender or "agent",
                "content": content.strip()[:5000],
            })

        return turns if turns else [{"role": "agent", "participant": "agent", "content": trajectory[:5000]}]

    def _parse_autogen(self, trajectory: str) -> List[Dict[str, Any]]:
        """Parse AutoGen/AG2 trajectory format."""
        import re
        turns = []

        # AutoGen format: agent_name (to recipient): content
        pattern = r'(\w+)\s*\(to\s+[^)]+\):\s*(.+?)(?=\n\w+\s*\(to|\Z)'
        matches = re.findall(pattern, trajectory, re.DOTALL)

        for sender, content in matches:
            role = "user" if sender.lower() in ("user", "human", "admin") else "agent"
            turns.append({
                "role": role,
                "participant": sender,
                "content": content.strip()[:5000],
            })

        return turns if turns else [{"role": "agent", "participant": "agent", "content": trajectory[:5000]}]

    def _parse_generic(self, trajectory: str) -> List[Dict[str, Any]]:
        """Generic trajectory parsing."""
        # Split on common turn markers
        import re

        # Try different patterns
        patterns = [
            r'(?:^|\n)(\w+):\s*(.+?)(?=\n\w+:|\Z)',  # Name: content
            r'(?:^|\n)(?:Step|Turn)\s*\d+[:\s]+(.+?)(?=(?:Step|Turn)\s*\d+|\Z)',  # Step N: content
        ]

        for pattern in patterns:
            matches = re.findall(pattern, trajectory, re.DOTALL | re.MULTILINE)
            if matches and len(matches) > 1:
                turns = []
                for match in matches:
                    if isinstance(match, tuple):
                        sender, content = match[0], match[1] if len(match) > 1 else match[0]
                    else:
                        sender, content = "agent", match

                    role = "user" if str(sender).lower() in ("user", "human") else "agent"
                    turns.append({
                        "role": role,
                        "participant": str(sender),
                        "content": str(content).strip()[:5000],
                    })
                return turns

        # Fallback: treat as single turn
        return [{"role": "agent", "participant": "agent", "content": trajectory[:10000]}]

    def _extract_task(self, trajectory: str, record: Dict) -> str:
        """Extract task/prompt from trajectory."""
        import re

        # Try task field first
        task = record.get("trace", {}).get("task", "")
        if task:
            return task[:2000]

        # Framework-specific patterns
        patterns = [
            r'\*\*task_prompt\*\*:\s*([^\n|]+)',  # ChatDev
            r'UserRequirement\s*\nCONTENT:\s*\n(.+?)(?:\n\n|\n\[)',  # MetaGPT
            r'(?:Task|Query|Prompt|Problem):\s*(.+?)(?:\n\n|\n\[|$)',  # Generic
        ]

        for pattern in patterns:
            match = re.search(pattern, trajectory, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()[:2000]

        # Fallback: first 500 chars
        return trajectory[:500]

    def _compute_repetition_ratio(self, turns: List[Dict]) -> float:
        """Compute ratio of repeated content across turns."""
        if len(turns) < 2:
            return 0.0

        contents = [t.get("content", "")[:500] for t in turns]
        unique = set(contents)

        if len(contents) == 0:
            return 0.0

        return 1.0 - (len(unique) / len(contents))


class MLFailureDetector:
    """ML-based failure detector trained on MAST data."""

    def __init__(
        self,
        use_embeddings: bool = True,
        model_type: str = "random_forest",
    ):
        self.use_embeddings = use_embeddings
        self.model_type = model_type
        self.feature_extractor = FeatureExtractor(use_embeddings=use_embeddings)

        # One classifier per failure mode
        self.classifiers: Dict[str, Any] = {}
        self.feature_scalers: Dict[str, Any] = {}
        self.is_trained = False

    def extract_feature_vector(self, features: TraceFeatures) -> np.ndarray:
        """Convert TraceFeatures to numpy feature vector.

        Args:
            features: Extracted features

        Returns:
            Feature vector for ML model
        """
        # Structural features
        structural = np.array([
            features.num_turns,
            features.num_agent_turns,
            features.num_user_turns,
            features.num_tool_turns,
            features.num_unique_participants,
            features.avg_turn_length,
            features.max_turn_length,
            features.repetition_ratio,
            features.question_count,
            features.error_mention_count,
            features.code_block_count,
        ], dtype=np.float32)

        # Combine with embeddings if available
        if features.text_embedding is not None:
            # Use first 128 dims of embedding to reduce dimensionality
            text_emb = features.text_embedding[:128] if len(features.text_embedding) > 128 else features.text_embedding
            task_emb = features.task_embedding[:128] if features.task_embedding is not None and len(features.task_embedding) > 128 else (features.task_embedding if features.task_embedding is not None else np.zeros(128))

            return np.concatenate([structural, text_emb, task_emb])

        return structural

    def train(
        self,
        records: List[Dict[str, Any]],
        test_split: float = 0.2,
    ) -> Dict[str, Any]:
        """Train classifiers on MAST data.

        Args:
            records: List of MAST records
            test_split: Fraction for test set

        Returns:
            Training results with metrics
        """
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import f1_score, precision_score, recall_score

        logger.info(f"Extracting features from {len(records)} traces...")

        # Extract features
        features_list = []
        for record in records:
            features = self.feature_extractor.extract_features(record)
            features_list.append(features)

        # Compute embeddings in batch
        if self.use_embeddings:
            self.feature_extractor.compute_embeddings(features_list)

        # Build feature matrix
        X = np.array([self.extract_feature_vector(f) for f in features_list])

        # Build label matrix for each failure mode
        results = {"modes": {}, "overall": {}}

        for mode in FAILURE_MODES:
            # Skip modes with no positive samples
            y = np.array([f.labels.get(mode, False) for f in features_list], dtype=int)

            if y.sum() < 5:
                logger.warning(f"Skipping {mode}: only {y.sum()} positive samples")
                continue

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_split, random_state=42, stratify=y
            )

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Train classifier
            if self.model_type == "random_forest":
                clf = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    min_samples_leaf=5,
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                )
            elif self.model_type == "gradient_boosting":
                clf = GradientBoostingClassifier(
                    n_estimators=100,
                    max_depth=5,
                    learning_rate=0.1,
                    random_state=42,
                )
            else:  # logistic regression
                clf = LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=42,
                )

            clf.fit(X_train_scaled, y_train)

            # Evaluate
            y_pred = clf.predict(X_test_scaled)

            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)

            # Store classifier and scaler
            self.classifiers[mode] = clf
            self.feature_scalers[mode] = scaler

            results["modes"][mode] = {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "train_positives": int(y_train.sum()),
                "test_positives": int(y_test.sum()),
                "test_size": len(y_test),
            }

            logger.info(f"{mode}: F1={f1:.3f}, P={precision:.3f}, R={recall:.3f}")

        self.is_trained = True

        # Compute overall metrics
        f1_scores = [m["f1"] for m in results["modes"].values()]
        results["overall"]["macro_f1"] = np.mean(f1_scores) if f1_scores else 0.0
        results["overall"]["num_modes_trained"] = len(self.classifiers)

        return results

    def predict(self, record: Dict[str, Any]) -> Dict[str, bool]:
        """Predict failure modes for a single record.

        Args:
            record: MAST record

        Returns:
            Dict mapping failure modes to predictions
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        # Extract features
        features = self.feature_extractor.extract_features(record)

        # Compute embedding if needed
        if self.use_embeddings:
            self.feature_extractor.compute_embeddings([features])

        # Get feature vector
        X = self.extract_feature_vector(features).reshape(1, -1)

        # Predict for each mode
        predictions = {}
        for mode, clf in self.classifiers.items():
            scaler = self.feature_scalers[mode]
            X_scaled = scaler.transform(X)
            predictions[mode] = bool(clf.predict(X_scaled)[0])

        return predictions

    def predict_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, bool]]:
        """Predict failure modes for multiple records.

        Args:
            records: List of MAST records

        Returns:
            List of prediction dicts
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        # Extract features
        features_list = [
            self.feature_extractor.extract_features(r) for r in records
        ]

        # Compute embeddings in batch
        if self.use_embeddings:
            self.feature_extractor.compute_embeddings(features_list)

        # Get feature matrix
        X = np.array([self.extract_feature_vector(f) for f in features_list])

        # Predict for each mode
        all_predictions = [{} for _ in records]

        for mode, clf in self.classifiers.items():
            scaler = self.feature_scalers[mode]
            X_scaled = scaler.transform(X)
            preds = clf.predict(X_scaled)

            for i, pred in enumerate(preds):
                all_predictions[i][mode] = bool(pred)

        return all_predictions

    def save(self, path: Path) -> None:
        """Save trained model to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save classifiers
        for mode, clf in self.classifiers.items():
            clf_path = path / f"clf_{mode}.pkl"
            with open(clf_path, "wb") as f:
                pickle.dump(clf, f)

        # Save scalers
        for mode, scaler in self.feature_scalers.items():
            scaler_path = path / f"scaler_{mode}.pkl"
            with open(scaler_path, "wb") as f:
                pickle.dump(scaler, f)

        # Save metadata
        meta = {
            "modes": list(self.classifiers.keys()),
            "model_type": self.model_type,
            "use_embeddings": self.use_embeddings,
        }
        with open(path / "metadata.json", "w") as f:
            json.dump(meta, f)

        logger.info(f"Model saved to {path}")

    def load(self, path: Path) -> None:
        """Load trained model from disk."""
        path = Path(path)

        # Load metadata
        with open(path / "metadata.json") as f:
            meta = json.load(f)

        self.model_type = meta["model_type"]
        self.use_embeddings = meta["use_embeddings"]

        # Load classifiers and scalers
        for mode in meta["modes"]:
            clf_path = path / f"clf_{mode}.pkl"
            scaler_path = path / f"scaler_{mode}.pkl"

            with open(clf_path, "rb") as f:
                self.classifiers[mode] = pickle.load(f)  # nosec B301 - trusted model file

            with open(scaler_path, "rb") as f:
                self.feature_scalers[mode] = pickle.load(f)  # nosec B301 - trusted model file

        self.is_trained = True
        logger.info(f"Model loaded from {path} ({len(self.classifiers)} modes)")


def train_on_mast(
    data_path: Path,
    output_path: Optional[Path] = None,
    model_type: str = "random_forest",
    use_embeddings: bool = True,
) -> Tuple[MLFailureDetector, Dict[str, Any]]:
    """Train ML detector on MAST dataset.

    Args:
        data_path: Path to MAD_full_dataset.json
        output_path: Optional path to save trained model
        model_type: Type of classifier to use
        use_embeddings: Whether to use text embeddings

    Returns:
        Trained detector and training results
    """
    # Load data
    with open(data_path) as f:
        records = json.load(f)

    logger.info(f"Loaded {len(records)} records from {data_path}")

    # Create and train detector
    detector = MLFailureDetector(
        use_embeddings=use_embeddings,
        model_type=model_type,
    )

    results = detector.train(records)

    # Save if path provided
    if output_path:
        detector.save(output_path)

    return detector, results


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Train ML failure detector")
    parser.add_argument("--data", type=Path, required=True, help="Path to MAST data")
    parser.add_argument("--output", type=Path, help="Path to save model")
    parser.add_argument("--model", choices=["random_forest", "gradient_boosting", "logistic"], default="random_forest")
    parser.add_argument("--no-embeddings", action="store_true", help="Disable text embeddings")

    args = parser.parse_args()

    detector, results = train_on_mast(
        data_path=args.data,
        output_path=args.output,
        model_type=args.model,
        use_embeddings=not args.no_embeddings,
    )

    print("\n" + "=" * 60)
    print("TRAINING RESULTS")
    print("=" * 60)

    for mode, metrics in sorted(results["modes"].items()):
        print(f"{mode}: F1={metrics['f1']:.1%}, P={metrics['precision']:.1%}, R={metrics['recall']:.1%}")

    print("-" * 60)
    print(f"Overall Macro F1: {results['overall']['macro_f1']:.1%}")
    print(f"Modes trained: {results['overall']['num_modes_trained']}")
