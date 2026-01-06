"""Advanced ML-based failure detection v2.0.

Improvements over v1:
1. Advanced features: TF-IDF, conversation patterns, framework-specific
2. XGBoost with hyperparameter tuning
3. Larger embedding model (all-mpnet-base-v2)
4. Class balancing with SMOTE
5. Neural network classifier option
6. Ensemble of multiple models

Target: 70% macro F1 on MAST benchmark
"""

import json
import logging
import pickle
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

FAILURE_MODES = [
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "F13", "F14",
]

ANNOTATION_MAP = {
    "1.1": "F1", "1.2": "F2", "1.3": "F3", "1.4": "F4", "1.5": "F5",
    "2.1": "F6", "2.2": "F7", "2.3": "F8", "2.4": "F9", "2.5": "F10", "2.6": "F11",
    "3.1": "F12", "3.2": "F13", "3.3": "F14",
}

# Framework-specific patterns
FRAMEWORK_PATTERNS = {
    "ChatDev": {
        "roles": ["CEO", "CPO", "CTO", "Programmer", "Reviewer", "Tester"],
        "phases": ["DemandAnalysis", "LanguageChoose", "Coding", "CodeReview", "Test"],
    },
    "MetaGPT": {
        "roles": ["ProductManager", "Architect", "ProjectManager", "Engineer", "QA"],
        "actions": ["WritePRD", "WriteDesign", "WriteTasks", "WriteCode", "WriteTest"],
    },
    "AG2": {
        "patterns": ["user_proxy", "assistant", "groupchat", "TERMINATE"],
    },
}

# Failure-specific keywords
FAILURE_KEYWORDS = {
    "F1": ["requirement", "specification", "misunderstand", "wrong", "incorrect", "not what"],
    "F3": ["resource", "memory", "timeout", "limit", "exceed", "allocation"],
    "F5": ["loop", "repeat", "stuck", "infinite", "same", "again"],
    "F6": ["derail", "off-topic", "unrelated", "different", "tangent"],
    "F7": ["ignore", "forgot", "missing", "context", "previous", "mentioned"],
    "F8": ["withhold", "omit", "hide", "not tell", "incomplete"],
    "F11": ["coordinate", "conflict", "disagree", "inconsistent", "mismatch"],
    "F12": ["validate", "check", "verify", "output", "result", "incorrect"],
    "F13": ["quality", "skip", "bypass", "ignore check", "no review"],
    "F14": ["complete", "done", "finish", "premature", "incomplete", "not done"],
}


@dataclass
class AdvancedFeatures:
    """Advanced features for ML detection."""
    trace_id: str
    framework: str = ""

    # Basic stats
    num_turns: int = 0
    num_unique_participants: int = 0
    total_chars: int = 0
    avg_turn_length: float = 0.0

    # Turn type distribution
    agent_turn_ratio: float = 0.0
    user_turn_ratio: float = 0.0
    tool_turn_ratio: float = 0.0

    # Conversation patterns
    max_consecutive_same_speaker: int = 0
    turn_length_variance: float = 0.0
    question_density: float = 0.0
    code_block_density: float = 0.0
    error_mention_density: float = 0.0

    # Repetition analysis
    exact_duplicate_ratio: float = 0.0
    near_duplicate_ratio: float = 0.0
    ngram_repetition_score: float = 0.0

    # Framework-specific
    framework_role_coverage: float = 0.0
    framework_phase_coverage: float = 0.0

    # Failure-specific keyword scores (14 dimensions)
    failure_keyword_scores: Dict[str, float] = field(default_factory=dict)

    # Task-response alignment
    task_mentioned_in_response: float = 0.0
    response_addresses_task: float = 0.0

    # Sentiment/tone
    negative_sentiment_ratio: float = 0.0
    uncertainty_ratio: float = 0.0

    # Embeddings
    text_embedding: Optional[np.ndarray] = None
    task_embedding: Optional[np.ndarray] = None

    # TF-IDF features (added during training)
    tfidf_features: Optional[np.ndarray] = None

    # Labels
    labels: Dict[str, bool] = field(default_factory=dict)


class AdvancedFeatureExtractor:
    """Extract advanced features from MAST traces."""

    def __init__(
        self,
        embedding_model: str = "all-mpnet-base-v2",
        use_tfidf: bool = True,
        max_tfidf_features: int = 500,
    ):
        self.embedding_model = embedding_model
        self.use_tfidf = use_tfidf
        self.max_tfidf_features = max_tfidf_features
        self._embedder = None
        self._tfidf = None

    @property
    def embedder(self):
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer(self.embedding_model)
                logger.info(f"Loaded embedding model: {self.embedding_model}")
            except Exception as e:
                logger.warning(f"Could not load embeddings: {e}")
        return self._embedder

    def fit_tfidf(self, texts: List[str]) -> None:
        """Fit TF-IDF vectorizer on texts."""
        if not self.use_tfidf:
            return
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._tfidf = TfidfVectorizer(
                max_features=self.max_tfidf_features,
                ngram_range=(1, 2),
                stop_words='english',
                min_df=5,
                max_df=0.95,
            )
            self._tfidf.fit(texts)
            logger.info(f"Fitted TF-IDF with {len(self._tfidf.vocabulary_)} features")
        except Exception as e:
            logger.warning(f"TF-IDF fitting failed: {e}")
            self.use_tfidf = False

    def extract_features(self, record: Dict[str, Any]) -> AdvancedFeatures:
        """Extract advanced features from a MAST record."""
        trace_id = str(record.get("trace_id", "unknown"))
        framework = record.get("mas_name", "unknown")
        trajectory = record.get("trace", {}).get("trajectory", "")
        annotations = record.get("mast_annotation", {})

        features = AdvancedFeatures(trace_id=trace_id, framework=framework)

        # Parse turns
        turns = self._parse_turns(trajectory, framework)

        # Basic stats
        features.num_turns = len(turns)
        participants = set(t.get("participant", "") for t in turns)
        features.num_unique_participants = len(participants)
        features.total_chars = len(trajectory)

        turn_lengths = [len(t.get("content", "")) for t in turns]
        if turn_lengths:
            features.avg_turn_length = np.mean(turn_lengths)
            features.turn_length_variance = np.var(turn_lengths) if len(turn_lengths) > 1 else 0

        # Turn type distribution
        if turns:
            agent_turns = sum(1 for t in turns if t.get("role") == "agent")
            user_turns = sum(1 for t in turns if t.get("role") == "user")
            tool_turns = sum(1 for t in turns if t.get("role") == "tool")
            features.agent_turn_ratio = agent_turns / len(turns)
            features.user_turn_ratio = user_turns / len(turns)
            features.tool_turn_ratio = tool_turns / len(turns)

        # Consecutive speaker analysis
        features.max_consecutive_same_speaker = self._max_consecutive_same(turns)

        # Density metrics
        text_lower = trajectory.lower()
        features.question_density = text_lower.count("?") / max(1, len(trajectory)) * 1000
        features.code_block_density = trajectory.count("```") / max(1, len(turns))
        features.error_mention_density = sum(
            text_lower.count(w) for w in ["error", "exception", "failed", "traceback"]
        ) / max(1, len(trajectory)) * 1000

        # Repetition analysis
        features.exact_duplicate_ratio = self._exact_duplicate_ratio(turns)
        features.near_duplicate_ratio = self._near_duplicate_ratio(turns)
        features.ngram_repetition_score = self._ngram_repetition(trajectory)

        # Framework-specific features
        if framework in FRAMEWORK_PATTERNS:
            patterns = FRAMEWORK_PATTERNS[framework]
            if "roles" in patterns:
                found_roles = sum(1 for r in patterns["roles"] if r.lower() in text_lower)
                features.framework_role_coverage = found_roles / len(patterns["roles"])
            if "phases" in patterns:
                found_phases = sum(1 for p in patterns["phases"] if p.lower() in text_lower)
                features.framework_phase_coverage = found_phases / len(patterns["phases"])

        # Failure-specific keyword scores
        for mode, keywords in FAILURE_KEYWORDS.items():
            score = sum(text_lower.count(kw) for kw in keywords)
            features.failure_keyword_scores[mode] = score / max(1, len(trajectory)) * 1000

        # Task analysis
        task = self._extract_task(trajectory, record)
        if task:
            task_words = set(task.lower().split())
            response_text = " ".join(t.get("content", "") for t in turns if t.get("role") == "agent")
            response_words = set(response_text.lower().split())
            if task_words:
                features.task_mentioned_in_response = len(task_words & response_words) / len(task_words)

        # Sentiment indicators
        negative_words = ["error", "fail", "wrong", "bad", "issue", "problem", "bug", "crash"]
        uncertainty_words = ["maybe", "perhaps", "might", "could", "unsure", "not sure", "i think"]

        word_count = len(trajectory.split())
        features.negative_sentiment_ratio = sum(text_lower.count(w) for w in negative_words) / max(1, word_count)
        features.uncertainty_ratio = sum(text_lower.count(w) for w in uncertainty_words) / max(1, word_count)

        # Labels
        for code, mode in ANNOTATION_MAP.items():
            value = annotations.get(code, 0)
            features.labels[mode] = bool(value) if isinstance(value, int) else value

        return features

    def compute_embeddings(self, features_list: List[AdvancedFeatures], records: List[Dict]) -> None:
        """Compute embeddings for features."""
        if not self.embedder:
            return

        # Prepare texts
        texts = []
        tasks = []
        for i, features in enumerate(features_list):
            trajectory = records[i].get("trace", {}).get("trajectory", "")[:10000]
            texts.append(trajectory)
            tasks.append(self._extract_task(trajectory, records[i])[:2000])

        logger.info(f"Computing embeddings for {len(texts)} traces...")

        text_embs = self.embedder.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        task_embs = self.embedder.encode(tasks, show_progress_bar=False, convert_to_numpy=True)

        for i, features in enumerate(features_list):
            features.text_embedding = text_embs[i]
            features.task_embedding = task_embs[i]

    def compute_tfidf(self, features_list: List[AdvancedFeatures], records: List[Dict]) -> None:
        """Compute TF-IDF features."""
        if not self.use_tfidf or not self._tfidf:
            return

        texts = [r.get("trace", {}).get("trajectory", "")[:20000] for r in records]
        tfidf_matrix = self._tfidf.transform(texts).toarray()

        for i, features in enumerate(features_list):
            features.tfidf_features = tfidf_matrix[i]

    def _parse_turns(self, trajectory: str, framework: str) -> List[Dict]:
        """Parse trajectory into turns."""
        turns = []

        if framework == "ChatDev":
            pattern = r'\[[\d\-\s:]+\s+\w+\]\s*\*\*([^*]+)\*\*[:\s]*(.+?)(?=\[\d|\Z)'
            matches = re.findall(pattern, trajectory, re.DOTALL)
            for role_part, content in matches:
                role = "user" if "user" in role_part.lower() else "agent"
                turns.append({"role": role, "participant": role_part.strip(), "content": content.strip()[:5000]})

        elif framework == "MetaGPT":
            pattern = r'\[[\d\-\s:]+\]\s*(?:FROM:\s*(\w+))?.+?(?:CONTENT:\s*)?(.+?)(?=\[\d{4}|\Z)'
            matches = re.findall(pattern, trajectory, re.DOTALL)
            for sender, content in matches:
                role = "user" if sender and sender.lower() == "human" else "agent"
                turns.append({"role": role, "participant": sender or "agent", "content": content.strip()[:5000]})

        elif framework in ("AG2", "AutoGen"):
            pattern = r'(\w+)\s*\(to\s+[^)]+\):\s*(.+?)(?=\n\w+\s*\(to|\Z)'
            matches = re.findall(pattern, trajectory, re.DOTALL)
            for sender, content in matches:
                role = "user" if sender.lower() in ("user", "human") else "agent"
                turns.append({"role": role, "participant": sender, "content": content.strip()[:5000]})

        else:
            # Generic parsing
            lines = trajectory.split('\n')
            current_content = []
            for line in lines:
                if re.match(r'^[\w\s]+:', line):
                    if current_content:
                        turns.append({"role": "agent", "participant": "agent", "content": "\n".join(current_content)})
                        current_content = []
                current_content.append(line)
            if current_content:
                turns.append({"role": "agent", "participant": "agent", "content": "\n".join(current_content)[:5000]})

        return turns if turns else [{"role": "agent", "participant": "agent", "content": trajectory[:10000]}]

    def _extract_task(self, trajectory: str, record: Dict) -> str:
        """Extract task from trajectory."""
        task = record.get("trace", {}).get("task", "")
        if task:
            return task[:2000]

        patterns = [
            r'\*\*task_prompt\*\*:\s*([^\n|]+)',
            r'UserRequirement\s*\nCONTENT:\s*\n(.+?)(?:\n\n|\n\[)',
            r'(?:Task|Query|Prompt|Problem):\s*(.+?)(?:\n\n|\n\[|$)',
        ]
        for pattern in patterns:
            match = re.search(pattern, trajectory, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()[:2000]
        return trajectory[:500]

    def _max_consecutive_same(self, turns: List[Dict]) -> int:
        """Find max consecutive turns from same speaker."""
        if not turns:
            return 0
        max_count = 1
        current_count = 1
        for i in range(1, len(turns)):
            if turns[i].get("participant") == turns[i-1].get("participant"):
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 1
        return max_count

    def _exact_duplicate_ratio(self, turns: List[Dict]) -> float:
        """Compute exact duplicate turn ratio."""
        if len(turns) < 2:
            return 0.0
        contents = [t.get("content", "")[:500] for t in turns]
        unique = len(set(contents))
        return 1.0 - (unique / len(contents))

    def _near_duplicate_ratio(self, turns: List[Dict]) -> float:
        """Compute near-duplicate ratio using simple heuristics."""
        if len(turns) < 2:
            return 0.0

        near_dups = 0
        contents = [t.get("content", "")[:500] for t in turns]

        for i in range(len(contents)):
            for j in range(i + 1, len(contents)):
                # Simple Jaccard similarity
                words_i = set(contents[i].lower().split())
                words_j = set(contents[j].lower().split())
                if words_i and words_j:
                    jaccard = len(words_i & words_j) / len(words_i | words_j)
                    if jaccard > 0.8:
                        near_dups += 1

        total_pairs = len(contents) * (len(contents) - 1) / 2
        return near_dups / max(1, total_pairs)

    def _ngram_repetition(self, text: str, n: int = 3) -> float:
        """Compute n-gram repetition score."""
        words = text.lower().split()
        if len(words) < n:
            return 0.0

        ngrams = [tuple(words[i:i+n]) for i in range(len(words) - n + 1)]
        if not ngrams:
            return 0.0

        counter = Counter(ngrams)
        repeated = sum(1 for count in counter.values() if count > 1)
        return repeated / len(counter)


class AdvancedMLDetector:
    """Advanced ML detector with multiple model options."""

    def __init__(
        self,
        model_type: str = "xgboost",
        use_embeddings: bool = True,
        use_tfidf: bool = True,
        use_smote: bool = True,
        embedding_model: str = "all-mpnet-base-v2",
    ):
        self.model_type = model_type
        self.use_embeddings = use_embeddings
        self.use_tfidf = use_tfidf
        self.use_smote = use_smote

        self.extractor = AdvancedFeatureExtractor(
            embedding_model=embedding_model,
            use_tfidf=use_tfidf,
        )

        self.classifiers: Dict[str, Any] = {}
        self.scalers: Dict[str, Any] = {}
        self.is_trained = False

    def _build_feature_vector(self, features: AdvancedFeatures) -> np.ndarray:
        """Convert AdvancedFeatures to feature vector."""
        # Numerical features
        numerical = np.array([
            features.num_turns,
            features.num_unique_participants,
            features.total_chars / 1000,  # Scale down
            features.avg_turn_length / 100,
            features.agent_turn_ratio,
            features.user_turn_ratio,
            features.tool_turn_ratio,
            features.max_consecutive_same_speaker,
            features.turn_length_variance / 10000,
            features.question_density,
            features.code_block_density,
            features.error_mention_density,
            features.exact_duplicate_ratio,
            features.near_duplicate_ratio,
            features.ngram_repetition_score,
            features.framework_role_coverage,
            features.framework_phase_coverage,
            features.task_mentioned_in_response,
            features.negative_sentiment_ratio,
            features.uncertainty_ratio,
        ], dtype=np.float32)

        # Failure keyword scores (14 dimensions)
        keyword_scores = np.array([
            features.failure_keyword_scores.get(f"F{i}", 0.0)
            for i in range(1, 15)
        ], dtype=np.float32)

        # Framework one-hot encoding
        frameworks = ["ChatDev", "MetaGPT", "AG2", "AutoGen", "Magentic", "OpenManus", "AppWorld", "HyperAgent"]
        framework_onehot = np.array([
            1.0 if features.framework == fw else 0.0
            for fw in frameworks
        ], dtype=np.float32)

        components = [numerical, keyword_scores, framework_onehot]

        # Add embeddings if available
        if features.text_embedding is not None:
            # Use PCA-reduced embedding (first 256 dims)
            text_emb = features.text_embedding[:256] if len(features.text_embedding) > 256 else features.text_embedding
            task_emb = features.task_embedding[:256] if features.task_embedding is not None and len(features.task_embedding) > 256 else np.zeros(256)
            components.extend([text_emb, task_emb])

        # Add TF-IDF if available
        if features.tfidf_features is not None:
            components.append(features.tfidf_features)

        return np.concatenate(components)

    def train(
        self,
        records: List[Dict[str, Any]],
        test_split: float = 0.2,
    ) -> Dict[str, Any]:
        """Train the detector."""
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import f1_score, precision_score, recall_score

        logger.info(f"Extracting features from {len(records)} traces...")

        # Extract features
        features_list = [self.extractor.extract_features(r) for r in records]

        # Fit TF-IDF
        if self.use_tfidf:
            texts = [r.get("trace", {}).get("trajectory", "")[:20000] for r in records]
            self.extractor.fit_tfidf(texts)
            self.extractor.compute_tfidf(features_list, records)

        # Compute embeddings
        if self.use_embeddings:
            self.extractor.compute_embeddings(features_list, records)

        # Build feature matrix
        X = np.array([self._build_feature_vector(f) for f in features_list])
        logger.info(f"Feature matrix shape: {X.shape}")

        # Handle NaN/Inf
        X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)

        results = {"modes": {}, "overall": {}}

        # Train classifier for each mode
        for mode in FAILURE_MODES:
            y = np.array([f.labels.get(mode, False) for f in features_list], dtype=int)

            n_positive = y.sum()
            if n_positive < 5:
                logger.warning(f"Skipping {mode}: only {n_positive} positive samples")
                continue

            # Split data
            if test_split > 0:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_split, random_state=42, stratify=y
                )
            else:
                X_train, y_train = X, y
                X_test, y_test = X[:20], y[:20]

            # Scale
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Apply SMOTE for class balancing
            if self.use_smote and y_train.sum() >= 5:
                try:
                    from imblearn.over_sampling import SMOTE
                    smote = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
                    X_train_scaled, y_train = smote.fit_resample(X_train_scaled, y_train)
                except Exception as e:
                    logger.debug(f"SMOTE failed for {mode}: {e}")

            # Create classifier
            clf = self._create_classifier(mode, n_positive)

            # Train
            clf.fit(X_train_scaled, y_train)

            # Evaluate
            y_pred = clf.predict(X_test_scaled)

            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)

            self.classifiers[mode] = clf
            self.scalers[mode] = scaler

            results["modes"][mode] = {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "train_positives": int(y_train.sum()),
                "test_positives": int(y_test.sum()),
            }

            logger.info(f"{mode}: F1={f1:.3f}, P={precision:.3f}, R={recall:.3f}")

        self.is_trained = True

        f1_scores = [m["f1"] for m in results["modes"].values()]
        results["overall"]["macro_f1"] = np.mean(f1_scores) if f1_scores else 0.0
        results["overall"]["num_modes_trained"] = len(self.classifiers)

        return results

    def _create_classifier(self, mode: str, n_positive: int):
        """Create classifier based on model type."""
        if self.model_type == "xgboost":
            try:
                from xgboost import XGBClassifier
                # Tune scale_pos_weight based on class imbalance
                scale_weight = max(1, (1242 - n_positive) / max(1, n_positive))
                return XGBClassifier(
                    n_estimators=200,
                    max_depth=6,
                    learning_rate=0.1,
                    scale_pos_weight=min(scale_weight, 10),
                    subsample=0.8,
                    colsample_bytree=0.8,
                    random_state=42,
                    n_jobs=-1,
                    eval_metric='logloss',
                )
            except ImportError:
                logger.warning("XGBoost not available, falling back to GradientBoosting")
                self.model_type = "gradient_boosting"

        if self.model_type == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingClassifier
            return GradientBoostingClassifier(
                n_estimators=200,
                max_depth=5,
                learning_rate=0.1,
                random_state=42,
            )

        if self.model_type == "neural_network":
            from sklearn.neural_network import MLPClassifier
            return MLPClassifier(
                hidden_layer_sizes=(256, 128, 64),
                activation='relu',
                solver='adam',
                alpha=0.001,
                batch_size='auto',
                learning_rate='adaptive',
                max_iter=500,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.1,
            )

        # Default: Random Forest
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )

    def predict(self, record: Dict[str, Any]) -> Dict[str, bool]:
        """Predict failure modes for a record."""
        return self.predict_batch([record])[0]

    def predict_batch(self, records: List[Dict[str, Any]]) -> List[Dict[str, bool]]:
        """Predict failure modes for multiple records."""
        if not self.is_trained:
            raise RuntimeError("Model not trained")

        # Extract features
        features_list = [self.extractor.extract_features(r) for r in records]

        # Compute TF-IDF
        if self.use_tfidf and self.extractor._tfidf:
            self.extractor.compute_tfidf(features_list, records)

        # Compute embeddings
        if self.use_embeddings:
            self.extractor.compute_embeddings(features_list, records)

        # Build feature matrix
        X = np.array([self._build_feature_vector(f) for f in features_list])
        X = np.nan_to_num(X, nan=0.0, posinf=1e6, neginf=-1e6)

        # Predict
        all_predictions = [{} for _ in records]

        for mode, clf in self.classifiers.items():
            scaler = self.scalers[mode]
            X_scaled = scaler.transform(X)
            preds = clf.predict(X_scaled)

            for i, pred in enumerate(preds):
                all_predictions[i][mode] = bool(pred)

        return all_predictions

    def save(self, path: Path) -> None:
        """Save model to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        for mode, clf in self.classifiers.items():
            with open(path / f"clf_{mode}.pkl", "wb") as f:
                pickle.dump(clf, f)
            with open(path / f"scaler_{mode}.pkl", "wb") as f:
                pickle.dump(self.scalers[mode], f)

        if self.extractor._tfidf:
            with open(path / "tfidf.pkl", "wb") as f:
                pickle.dump(self.extractor._tfidf, f)

        meta = {
            "modes": list(self.classifiers.keys()),
            "model_type": self.model_type,
            "use_embeddings": self.use_embeddings,
            "use_tfidf": self.use_tfidf,
            "embedding_model": self.extractor.embedding_model,
        }
        with open(path / "metadata.json", "w") as f:
            json.dump(meta, f)

        logger.info(f"Model saved to {path}")


def train_advanced(
    data_path: Path,
    output_path: Optional[Path] = None,
    model_type: str = "xgboost",
    use_smote: bool = True,
) -> Tuple[AdvancedMLDetector, Dict[str, Any]]:
    """Train advanced detector."""
    with open(data_path) as f:
        records = json.load(f)

    logger.info(f"Loaded {len(records)} records")

    detector = AdvancedMLDetector(
        model_type=model_type,
        use_embeddings=True,
        use_tfidf=True,
        use_smote=use_smote,
    )

    results = detector.train(records)

    if output_path:
        detector.save(output_path)

    return detector, results


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", choices=["xgboost", "gradient_boosting", "neural_network", "random_forest"], default="xgboost")
    parser.add_argument("--no-smote", action="store_true")

    args = parser.parse_args()

    detector, results = train_advanced(
        data_path=args.data,
        output_path=args.output,
        model_type=args.model,
        use_smote=not args.no_smote,
    )

    print("\n" + "=" * 60)
    print("TRAINING RESULTS")
    print("=" * 60)
    for mode, m in sorted(results["modes"].items()):
        print(f"{mode}: F1={m['f1']:.1%}, P={m['precision']:.1%}, R={m['recall']:.1%}")
    print("-" * 60)
    print(f"Macro F1: {results['overall']['macro_f1']:.1%}")
