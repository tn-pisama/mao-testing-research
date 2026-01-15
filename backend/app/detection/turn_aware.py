"""
Turn-Aware Detection for Multi-Turn Conversation Traces
========================================================

This module provides turn-aware detection algorithms that analyze entire
conversation traces rather than single states. These detectors are designed
for MAST-Data and similar multi-turn conversation benchmarks.

Key differences from state-based detectors:
1. Analyze accumulated context across turns
2. Track topic/intent drift over conversation
3. Detect patterns that emerge across multiple turns
4. Support participant-aware analysis (user vs agent vs tool)

Version History:
- v1.0: Initial implementation with turn-aware context neglect and derailment
- v1.1: Added sliding window support for long conversations
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Maximum turns before triggering summarization
MAX_TURNS_BEFORE_SUMMARIZATION = 50
MAX_TOKENS_BEFORE_SUMMARIZATION = 8000

# Module version
MODULE_VERSION = "1.1"  # Updated for semantic enhancements

# Embedding configuration
EMBEDDING_SIMILARITY_THRESHOLD = 0.7  # Below this = significant drift
EMBEDDING_AVAILABLE = None  # Lazy-loaded flag


def _check_embedding_available() -> bool:
    """Check if embedding service is available (lazy load)."""
    global EMBEDDING_AVAILABLE
    if EMBEDDING_AVAILABLE is None:
        try:
            from app.core.embeddings import get_embedder
            embedder = get_embedder()
            # Try a quick encode to verify it works
            _ = embedder.encode("test", is_query=True)
            EMBEDDING_AVAILABLE = True
            logger.info("Embedding service available for semantic detection")
        except Exception as e:
            EMBEDDING_AVAILABLE = False
            logger.warning(f"Embedding service not available, using keyword fallback: {e}")
    return EMBEDDING_AVAILABLE


class EmbeddingMixin:
    """Mixin providing embedding-based semantic analysis for detectors.

    Based on STATE_OF_THE_ART_DETECTOR_DESIGN.md recommendations:
    - Tier 2 detection using embedding similarity
    - Semantic drift detection for task alignment
    - Information density analysis
    """

    _embedder = None
    _embedder_lock = None  # Class-level lock for thread safety

    @classmethod
    def _get_embedder_lock(cls):
        """Get or create the class-level lock for embedder initialization."""
        if cls._embedder_lock is None:
            import threading
            cls._embedder_lock = threading.RLock()
        return cls._embedder_lock

    @property
    def embedder(self):
        """Lazy-load embedding service (thread-safe)."""
        lock = self._get_embedder_lock()
        with lock:
            if self._embedder is None and _check_embedding_available():
                try:
                    from app.core.embeddings import get_embedder
                    self._embedder = get_embedder()
                except Exception:
                    pass
        return self._embedder

    def semantic_similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts.

        Returns:
            Cosine similarity score (0-1), or -1 if embeddings unavailable
        """
        if not self.embedder:
            return -1.0

        try:
            emb1 = self.embedder.encode(text1, is_query=True)
            emb2 = self.embedder.encode(text2, is_query=False)
            return self.embedder.similarity(emb1, emb2)
        except Exception as e:
            logger.debug(f"Embedding similarity failed: {e}")
            return -1.0

    def batch_semantic_similarity(
        self,
        query: str,
        passages: List[str]
    ) -> List[float]:
        """Compute semantic similarity between query and multiple passages.

        Returns:
            List of similarity scores, or empty list if unavailable
        """
        if not self.embedder or not passages:
            return []

        try:
            query_emb = self.embedder.encode_query(query)
            passage_embs = self.embedder.encode_passages(passages)
            similarities = self.embedder.batch_similarity(query_emb, passage_embs)
            return similarities.tolist()
        except Exception as e:
            logger.debug(f"Batch embedding similarity failed: {e}")
            return []

    def detect_semantic_drift(
        self,
        reference: str,
        responses: List[str],
        threshold: float = EMBEDDING_SIMILARITY_THRESHOLD
    ) -> Dict[str, Any]:
        """Detect semantic drift from reference text across multiple responses.

        Based on MAST research: embedding similarity < 0.7 indicates significant drift.

        Returns:
            Dict with drift analysis including scores and drifted indices
        """
        similarities = self.batch_semantic_similarity(reference, responses)

        if not similarities:
            return {"available": False}

        drifted_indices = [i for i, sim in enumerate(similarities) if sim < threshold]
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0

        # Detect progressive drift (similarity decreasing over time)
        progressive = False
        if len(similarities) >= 3:
            first_half = similarities[:len(similarities)//2]
            second_half = similarities[len(similarities)//2:]
            first_avg = sum(first_half) / len(first_half) if first_half else 0
            second_avg = sum(second_half) / len(second_half) if second_half else 0
            progressive = second_avg < first_avg - 0.1  # 10% degradation

        return {
            "available": True,
            "similarities": similarities,
            "avg_similarity": avg_similarity,
            "drifted_indices": drifted_indices,
            "drift_detected": len(drifted_indices) > 0,
            "progressive_drift": progressive,
            "threshold": threshold,
        }

    def compute_information_density(self, text: str) -> float:
        """Estimate information density of text.

        Higher values = more substantive content.
        Based on: unique terms, sentence complexity, specificity markers.
        """
        if not text:
            return 0.0

        words = text.lower().split()
        if not words:
            return 0.0

        # Unique word ratio
        unique_ratio = len(set(words)) / len(words)

        # Specificity markers (numbers, technical terms, proper nouns)
        import re
        numbers = len(re.findall(r'\b\d+(?:\.\d+)?\b', text))
        technical = len(re.findall(r'\b[A-Z][a-z]*[A-Z]\w*\b', text))  # camelCase

        # Sentence complexity (words per sentence)
        sentences = max(1, text.count('.') + text.count('!') + text.count('?'))
        words_per_sentence = len(words) / sentences

        # Combine metrics
        density = (
            unique_ratio * 0.4 +
            min(1.0, numbers / 10) * 0.2 +
            min(1.0, technical / 5) * 0.2 +
            min(1.0, words_per_sentence / 20) * 0.2
        )

        return min(1.0, density)

    def contrastive_similarity(
        self,
        anchor: str,
        positive: str,
        negative: str,
        mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compute contrastive similarity using triplet comparison.

        Uses TRACE framework approach: anchor should be more similar to
        positive than to negative by a margin.

        Args:
            anchor: Reference text (e.g., the trace being analyzed)
            positive: Example of expected behavior
            negative: Example of failure/anomaly
            mode: MAST failure mode for model selection

        Returns:
            Dict with similarity scores and classification
        """
        if not self.embedder:
            return {"available": False}

        try:
            result = self.embedder.compute_contrastive_score(
                anchor=anchor,
                positive=positive,
                negative=negative,
            )
            result["available"] = True

            # Classify based on which example is closer
            if result["pos_sim"] > result["neg_sim"]:
                result["classification"] = "normal"
                result["confidence"] = result["margin_score"]
            else:
                result["classification"] = "anomaly"
                result["confidence"] = -result["margin_score"]

            return result
        except Exception as e:
            logger.debug(f"Contrastive similarity failed: {e}")
            return {"available": False, "error": str(e)}

    def batch_semantic_drift(
        self,
        reference: str,
        responses: List[str],
        window_size: int = 3,
        threshold: float = EMBEDDING_SIMILARITY_THRESHOLD,
    ) -> Dict[str, Any]:
        """Detect semantic drift using efficient batch processing.

        Optimized for long traces by:
        1. Using sliding window for local drift detection
        2. Computing trend line for progressive drift
        3. Identifying sudden drift points

        Args:
            reference: Original task/context text
            responses: List of agent responses in order
            window_size: Size of sliding window for local analysis
            threshold: Similarity threshold for drift detection

        Returns:
            Dict with comprehensive drift analysis
        """
        if not self.embedder or not responses:
            return {"available": False}

        try:
            # Get similarities using parent method
            similarities = self.batch_semantic_similarity(reference, responses)
            if not similarities:
                return {"available": False}

            n = len(similarities)

            # Find drift points (sudden drops)
            drift_points = []
            for i in range(1, n):
                if similarities[i-1] - similarities[i] > 0.15:  # 15% drop
                    drift_points.append({
                        "index": i,
                        "drop": similarities[i-1] - similarities[i],
                        "before": similarities[i-1],
                        "after": similarities[i],
                    })

            # Sliding window analysis
            window_avgs = []
            for i in range(n - window_size + 1):
                window = similarities[i:i + window_size]
                window_avgs.append(sum(window) / len(window))

            # Compute trend (linear regression slope)
            if n >= 3:
                x = list(range(n))
                x_mean = sum(x) / n
                y_mean = sum(similarities) / n
                numerator = sum((x[i] - x_mean) * (similarities[i] - y_mean) for i in range(n))
                denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
                slope = numerator / denominator if denominator != 0 else 0
            else:
                slope = 0

            # Classify drift severity
            avg_sim = sum(similarities) / n
            drifted_count = sum(1 for s in similarities if s < threshold)

            if slope < -0.05 and drifted_count > n // 2:
                severity = "severe"
            elif slope < -0.02 or drifted_count > n // 3:
                severity = "moderate"
            elif drifted_count > 0:
                severity = "mild"
            else:
                severity = "none"

            return {
                "available": True,
                "similarities": similarities,
                "avg_similarity": avg_sim,
                "min_similarity": min(similarities),
                "max_similarity": max(similarities),
                "trend_slope": slope,
                "drift_points": drift_points,
                "window_averages": window_avgs,
                "drifted_count": drifted_count,
                "drifted_indices": [i for i, s in enumerate(similarities) if s < threshold],
                "severity": severity,
                "progressive_drift": slope < -0.02,
                "sudden_drift": len(drift_points) > 0,
            }
        except Exception as e:
            logger.debug(f"Batch semantic drift failed: {e}")
            return {"available": False, "error": str(e)}


class TurnAwareSeverity(str, Enum):
    """Severity levels for turn-aware detections."""
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass
class TurnSnapshot:
    """Snapshot of a single turn in a conversation.

    Similar to StateSnapshot but designed for conversation analysis,
    capturing the context flow between participants.
    """
    turn_number: int
    participant_type: str  # user, agent, system, tool
    participant_id: str
    content: str
    content_hash: Optional[str] = None
    accumulated_context: Optional[str] = None
    accumulated_tokens: int = 0
    turn_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.content_hash is None:
            self.content_hash = hashlib.sha256(
                self.content.encode()
            ).hexdigest()[:16]


@dataclass
class TurnAwareDetectionResult:
    """Result from a turn-aware detector."""
    detected: bool
    severity: TurnAwareSeverity
    confidence: float
    failure_mode: Optional[str]  # F1-F14 mapping
    explanation: str
    affected_turns: List[int] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    suggested_fix: Optional[str] = None
    detector_name: str = ""
    detector_version: str = MODULE_VERSION


class TurnAwareDetector(ABC):
    """Abstract base class for turn-aware detectors.

    Turn-aware detectors analyze entire conversation traces,
    looking for patterns that emerge across multiple turns.
    """

    name: str = "TurnAwareDetector"
    version: str = MODULE_VERSION
    supported_failure_modes: List[str] = []

    @abstractmethod
    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Analyze conversation turns for failures.

        Args:
            turns: List of conversation turns in order
            conversation_metadata: Optional metadata about the conversation

        Returns:
            Detection result with findings
        """
        pass

    def get_config(self) -> Dict[str, Any]:
        """Return detector configuration for versioning."""
        return {
            "name": self.name,
            "version": self.version,
            "supported_failure_modes": self.supported_failure_modes,
        }


class TurnAwareContextNeglectDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F7: Context Neglect across conversation turns.

    Analyzes whether agents properly utilize context from:
    1. Previous turns in the conversation
    2. User instructions and requirements
    3. Tool/system outputs

    Uses accumulated context tracking to detect when information
    is "lost" or ignored as the conversation progresses.

    Enhanced with semantic embeddings (v2.0):
    - Embedding-based context utilization scoring
    - Semantic similarity to detect topic alignment even with different words
    - Information density analysis for substantive responses

    Based on MAST research (NeurIPS 2025): FM-1.4 Loss of Conversation History (12%)
    """

    name = "TurnAwareContextNeglectDetector"
    version = "2.0"  # Semantic enhancement
    supported_failure_modes = ["F7"]

    # Code patterns that indicate a code response
    CODE_PATTERNS = [
        "def ", "class ", "import ", "from ", "function ",
        "const ", "let ", "var ", "return ", "if (", "if(",
        "for (", "for(", "while ", "=>", "```", "{", "}",
        "self.", "this.", "async ", "await ",
    ]

    # Explicit neglect indicators - agent explicitly ignoring or misunderstanding
    # Enhanced for MAST benchmark patterns
    NEGLECT_INDICATORS = [
        "instead", "rather than", "not what you asked",
        "different topic", "unrelated", "i'll analyze",
        "let me look at", "i'll check",
        # Added for better MAST recall
        "i'll focus on", "let me try", "actually",
        "ignore", "skip", "disregard", "missing the point",
        "that's not", "not related", "off-topic",
        "weather", "temperature",  # Common wrong-topic responses
    ]

    def __init__(
        self,
        utilization_threshold: float = 0.08,  # Raised from 0.03 to reduce FPs (16.2% FPR)
        min_context_length: int = 40,  # Reduced to catch shorter context issues
        check_user_instructions: bool = True,
        check_tool_outputs: bool = True,
        require_explicit_neglect: bool = False,  # Enable implicit detection for F7
        min_issues_to_flag: int = 2,  # Raised from 1 to reduce FPs
    ):
        self.utilization_threshold = utilization_threshold
        self.min_context_length = min_context_length
        self.check_user_instructions = check_user_instructions
        self.check_tool_outputs = check_tool_outputs
        self.require_explicit_neglect = require_explicit_neglect
        self.min_issues_to_flag = min_issues_to_flag

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect context neglect across conversation turns."""
        if len(turns) < 2:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to analyze",
                detector_name=self.name,
            )

        # Separate turns by participant type
        user_turns = [t for t in turns if t.participant_type == "user"]
        agent_turns = [t for t in turns if t.participant_type == "agent"]
        tool_turns = [t for t in turns if t.participant_type == "tool"]
        system_turns = [t for t in turns if t.participant_type == "system"]

        neglect_issues = []
        affected_turns = []

        # Detect if this is a multi-agent conversation (no user turns, multiple agents)
        is_multi_agent = not user_turns and len(agent_turns) >= 3

        if is_multi_agent:
            # MULTI-AGENT MODE: Check if agents ignore accumulated context
            # In ChatDev/MetaGPT, context neglect = agent ignores key info from prior turns
            neglect_issues.extend(self._check_multi_agent_context_neglect(turns, agent_turns))
            for issue in neglect_issues:
                affected_turns.append(issue.get("turn", 0))
        else:
            # TRADITIONAL MODE: User-agent conversation
            # Handle systems where task comes from system prompt
            synthetic_user_turns = []
            agents_to_check = agent_turns
            if user_turns:
                synthetic_user_turns = user_turns
            elif system_turns and any(len(t.content) > 50 for t in system_turns):
                synthetic_user_turns = [t for t in system_turns if len(t.content) > 50]
            elif agent_turns:
                synthetic_user_turns = [agent_turns[0]]
                agents_to_check = agent_turns[1:]

            # Check 1: Agent responses vs user instructions
            if self.check_user_instructions and synthetic_user_turns and agents_to_check:
                for agent_turn in agents_to_check:
                    prior_user_turns = [
                        u for u in synthetic_user_turns
                        if u.turn_number < agent_turn.turn_number
                    ]
                    if not prior_user_turns:
                        continue

                    immediate_user = max(prior_user_turns, key=lambda u: u.turn_number)
                    user_context = immediate_user.content

                    if self._is_code_response(agent_turn.content):
                        if self._is_code_request(user_context):
                            continue

                    has_explicit_neglect = self._has_explicit_neglect(
                        user_context, agent_turn.content
                    )

                    if has_explicit_neglect:
                        neglect_issues.append({
                            "type": "explicit_neglect",
                            "turn": agent_turn.turn_number,
                            "description": f"Agent turn {agent_turn.turn_number} explicitly ignored user request",
                        })
                        affected_turns.append(agent_turn.turn_number)
                    elif not self.require_explicit_neglect:
                        utilization = self._compute_utilization(
                            user_context, agent_turn.content
                        )
                        if utilization < self.utilization_threshold:
                            neglect_issues.append({
                                "type": "user_instruction_neglect",
                                "turn": agent_turn.turn_number,
                                "utilization": utilization,
                                "description": f"Agent turn {agent_turn.turn_number} poorly utilized user context",
                            })
                            affected_turns.append(agent_turn.turn_number)

        # Check 2: Agent responses vs tool outputs
        if self.check_tool_outputs and tool_turns and agent_turns:
            for agent_turn in agent_turns:
                # Find tool turns immediately before this agent turn
                prior_tool_turns = [
                    t for t in tool_turns
                    if t.turn_number < agent_turn.turn_number
                    and t.turn_number >= agent_turn.turn_number - 3  # Within 3 turns
                ]
                if prior_tool_turns:
                    tool_context = "\n".join(t.content for t in prior_tool_turns)
                    if len(tool_context) >= self.min_context_length:
                        # For tool outputs, check if key data is referenced
                        if self._ignores_tool_data(tool_context, agent_turn.content):
                            neglect_issues.append({
                                "type": "tool_output_neglect",
                                "turn": agent_turn.turn_number,
                                "description": f"Agent turn {agent_turn.turn_number} ignored tool output",
                            })
                            affected_turns.append(agent_turn.turn_number)

        # NOTE: Removed context_drift check - repetition is F5's job, not F7

        # Require minimum issues to reduce false positives
        if len(neglect_issues) < self.min_issues_to_flag:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Insufficient evidence ({len(neglect_issues)} issue(s), need {self.min_issues_to_flag}+)",
                detector_name=self.name,
            )

        # Determine severity based on number and type of issues
        if len(neglect_issues) >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif len(neglect_issues) >= 2 or any(i["type"] == "explicit_neglect" for i in neglect_issues):
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.95, 0.5 + len(neglect_issues) * 0.15)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F7",
            explanation=f"Context neglect detected in {len(neglect_issues)} instances",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": neglect_issues,
                "total_turns": len(turns),
                "agent_turns": len(agent_turns),
            },
            suggested_fix=(
                "Ensure agent prompts explicitly reference accumulated conversation context. "
                "Add context window management to prevent information loss."
            ),
            detector_name=self.name,
        )

    def _is_code_response(self, content: str) -> bool:
        """Check if response contains code."""
        content_lower = content.lower()
        code_pattern_count = sum(1 for p in self.CODE_PATTERNS if p.lower() in content_lower)
        return code_pattern_count >= 2

    def _is_code_request(self, content: str) -> bool:
        """Check if user is asking for code."""
        code_keywords = [
            "write", "code", "function", "implement", "create",
            "program", "script", "fix", "debug", "add", "python",
            "javascript", "java", "def", "class", "method",
        ]
        content_lower = content.lower()
        return any(kw in content_lower for kw in code_keywords)

    def _has_explicit_neglect(self, user_context: str, agent_response: str) -> bool:
        """Check for explicit signs of ignoring user context."""
        response_lower = agent_response.lower()
        context_lower = user_context.lower()

        # Check if agent mentions doing something else
        for indicator in self.NEGLECT_INDICATORS:
            if indicator in response_lower:
                # Verify it's not the user's correction
                if indicator not in context_lower:
                    return True

        # Check for topic mismatch: user asks about X, agent talks about Y
        # Extract key nouns from both
        user_topics = self._extract_topics(context_lower)
        agent_topics = self._extract_topics(response_lower)

        if user_topics and agent_topics:
            overlap = user_topics & agent_topics
            if len(overlap) == 0 and not self._is_code_response(agent_response):
                # No topic overlap and not a code response = likely neglect
                return True

        return False

    def _extract_topics(self, text: str) -> set:
        """Extract main topic words from text."""
        # Common domain-specific keywords that indicate topic
        # Enhanced for MAST benchmark diversity
        topic_indicators = {
            "sales", "data", "analysis", "report", "weather", "temperature",
            "calculator", "function", "code", "implementation", "database",
            "user", "authentication", "api", "server", "client", "file",
            "error", "bug", "test", "performance", "security", "config",
            # Added for better MAST coverage
            "upload", "download", "login", "register", "password", "email",
            "todo", "task", "list", "game", "chat", "message", "search",
            "product", "order", "cart", "payment", "invoice", "customer",
            "document", "image", "video", "audio", "pdf", "export", "import",
        }
        words = set(text.split())
        return words & topic_indicators

    def _ignores_tool_data(self, tool_output: str, agent_response: str) -> bool:
        """Check if agent ignores important data from tool output."""
        # Look for numbers, names, or key data in tool output
        import re

        # Extract numbers from tool output
        numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', tool_output))
        response_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', agent_response))

        # If tool output has significant numbers and none appear in response
        if len(numbers) >= 3 and len(numbers & response_numbers) == 0:
            return True

        return False

    def _compute_utilization(self, context: str, output: str) -> float:
        """Compute how much of the context is reflected in the output.

        Enhanced with semantic similarity (v2.0):
        - Uses embedding similarity when available (more accurate)
        - Falls back to word overlap for speed or when unavailable
        """
        # Try semantic similarity first (more accurate for different phrasings)
        similarity = self.semantic_similarity(context, output)
        if similarity >= 0:  # Embeddings available
            return similarity

        # Fallback to keyword-based
        context_words = set(w.lower() for w in context.split() if len(w) > 3)
        output_words = set(w.lower() for w in output.split() if len(w) > 3)

        if not context_words:
            return 1.0

        overlap = context_words & output_words
        return len(overlap) / len(context_words)

    def _check_semantic_context_alignment(
        self,
        user_context: str,
        agent_response: str,
        threshold: float = 0.5
    ) -> Dict[str, Any]:
        """Check if agent response semantically aligns with user context.

        Returns dict with alignment analysis.
        """
        similarity = self.semantic_similarity(user_context, agent_response)

        if similarity < 0:  # Embeddings unavailable
            return {"available": False}

        # Also check information density of response
        response_density = self.compute_information_density(agent_response)

        return {
            "available": True,
            "similarity": similarity,
            "aligned": similarity >= threshold,
            "response_density": response_density,
            "low_density": response_density < 0.3,  # Very sparse response
        }

    def _check_multi_agent_context_neglect(
        self,
        all_turns: List[TurnSnapshot],
        agent_turns: List[TurnSnapshot],
    ) -> List[Dict[str, Any]]:
        """Check for context neglect in multi-agent conversations.

        In multi-agent systems (ChatDev, MetaGPT), F7 occurs when:
        1. Agents don't reference key information from earlier turns
        2. Low semantic coherence between task and later execution
        3. Evidence of "forgotten" context or repeated clarifications

        Detection approach:
        - Track key topic words from task description
        - Check semantic coherence across conversation
        - Detect low information transfer from early to late turns
        """
        import re

        issues = []

        if len(agent_turns) < 5:
            return issues

        # Step 1: Extract task topic from early turns (first 2-3 substantive turns)
        early_turns = [t for t in agent_turns[:4] if len(t.content) > 100]
        if not early_turns:
            return issues

        task_content = " ".join(t.content for t in early_turns)
        task_keywords = self._extract_task_keywords(task_content)

        if len(task_keywords) < 3:
            return issues

        # Step 2: Check middle turns for context coherence
        # F7 often manifests in the middle of conversation where agents "forget"
        mid_start = len(agent_turns) // 3
        mid_end = 2 * len(agent_turns) // 3
        middle_turns = agent_turns[mid_start:mid_end] if mid_end > mid_start else []

        for turn in middle_turns:
            if len(turn.content) < 50:
                continue

            turn_lower = turn.content.lower()
            turn_words = set(turn_lower.split())

            # Check keyword overlap with task
            overlap = len(task_keywords & turn_words)
            overlap_ratio = overlap / len(task_keywords)

            # Very low overlap in a substantive turn suggests context neglect
            if len(turn.content) > 200 and overlap_ratio < 0.1:
                # Additional check: is this turn about something completely different?
                if not self._is_code_response(turn.content):
                    issues.append({
                        "type": "low_context_coherence",
                        "turn": turn.turn_number,
                        "description": f"Turn {turn.turn_number} has low coherence with task context",
                        "overlap_ratio": overlap_ratio,
                    })

        # Step 3: Check for explicit neglect indicators
        neglect_indicators = [
            "forgot", "forgotten", "didn't mention", "wasn't clear",
            "misunderstood", "wrong assumption", "actually",
            "wait", "hold on", "let me reconsider", "missed",
        ]

        for i, turn in enumerate(agent_turns[3:], start=3):
            turn_lower = turn.content.lower()
            for indicator in neglect_indicators:
                if indicator in turn_lower:
                    # Check if this seems like catching a mistake
                    context = turn_lower[max(0, turn_lower.find(indicator)-30):turn_lower.find(indicator)+50]
                    if any(x in context for x in ["requirement", "task", "should", "need", "must"]):
                        issues.append({
                            "type": "explicit_neglect_recovery",
                            "turn": turn.turn_number,
                            "description": f"Agent catches forgotten context: '{indicator}'",
                        })
                        break

        # Step 4: Check for re-asking questions (strong signal)
        question_patterns = [
            r"what (?:is|are|should|would)",
            r"how (?:do|should|would|can)",
            r"could you (?:clarify|explain|tell)",
            r"can you (?:clarify|explain|tell)",
        ]

        for i, turn in enumerate(agent_turns[4:], start=4):
            turn_lower = turn.content.lower()
            for pattern in question_patterns:
                if re.search(pattern, turn_lower):
                    # Extract what's being asked
                    match = re.search(pattern + r"\s+(\w+(?:\s+\w+){0,3})", turn_lower)
                    if match:
                        asked_topic = match.group(1) if match.lastindex else ""
                        # Check if this was discussed in earlier turns
                        earlier = " ".join(t.content.lower() for t in agent_turns[:i])
                        topic_words = [w for w in asked_topic.split() if len(w) > 3]
                        if topic_words:
                            found = sum(1 for w in topic_words if w in earlier)
                            if found >= len(topic_words) * 0.6:
                                issues.append({
                                    "type": "re_asks_discussed_topic",
                                    "turn": turn.turn_number,
                                    "description": f"Re-asks about already discussed: {asked_topic[:30]}",
                                })
                                break

        # Prioritize and return issues
        # Strong signals: explicit_neglect_recovery, re_asks_discussed_topic
        # Weak signals: low_context_coherence
        strong_issues = [i for i in issues if i["type"] in ("explicit_neglect_recovery", "re_asks_discussed_topic")]
        weak_issues = [i for i in issues if i["type"] == "low_context_coherence"]

        if strong_issues:
            return strong_issues[:2]
        elif len(weak_issues) >= 2:
            # Multiple low coherence turns = likely context neglect
            return weak_issues[:2]

        return []

    def _extract_task_keywords(self, text: str) -> set:
        """Extract key task-related keywords from early conversation.

        Focuses on technical terms, product names, and specific requirements
        that should be maintained throughout the conversation.
        """
        import re
        keywords = set()
        text_lower = text.lower()

        # Extract programming-related terms
        prog_terms = re.findall(r'\b(python|java|javascript|react|django|flask|api|database|sql|cli|gui|web|app|file|data|user|input|output|function|class|method)\b', text_lower)
        keywords.update(prog_terms)

        # Extract quoted terms (often specific requirements)
        quoted = re.findall(r'"([^"]+)"', text)
        for q in quoted:
            keywords.update(w.lower() for w in q.split() if len(w) > 3)

        # Extract CamelCase terms (class/component names)
        camel = re.findall(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', text)
        keywords.update(c.lower() for c in camel)

        # Extract snake_case terms
        snake = re.findall(r'\b([a-z]+_[a-z_]+)\b', text)
        keywords.update(snake)

        # Extract key nouns that appear multiple times
        words = re.findall(r'\b[a-z]{4,}\b', text_lower)
        word_counts = {}
        for w in words:
            word_counts[w] = word_counts.get(w, 0) + 1
        frequent = [w for w, c in word_counts.items() if c >= 2]
        keywords.update(frequent[:10])

        # Remove common stop words
        stop_words = {'that', 'this', 'with', 'from', 'have', 'will', 'been', 'were', 'they', 'their', 'would', 'could', 'should', 'about', 'into', 'more', 'some', 'such', 'than', 'then', 'them', 'when', 'where', 'which', 'while', 'your'}
        keywords -= stop_words

        return keywords

    def _extract_requirements(self, text: str) -> List[str]:
        """Extract requirements/constraints from task description."""
        requirements = []
        text_lower = text.lower()

        # Patterns that indicate requirements
        req_patterns = [
            r"must\s+(\w+(?:\s+\w+){0,5})",
            r"should\s+(\w+(?:\s+\w+){0,5})",
            r"need(?:s)?\s+to\s+(\w+(?:\s+\w+){0,5})",
            r"require(?:s|d)?\s+(\w+(?:\s+\w+){0,5})",
            r"implement\s+(\w+(?:\s+\w+){0,5})",
            r"ensure\s+(\w+(?:\s+\w+){0,5})",
            r"include\s+(\w+(?:\s+\w+){0,5})",
        ]

        import re
        for pattern in req_patterns:
            matches = re.findall(pattern, text_lower)
            requirements.extend(matches)

        return list(set(requirements))[:10]  # Limit to top 10

    def _extract_key_entities(self, text: str) -> set:
        """Extract key named entities from text."""
        # Simple entity extraction - focus on technical terms
        import re
        words = re.findall(r'\b[A-Z][a-zA-Z]+(?:[A-Z][a-zA-Z]+)*\b', text)  # CamelCase
        words += re.findall(r'\b[a-z]+_[a-z_]+\b', text)  # snake_case
        return set(words)

    def _check_for_contradiction(self, prior_context: str, current_turn: str) -> Optional[str]:
        """Check if current turn contradicts prior context."""
        prior_lower = prior_context.lower()
        current_lower = current_turn.lower()

        # Contradiction patterns
        if "cli" in prior_lower and "gui" in current_lower:
            if "instead of cli" in current_lower or "not cli" in current_lower:
                return "Changed from CLI to GUI requirement"

        if "web" in prior_lower and "desktop" in current_lower:
            if "instead" in current_lower or "change to" in current_lower:
                return "Changed platform requirement"

        # Check for explicit contradictions
        contradiction_markers = ["actually", "instead", "rather than", "change to", "not what"]
        for marker in contradiction_markers:
            if marker in current_lower:
                # Check if it's contradicting something from prior context
                idx = current_lower.find(marker)
                context_around = current_lower[max(0, idx-50):idx+50]
                if any(word in context_around for word in ["requirement", "task", "original", "specification"]):
                    return f"Explicit change detected near '{marker}'"

        return None

    def _is_decision_turn(self, content: str) -> bool:
        """Check if this turn makes a decision that should consider requirements."""
        decision_indicators = [
            "i will", "i'll", "let me", "let's", "we will", "we'll",
            "implementing", "creating", "building", "developing",
            "the approach", "my plan", "the solution", "the design",
            "decided to", "choosing", "selected",
        ]
        content_lower = content.lower()
        return any(ind in content_lower for ind in decision_indicators)

    def _check_missing_requirements(
        self,
        requirements: List[str],
        current_content: str,
        prior_turns: List[TurnSnapshot],
    ) -> List[str]:
        """Check which requirements are not addressed in the conversation so far."""
        if not requirements:
            return []

        # Build context from all prior turns
        all_content = current_content.lower()
        for turn in prior_turns:
            all_content += " " + turn.content.lower()

        missing = []
        for req in requirements:
            req_words = set(req.lower().split())
            # Check if requirement words appear in the conversation
            words_found = sum(1 for w in req_words if w in all_content)
            if words_found < len(req_words) * 0.5:  # Less than half the words found
                missing.append(req)

        return missing[:3]  # Return top 3 missing

    def _repeats_prior_work(
        self,
        current_content: str,
        prior_turns: List[TurnSnapshot],
    ) -> bool:
        """Check if current turn is repeating work from prior turns."""
        if len(prior_turns) < 2:
            return False

        current_lower = current_content.lower()

        # Check for phrases indicating repetition
        repeat_phrases = [
            "let me implement", "let me create", "let me write",
            "i will implement", "i will create", "i will write",
        ]

        for phrase in repeat_phrases:
            if phrase in current_lower:
                # Check if something similar was already done
                for prior in prior_turns[-5:]:  # Check last 5 turns
                    prior_lower = prior.content.lower()
                    if phrase.replace("let me ", "i ") in prior_lower or phrase in prior_lower:
                        return True

        return False


class TurnAwareDerailmentDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F6: Task Derailment across conversation turns.

    Tracks topic consistency and task focus across the conversation,
    detecting when:
    1. Agent responses drift from the original task
    2. Conversation topic changes unexpectedly
    3. Agent addresses wrong task or substitutes tasks

    Uses sliding window analysis to detect gradual drift.

    Enhanced with semantic embeddings (v2.0):
    - Embedding-based topic drift detection when available
    - Falls back to keyword-based for speed or when embeddings unavailable
    - Progressive drift detection using similarity trends

    Based on MAST research (NeurIPS 2025): FM-2.3 Task Derailment (20% prevalence)
    """

    name = "TurnAwareDerailmentDetector"
    version = "2.1"  # Phase 1: Benign pattern whitelisting
    supported_failure_modes = ["F6"]

    # Code patterns (shared with F7 detector logic)
    CODE_PATTERNS = [
        "def ", "class ", "import ", "from ", "function ",
        "const ", "let ", "var ", "return ", "if (", "if(",
        "for (", "for(", "while ", "=>", "```", "{", "}",
        "self.", "this.", "async ", "await ",
    ]

    # Phase 1: Framework-specific benign patterns (legitimate role transitions, not derailment)
    BENIGN_PATTERNS = {
        "ChatDev": [
            r"now switching to\b",
            r"role transition",
            r"moving to (?:the )?next (?:phase|stage)",
            r"switching (?:to|from) .+ (?:role|phase)",
            r"transitioning to",
            r"handing off to",
            r"passing (?:control|task) to",
        ],
        "AG2": [
            r"let me think",
            r"reasoning step",
            r"analyzing (?:the )?problem",
            r"breaking down (?:the )?task",
            r"let me (?:check|verify|validate)",
        ],
        "MetaGPT": [
            r"moving to implementation phase",
            r"switching context",
            r"proceeding to",
            r"transitioning from .+ to",
        ],
        "AutoGen": [
            r"delegating to",
            r"coordinating with",
            r"checking with",
        ],
        "default": [
            r"as (?:you )?(?:requested|asked)",
            r"to address your (?:question|request)",
            r"focusing on (?:the|your)",
        ],
    }

    def __init__(
        self,
        drift_threshold: float = 0.55,  # Lowered for better recall (was 0.70)
        min_turns_for_analysis: int = 3,
        window_size: int = 5,
        require_strong_evidence: bool = False,  # Disabled for MAST recall (was True)
        framework: Optional[str] = None,
    ):
        self.drift_threshold = drift_threshold
        self.min_turns_for_analysis = min_turns_for_analysis
        self.window_size = window_size
        self.require_strong_evidence = require_strong_evidence
        self.framework = framework
        self._embedder = None

    @property
    def embedder(self):
        if self._embedder is None:
            try:
                from app.core.embeddings import get_embedder
                self._embedder = get_embedder()
            except ImportError:
                logger.warning("EmbeddingService not available, using fallback")
                self._embedder = "fallback"
        return self._embedder

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect task derailment across conversation turns."""
        if len(turns) < self.min_turns_for_analysis:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to analyze for derailment",
                detector_name=self.name,
            )

        # Extract initial task/topic from first user turn (or first turn if all agents)
        user_turns = [t for t in turns if t.participant_type == "user"]
        agent_turns = [t for t in turns if t.participant_type == "agent"]
        system_turns = [t for t in turns if t.participant_type == "system"]

        # Handle multi-agent systems where all participants are "agent" role
        # (e.g., ChatDev where CEO gives task to Programmer)
        # The task can come from: user turns, system prompt, or first agent
        initial_task = None
        if user_turns:
            initial_task = user_turns[0].content
        elif system_turns and any(len(t.content) > 50 for t in system_turns):
            # Multi-agent: system prompt contains the task
            task_turns = [t for t in system_turns if len(t.content) > 50]
            initial_task = task_turns[0].content
        elif agent_turns:
            # Treat first agent as task-giver, rest as executors
            initial_task = agent_turns[0].content
            agent_turns = agent_turns[1:]  # Remaining agents to check for derailment

        if not initial_task or not agent_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="No user-agent interaction found",
                detector_name=self.name,
            )
        initial_terms = self._extract_key_terms(initial_task)

        # Check if user is asking for code
        is_code_task = self._is_code_task(initial_task)

        derailment_issues = []
        affected_turns = []
        high_drift_count = 0

        # OPTIMIZATION: Pre-filter turns and use batch similarity computation
        turns_to_check = []
        for agent_turn in agent_turns:
            # Skip drift check for code responses to code tasks
            if is_code_task and self._is_code_response(agent_turn.content):
                continue  # Code response to code task - don't flag as drift

            # Phase 1: Skip drift check for benign patterns (legitimate role transitions)
            if self._is_benign_pattern(agent_turn.content):
                continue  # Benign framework pattern - not derailment

            turns_to_check.append(agent_turn)

        # OPTIMIZATION: Compute drift scores in batch using batch_semantic_similarity
        similarities = []  # Initialize for progressive drift check
        if turns_to_check and self.embedder:
            turn_contents = [t.content for t in turns_to_check]
            similarities = self.batch_semantic_similarity(initial_task, turn_contents)

            if similarities:
                # Process batch results
                for i, (agent_turn, sim) in enumerate(zip(turns_to_check, similarities)):
                    drift_score = 1.0 - sim
                    coverage = sim

                    if drift_score > self.drift_threshold:
                        high_drift_count += 1
                        if not self.require_strong_evidence:
                            derailment_issues.append({
                                "type": "topic_drift",
                                "turn": agent_turn.turn_number,
                                "drift_score": drift_score,
                                "coverage": coverage,
                                "description": f"Agent turn {agent_turn.turn_number} drifted from task (drift={drift_score:.2f})",
                            })
                            affected_turns.append(agent_turn.turn_number)
            else:
                # Fallback to per-turn if batch fails
                for agent_turn in turns_to_check:
                    drift_score, coverage = self._compute_topic_drift(
                        initial_task, agent_turn.content
                    )
                    if drift_score > self.drift_threshold:
                        high_drift_count += 1
                        if not self.require_strong_evidence:
                            derailment_issues.append({
                                "type": "topic_drift",
                                "turn": agent_turn.turn_number,
                                "drift_score": drift_score,
                                "coverage": coverage,
                                "description": f"Agent turn {agent_turn.turn_number} drifted from task (drift={drift_score:.2f})",
                            })
                            affected_turns.append(agent_turn.turn_number)
        else:
            # No turns to check or no embedder - use keyword fallback per turn
            for agent_turn in turns_to_check:
                drift_score, coverage = self._compute_topic_drift(
                    initial_task, agent_turn.content, use_embeddings=False
                )
                if drift_score > self.drift_threshold:
                    high_drift_count += 1
                    if not self.require_strong_evidence:
                        derailment_issues.append({
                            "type": "topic_drift",
                            "turn": agent_turn.turn_number,
                            "drift_score": drift_score,
                            "coverage": coverage,
                            "description": f"Agent turn {agent_turn.turn_number} drifted from task (drift={drift_score:.2f})",
                        })
                        affected_turns.append(agent_turn.turn_number)

        # Check for progressive drift (getting worse over time)
        # OPTIMIZATION: Use pre-computed similarities to avoid re-encoding
        progressive_drift = {"detected": False}
        if len(turns_to_check) >= 3 and similarities:
            # Use pre-computed similarities from batch_semantic_similarity above
            progressive_drift = self._detect_progressive_drift_from_similarities(
                turns_to_check, similarities
            )
        elif len(agent_turns) >= 3 and not similarities:
            # Fallback only if no batch similarities were computed
            progressive_drift = self._detect_progressive_drift(
                initial_task, agent_turns, is_code_task
            )
        # Handle progressive drift detection result (from either path)
        if progressive_drift["detected"]:
            derailment_issues.append({
                "type": "progressive_drift",
                "turn": progressive_drift["worst_turn"],
                "description": "Agent responses progressively drifting from task",
                "drift_progression": progressive_drift.get("drift_scores", []),
            })
            affected_turns.append(progressive_drift["worst_turn"])

        # Check for task substitution (strongest signal)
        task_substitution = self._detect_task_substitution(
            initial_task, agent_turns
        )
        if task_substitution["detected"]:
            derailment_issues.append({
                "type": "task_substitution",
                "turn": task_substitution["turn"],
                "description": task_substitution["description"],
            })
            affected_turns.append(task_substitution["turn"])

        # If requiring strong evidence, only detect if we have:
        # 1. Task substitution, OR
        # 2. Progressive drift, OR
        # 3. Multiple (3+) high-drift turns
        if self.require_strong_evidence:
            has_strong_evidence = (
                task_substitution["detected"] or
                progressive_drift["detected"] or
                high_drift_count >= 3
            )
            if not has_strong_evidence:
                return TurnAwareDetectionResult(
                    detected=False,
                    severity=TurnAwareSeverity.NONE,
                    confidence=0.9,
                    failure_mode=None,
                    explanation="Agent maintained task focus across all turns",
                    detector_name=self.name,
                )
            # If we have strong evidence from high_drift_count, add drift issues
            elif high_drift_count >= 3 and not derailment_issues:
                derailment_issues.append({
                    "type": "high_drift",
                    "turn": "multiple",
                    "description": f"Multiple turns ({high_drift_count}) showed high topic drift from initial task",
                    "drift_count": high_drift_count,
                })
                # Add affected turn numbers
                for agent_turn in agent_turns:
                    if not (is_code_task and self._is_code_response(agent_turn.content)):
                        drift_score, _ = self._compute_topic_drift(initial_task, agent_turn.content)
                        if drift_score > self.drift_threshold:
                            affected_turns.append(agent_turn.turn_number)

        if not derailment_issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.9,
                failure_mode=None,
                explanation="Agent maintained task focus across all turns",
                detector_name=self.name,
            )

        # Determine severity
        if any(i["type"] == "progressive_drift" for i in derailment_issues):
            severity = TurnAwareSeverity.SEVERE
        elif any(i["type"] == "task_substitution" for i in derailment_issues):
            severity = TurnAwareSeverity.MODERATE
        elif len(derailment_issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.95, 0.5 + len(derailment_issues) * 0.15)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F6",
            explanation=f"Task derailment detected: {len(derailment_issues)} issues",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": derailment_issues,
                "initial_task_terms": list(initial_terms)[:10],
                "total_turns": len(turns),
            },
            suggested_fix=(
                "Add task reminders in agent prompts. Consider using: "
                "'Stay focused on: [ORIGINAL_TASK]. Do not address unrelated topics.'"
            ),
            detector_name=self.name,
        )

    def _extract_key_terms(self, text: str) -> set:
        """Extract key terms from text, excluding stopwords."""
        words = text.lower().split()
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "and", "but", "or", "nor", "so", "yet", "not", "it",
            "this", "that", "these", "those", "i", "you", "we", "they",
            "me", "him", "her", "us", "them", "my", "your", "our", "their",
        }
        return {w for w in words if len(w) > 2 and w not in stopwords}

    def _is_benign_pattern(self, content: str) -> bool:
        """Phase 1: Check if content contains benign framework-specific patterns."""
        content_lower = content.lower()

        # Get patterns for this framework (or default)
        framework_key = self.framework if self.framework in self.BENIGN_PATTERNS else "default"
        patterns = self.BENIGN_PATTERNS.get(framework_key, [])
        patterns.extend(self.BENIGN_PATTERNS["default"])  # Always include default patterns

        # Check if any benign pattern matches
        import re
        for pattern in patterns:
            if re.search(pattern, content_lower):
                return True
        return False

    def _is_code_task(self, task: str) -> bool:
        """Check if the task is asking for code."""
        code_keywords = [
            "write", "code", "function", "implement", "create",
            "program", "script", "fix", "debug", "add", "python",
            "javascript", "java", "def", "class", "method",
            "build", "develop", "generate", "make",
        ]
        task_lower = task.lower()
        return any(kw in task_lower for kw in code_keywords)

    def _is_code_response(self, content: str) -> bool:
        """Check if response contains code."""
        content_lower = content.lower()
        code_pattern_count = sum(1 for p in self.CODE_PATTERNS if p.lower() in content_lower)
        return code_pattern_count >= 2

    def _compute_topic_drift(
        self,
        task: str,
        output: str,
        use_embeddings: bool = True,
    ) -> tuple:
        """Compute topic drift and task coverage.

        Enhanced with embedding-based semantic similarity (v2.0).
        Falls back to keyword-based when embeddings unavailable.

        Returns:
            (drift_score, coverage) tuple where drift_score in [0,1]
            Higher drift_score = more drift from task
        """
        # Try embedding-based similarity first (more accurate)
        if use_embeddings:
            similarity = self.semantic_similarity(task, output)
            if similarity >= 0:  # Embeddings available
                # Convert similarity to drift score (inverted)
                drift_score = 1.0 - similarity
                coverage = similarity  # Similarity approximates coverage
                return drift_score, coverage

        # Fallback to keyword-based
        task_terms = self._extract_key_terms(task)
        output_terms = self._extract_key_terms(output)

        if not task_terms:
            return 0.0, 1.0

        overlap = task_terms & output_terms
        coverage = len(overlap) / len(task_terms)

        # New terms not in task
        new_terms = output_terms - task_terms
        novelty_ratio = len(new_terms) / max(len(output_terms), 1)

        drift_score = (1 - coverage) * 0.6 + novelty_ratio * 0.4
        return min(drift_score, 1.0), coverage

    def _detect_progressive_drift(
        self,
        initial_task: str,
        agent_turns: List[TurnSnapshot],
        is_code_task: bool = False,
    ) -> Dict[str, Any]:
        """Detect if agent responses are progressively drifting.

        Enhanced with batch embedding analysis (v2.0).
        Phase 1: Skip benign patterns.
        """
        # Filter turns for analysis
        turns_to_analyze = []
        for turn in agent_turns:
            if is_code_task and self._is_code_response(turn.content):
                continue
            # Phase 1: Skip benign patterns
            if self._is_benign_pattern(turn.content):
                continue
            turns_to_analyze.append(turn)

        if len(turns_to_analyze) < 3:
            return {"detected": False}

        # Try batch embedding analysis first (more efficient)
        responses = [t.content for t in turns_to_analyze]
        semantic_result = self.detect_semantic_drift(initial_task, responses)

        if semantic_result.get("available"):
            # Use embedding-based progressive drift detection
            if semantic_result.get("progressive_drift"):
                similarities = semantic_result["similarities"]
                # Find worst turn (lowest similarity)
                min_idx = similarities.index(min(similarities))
                worst_turn = turns_to_analyze[min_idx].turn_number

                drift_scores = [
                    {"turn": t.turn_number, "drift": 1.0 - sim, "similarity": sim}
                    for t, sim in zip(turns_to_analyze, similarities)
                ]

                return {
                    "detected": True,
                    "worst_turn": worst_turn,
                    "drift_scores": drift_scores,
                    "avg_similarity": semantic_result["avg_similarity"],
                    "method": "embedding",
                }

            return {"detected": False, "method": "embedding"}

        # Fallback to keyword-based progressive drift
        drift_scores = []
        for turn in turns_to_analyze:
            drift, _ = self._compute_topic_drift(initial_task, turn.content, use_embeddings=False)
            drift_scores.append({
                "turn": turn.turn_number,
                "drift": drift,
            })

        # Check if drift is increasing
        scores = [d["drift"] for d in drift_scores]
        mid = len(scores) // 2
        first_half_avg = sum(scores[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(scores[mid:]) / (len(scores) - mid) if len(scores) > mid else 0

        # Raised threshold from 0.2 to 0.3 to reduce false positives
        if second_half_avg > first_half_avg + 0.3:  # Significant increase
            worst_turn = max(drift_scores, key=lambda x: x["drift"])["turn"]
            return {
                "detected": True,
                "worst_turn": worst_turn,
                "drift_scores": drift_scores,
                "first_half_avg": first_half_avg,
                "second_half_avg": second_half_avg,
                "method": "keyword",
            }

        return {"detected": False, "method": "keyword"}

    def _detect_progressive_drift_from_similarities(
        self,
        turns: List[TurnSnapshot],
        similarities: List[float],
    ) -> Dict[str, Any]:
        """Detect progressive drift using pre-computed similarities.

        OPTIMIZATION: This avoids re-encoding texts that were already encoded
        in the main detect() method's batch_semantic_similarity call.
        """
        if len(similarities) < 3 or len(turns) != len(similarities):
            return {"detected": False}

        # Build drift scores from pre-computed similarities
        drift_scores = [
            {"turn": t.turn_number, "drift": 1.0 - sim, "similarity": sim}
            for t, sim in zip(turns, similarities)
        ]

        # Check for progressive drift (similarity decreasing over time)
        mid = len(similarities) // 2
        first_half = similarities[:mid]
        second_half = similarities[mid:]
        first_avg = sum(first_half) / len(first_half) if first_half else 0
        second_avg = sum(second_half) / len(second_half) if second_half else 0

        # 10% degradation threshold for progressive drift
        if second_avg < first_avg - 0.1:
            min_idx = similarities.index(min(similarities))
            worst_turn = turns[min_idx].turn_number

            return {
                "detected": True,
                "worst_turn": worst_turn,
                "drift_scores": drift_scores,
                "avg_similarity": sum(similarities) / len(similarities),
                "method": "embedding_precomputed",
            }

        return {"detected": False, "method": "embedding_precomputed"}

    def _detect_task_substitution(
        self,
        initial_task: str,
        agent_turns: List[TurnSnapshot],
    ) -> Dict[str, Any]:
        """Detect if agent is doing a different but related task."""
        # Common substitution pairs
        substitution_pairs = [
            ("authentication", "authorization"),
            ("encrypt", "decrypt"),
            ("upload", "download"),
            ("create", "delete"),
            ("read", "write"),
            ("frontend", "backend"),
        ]

        task_lower = initial_task.lower()

        for correct, wrong in substitution_pairs:
            if correct in task_lower:
                # Check if any agent turn focuses on wrong task
                for turn in agent_turns:
                    output_lower = turn.content.lower()
                    correct_count = output_lower.count(correct)
                    wrong_count = output_lower.count(wrong)

                    if wrong_count > correct_count + 2:
                        return {
                            "detected": True,
                            "turn": turn.turn_number,
                            "description": f"Agent focused on '{wrong}' instead of '{correct}'",
                        }

        return {"detected": False}


class TurnAwareLoopDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F5: Infinite Loop / Repetitive Behavior across conversation turns.

    Analyzes conversation for:
    1. Repetitive agent responses (exact + semantic)
    2. Cyclic conversation patterns
    3. Coordination loops (A→B→A→B in multi-agent)
    4. Stuck loops where same content repeats

    Phase 2 Enhancement: Uses semantic similarity to detect loops where content
    is paraphrased but semantically identical (e.g., "let me try again" vs "I'll attempt once more").
    """

    name = "TurnAwareLoopDetector"
    version = "2.0"  # Phase 2: Enhanced with semantic loop detection
    supported_failure_modes = ["F5"]

    def __init__(
        self,
        repetition_threshold: float = 0.9,
        min_repetitions: int = 3,  # Raised from 2 to reduce FPs (18.3% FPR)
    ):
        self.repetition_threshold = repetition_threshold
        self.min_repetitions = min_repetitions

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect loops and repetitive behavior in conversation."""
        if len(turns) < 4:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to detect loops",
                detector_name=self.name,
            )

        agent_turns = [t for t in turns if t.participant_type == "agent"]

        if len(agent_turns) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few agent turns to detect loops",
                detector_name=self.name,
            )

        loop_issues = []
        affected_turns = []

        # Check for exact duplicate responses (by hash)
        hash_counts = {}
        for turn in agent_turns:
            h = turn.content_hash
            if h not in hash_counts:
                hash_counts[h] = []
            hash_counts[h].append(turn.turn_number)

        for h, turn_numbers in hash_counts.items():
            if len(turn_numbers) >= self.min_repetitions:
                loop_issues.append({
                    "type": "exact_repetition",
                    "turns": turn_numbers,
                    "repetition_count": len(turn_numbers),
                    "description": f"Exact same response repeated {len(turn_numbers)} times",
                })
                affected_turns.extend(turn_numbers)

        # Check for cyclic patterns (A -> B -> A -> B)
        cyclic_pattern = self._detect_cyclic_pattern(agent_turns)
        if cyclic_pattern["detected"]:
            loop_issues.append({
                "type": "cyclic_pattern",
                "cycle_length": cyclic_pattern["cycle_length"],
                "turns": cyclic_pattern["turns"],
                "description": f"Cyclic pattern detected with length {cyclic_pattern['cycle_length']}",
            })
            affected_turns.extend(cyclic_pattern["turns"])

        # Phase 2: Check for coordination loops (A→B→A→B in multi-agent)
        coord_loop = self._detect_coordination_loop(agent_turns)
        if coord_loop["detected"]:
            loop_issues.append({
                "type": "coordination_loop",
                "agent_sequence": coord_loop["sequence"],
                "turns": coord_loop["turns"],
                "description": f"Coordination loop: agents alternating without progress",
            })
            affected_turns.extend(coord_loop["turns"])

        # Phase 2: Check for semantic loops (paraphrased repetition)
        semantic_loop = self._detect_semantic_loop(agent_turns)
        if semantic_loop["detected"]:
            loop_issues.append({
                "type": "semantic_loop",
                "turns": semantic_loop["turns"],
                "description": f"Semantic loop: {semantic_loop['count']} semantically similar responses",
            })
            affected_turns.extend(semantic_loop["turns"])

        if not loop_issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.9,
                failure_mode=None,
                explanation="No repetitive patterns detected",
                detector_name=self.name,
            )

        # Determine severity
        max_repetitions = max(
            (i.get("repetition_count", 0) for i in loop_issues),
            default=0
        )
        if max_repetitions >= 4 or any(i["type"] == "cyclic_pattern" for i in loop_issues):
            severity = TurnAwareSeverity.SEVERE
        elif max_repetitions >= 3:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.95, 0.6 + max_repetitions * 0.1)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F5",
            explanation=f"Loop/repetition detected: {len(loop_issues)} patterns found",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": loop_issues,
                "total_agent_turns": len(agent_turns),
            },
            suggested_fix=(
                "Implement loop breaking logic. Add variation detection to prevent "
                "repeated identical responses. Consider maximum retry limits."
            ),
            detector_name=self.name,
        )

    def _detect_cyclic_pattern(
        self,
        agent_turns: List[TurnSnapshot],
    ) -> Dict[str, Any]:
        """Detect cyclic patterns in agent responses."""
        if len(agent_turns) < 4:
            return {"detected": False}

        hashes = [t.content_hash for t in agent_turns]

        # Check for cycle lengths 2 and 3
        for cycle_len in [2, 3]:
            if len(hashes) >= cycle_len * 2:
                for start in range(len(hashes) - cycle_len * 2 + 1):
                    pattern = hashes[start:start + cycle_len]
                    next_seq = hashes[start + cycle_len:start + cycle_len * 2]
                    if pattern == next_seq:
                        affected_turns = [
                            agent_turns[i].turn_number
                            for i in range(start, min(start + cycle_len * 2, len(agent_turns)))
                        ]
                        return {
                            "detected": True,
                            "cycle_length": cycle_len,
                            "turns": affected_turns,
                        }

        return {"detected": False}

    def _detect_coordination_loop(
        self,
        agent_turns: List[TurnSnapshot],
    ) -> Dict[str, Any]:
        """Detect coordination loops (A→B→A→B pattern) in multi-agent systems.

        Phase 2: Identifies when two or more agents alternate without making progress.
        Common in multi-agent coordination failures.

        Args:
            agent_turns: List of agent turns

        Returns:
            Dict with detection result, agent sequence, and affected turns
        """
        if len(agent_turns) < 4:
            return {"detected": False}

        # Get agent ID sequence
        agent_sequence = [t.participant_id for t in agent_turns]

        # Check for A→B→A→B pattern (2-agent loop)
        for i in range(len(agent_sequence) - 3):
            if (agent_sequence[i] == agent_sequence[i + 2] and
                agent_sequence[i + 1] == agent_sequence[i + 3] and
                agent_sequence[i] != agent_sequence[i + 1]):
                # Found A→B→A→B loop
                return {
                    "detected": True,
                    "sequence": agent_sequence[i:i + 4],
                    "turns": [agent_turns[i + j].turn_number for j in range(4)],
                }

        # Check for A→B→C→A→B→C pattern (3-agent loop)
        for i in range(len(agent_sequence) - 5):
            if (agent_sequence[i] == agent_sequence[i + 3] and
                agent_sequence[i + 1] == agent_sequence[i + 4] and
                agent_sequence[i + 2] == agent_sequence[i + 5] and
                len(set(agent_sequence[i:i + 3])) == 3):
                # Found A→B→C→A→B→C loop
                return {
                    "detected": True,
                    "sequence": agent_sequence[i:i + 6],
                    "turns": [agent_turns[i + j].turn_number for j in range(6)],
                }

        return {"detected": False}

    def _detect_semantic_loop(
        self,
        agent_turns: List[TurnSnapshot],
        similarity_threshold: float = 0.92,
    ) -> Dict[str, Any]:
        """Detect semantic loops using embeddings.

        Phase 2: Identifies when agents repeat semantically similar content even if
        worded differently (e.g., "let me try again" vs "I'll attempt once more").

        Args:
            agent_turns: List of agent turns
            similarity_threshold: Minimum similarity to consider a semantic loop (0.92)

        Returns:
            Dict with detection result, turn numbers, and count
        """
        if not self.embedder or len(agent_turns) < 3:
            return {"detected": False}

        try:
            # Get content from all agent turns (limited to 200 chars for embedding)
            contents = [t.content[:200] for t in agent_turns]

            # Find semantically similar consecutive turns
            similar_pairs = []
            for i in range(len(contents) - 1):
                similarity = self.semantic_similarity(contents[i], contents[i + 1])
                if similarity >= similarity_threshold:
                    similar_pairs.append((i, i + 1, similarity))

            # Check if we have at least 2 consecutive similar pairs (3+ turns)
            if len(similar_pairs) >= 2:
                affected_turn_indices = set()
                for i, j, _ in similar_pairs:
                    affected_turn_indices.add(i)
                    affected_turn_indices.add(j)

                affected_turn_numbers = [agent_turns[i].turn_number for i in sorted(affected_turn_indices)]

                return {
                    "detected": True,
                    "turns": affected_turn_numbers,
                    "count": len(affected_turn_indices),
                }

        except Exception as e:
            logger.debug(f"Semantic loop detection failed: {e}")

        return {"detected": False}


class TurnAwareSpecificationMismatchDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F1: Specification Mismatch in conversations.

    Analyzes whether agent outputs match the user's requirements:
    1. Missing required features - user asked for X but agent didn't provide
    2. Extra unrequested features - agent added things user didn't ask for
    3. Misinterpreted requirements - agent did something different than asked
    4. Incomplete implementation - partial fulfillment of requirements

    Phase 2 Enhancement: Uses semantic similarity (EmbeddingMixin) for requirement
    matching instead of simple keyword matching. This improves detection accuracy
    by understanding semantic equivalence (e.g., "authentication" matches "login system").

    This is the 3rd most common failure mode in MAST (30% prevalence).
    """

    name = "TurnAwareSpecificationMismatchDetector"
    version = "2.0"  # Phase 2: Enhanced with semantic matching
    supported_failure_modes = ["F1"]

    # Requirement indicators in user messages
    REQUIREMENT_KEYWORDS = [
        "must", "should", "need", "require", "want", "please",
        "make sure", "ensure", "implement", "create", "build",
        "add", "include", "support", "feature", "functionality",
    ]

    # Mismatch indicators - signs of spec violation
    MISMATCH_INDICATORS = [
        "instead of", "rather than", "different from", "not what",
        "missing", "forgot", "didn't include", "left out",
        "extra", "unnecessary", "not requested", "not needed",
        "incomplete", "partial", "only part", "some of",
    ]

    def __init__(
        self,
        min_requirement_terms: int = 2,
        coverage_threshold: float = 0.55,  # Raised from 0.40 to reduce FPs (41% FPR)
    ):
        self.min_requirement_terms = min_requirement_terms
        self.coverage_threshold = coverage_threshold

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect specification mismatches between requirements and outputs."""
        user_turns = [t for t in turns if t.participant_type == "user"]
        agent_turns = [t for t in turns if t.participant_type == "agent"]
        system_turns = [t for t in turns if t.participant_type == "system"]

        # Handle multi-agent systems where all participants are "agent" role
        # (e.g., ChatDev where CEO gives task to Programmer)
        # The task can come from: user turns, system prompt, or first agent
        synthetic_user_turns = []
        agents_to_check = agent_turns
        if user_turns:
            synthetic_user_turns = user_turns
        elif system_turns and any(len(t.content) > 50 for t in system_turns):
            # Multi-agent: system prompt contains the task
            synthetic_user_turns = [t for t in system_turns if len(t.content) > 50]
        elif agent_turns:
            # Multi-agent: first agent's message contains the task
            synthetic_user_turns = [agent_turns[0]]
            agents_to_check = agent_turns[1:]

        if not synthetic_user_turns or not agents_to_check:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need both user requirements and agent output",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # Extract requirements from user turns (or first agent in multi-agent)
        requirements = self._extract_requirements(synthetic_user_turns)

        if len(requirements) < self.min_requirement_terms:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.5,
                failure_mode=None,
                explanation="Could not extract clear requirements from user input",
                detector_name=self.name,
            )

        # Check agent responses against requirements
        agent_content = " ".join([t.content for t in agents_to_check])

        # 1. Check requirement coverage - only flag if below threshold
        coverage_result = self._check_coverage(requirements, agent_content)
        if coverage_result["coverage"] < self.coverage_threshold:
            issues.append({
                "type": "missing_requirements",
                "uncovered": coverage_result["uncovered"][:5],
                "coverage_ratio": coverage_result["coverage"],
                "description": f"Missing requirements: {', '.join(coverage_result['uncovered'][:3])} ({coverage_result['coverage']:.0%} coverage < {self.coverage_threshold:.0%} threshold)",
            })
            for ut in synthetic_user_turns:
                affected_turns.append(ut.turn_number)

        # 2. Check for explicit mismatch indicators
        mismatch_issues = self._check_mismatch_indicators(agents_to_check)
        issues.extend(mismatch_issues)
        for issue in mismatch_issues:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for scope creep (unrequested additions)
        scope_issues = self._check_scope_creep(synthetic_user_turns, agents_to_check)
        issues.extend(scope_issues)
        for issue in scope_issues:
            affected_turns.extend(issue.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Requirements appear to be addressed ({coverage_result['coverage']:.0%} coverage)",
                detector_name=self.name,
            )

        # Determine severity
        if any(i["type"] == "missing_requirements" and i.get("coverage_ratio", 1) < 0.5 for i in issues):
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F1",
            explanation=f"Specification mismatch: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": issues,
                "extracted_requirements": list(requirements)[:10],
            },
            suggested_fix=(
                "Review requirements more carefully. Consider: 1) Extracting explicit "
                "requirements before implementing, 2) Validating output against each "
                "requirement, 3) Asking clarifying questions for ambiguous specs."
            ),
            detector_name=self.name,
        )

    def _extract_requirements(self, user_turns: List[TurnSnapshot]) -> set:
        """Extract requirement keywords from user messages."""
        requirements = set()

        for turn in user_turns:
            content_lower = turn.content.lower()
            words = content_lower.split()

            # Extract nouns/key terms after requirement keywords
            for i, word in enumerate(words):
                if word in self.REQUIREMENT_KEYWORDS:
                    # Get next 1-3 words as potential requirement
                    for j in range(i + 1, min(i + 4, len(words))):
                        candidate = words[j].strip(",.;:!?")
                        if len(candidate) > 3 and candidate.isalpha():
                            requirements.add(candidate)

            # Also extract capitalized terms (likely proper nouns/features)
            for word in turn.content.split():
                clean = word.strip(",.;:!?()")
                if clean and clean[0].isupper() and len(clean) > 2:
                    requirements.add(clean.lower())

        return requirements

    def _chunk_output(self, agent_content: str, max_len: int = 500) -> List[str]:
        """Chunk agent output into smaller pieces for semantic matching.

        Args:
            agent_content: Full agent output text
            max_len: Maximum characters per chunk

        Returns:
            List of text chunks
        """
        # Split on paragraphs first (double newlines or sentences)
        paragraphs = [p.strip() for p in agent_content.split('\n\n') if p.strip()]

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) <= max_len:
                current_chunk += para + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks if chunks else [agent_content[:max_len]]

    def _semantic_requirement_matching(
        self,
        requirements: set,
        agent_content: str,
        similarity_threshold: float = 0.82  # Raised from 0.75 to reduce FPs
    ) -> dict:
        """Use embeddings to check if requirements are semantically met.

        Phase 2 Enhancement: Semantic matching understands synonyms and paraphrasing.
        For example, "authentication system" matches "login functionality".

        Args:
            requirements: Set of requirement keywords/phrases
            agent_content: Agent output text to check
            similarity_threshold: Minimum similarity score to consider a match (0.82, raised from 0.75)

        Returns:
            Dict with covered/uncovered requirements and coverage ratio
        """
        if not self.embedder or not requirements:
            # Fallback to keyword matching if embeddings unavailable
            return self._keyword_requirement_matching(requirements, agent_content)

        try:
            # Chunk agent output for better semantic matching
            output_chunks = self._chunk_output(agent_content, max_len=500)

            # OPTIMIZATION: Pre-encode all passages ONCE instead of per-requirement
            # This reduces O(n*m) to O(n+m) embedding calls
            passage_embs = self.embedder.encode_passages(output_chunks) if output_chunks else None
            if passage_embs is None or len(passage_embs) == 0:
                return self._keyword_requirement_matching(requirements, agent_content)

            covered = set()
            uncovered = set()

            # For each requirement, compute similarity with pre-encoded passages
            for req in requirements:
                try:
                    query_emb = self.embedder.encode_query(req)
                    similarities = self.embedder.batch_similarity(query_emb, passage_embs)

                    if similarities is not None and len(similarities) > 0:
                        best_match = float(max(similarities))
                        if best_match >= similarity_threshold:
                            covered.add(req)
                        else:
                            uncovered.add(req)
                    else:
                        # Fallback to keyword
                        if req in agent_content.lower():
                            covered.add(req)
                        else:
                            uncovered.add(req)
                except Exception:
                    # Fallback to keyword for this requirement
                    if req in agent_content.lower():
                        covered.add(req)
                    else:
                        uncovered.add(req)

            coverage = len(covered) / len(requirements) if requirements else 1.0

            return {
                "covered": list(covered),
                "uncovered": list(uncovered),
                "coverage": coverage,
                "method": "semantic",
            }

        except Exception as e:
            logger.debug(f"Semantic requirement matching failed: {e}, falling back to keyword")
            return self._keyword_requirement_matching(requirements, agent_content)

    def _keyword_requirement_matching(self, requirements: set, agent_content: str) -> dict:
        """Keyword-based requirement matching (fallback for when embeddings unavailable).

        Args:
            requirements: Set of requirement keywords
            agent_content: Agent output text

        Returns:
            Dict with covered/uncovered requirements and coverage ratio
        """
        agent_lower = agent_content.lower()
        covered = set()
        uncovered = set()

        for req in requirements:
            if req in agent_lower:
                covered.add(req)
            else:
                uncovered.add(req)

        coverage = len(covered) / len(requirements) if requirements else 1.0

        return {
            "covered": list(covered),
            "uncovered": list(uncovered),
            "coverage": coverage,
            "method": "keyword",
        }

    def _check_coverage(self, requirements: set, agent_content: str) -> dict:
        """Check how many requirements are addressed in agent output.

        Phase 2: Prefers semantic matching, falls back to keyword matching.
        """
        return self._semantic_requirement_matching(requirements, agent_content)

    def _check_mismatch_indicators(self, agent_turns: List[TurnSnapshot]) -> list:
        """Check for explicit mismatch indicators in agent output."""
        issues = []

        for turn in agent_turns:
            content_lower = turn.content.lower()
            for indicator in self.MISMATCH_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "explicit_mismatch",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Mismatch indicator found: '{indicator}'",
                    })
                    break  # One per turn

        return issues[:3]

    def _check_scope_creep(
        self, user_turns: List[TurnSnapshot], agent_turns: List[TurnSnapshot]
    ) -> list:
        """Check for scope creep - agent adding unrequested features."""
        issues = []

        # Look for phrases indicating unrequested additions
        scope_indicators = [
            "i also added", "i've included extra", "bonus feature",
            "additionally", "as a bonus", "extra functionality",
            "i went ahead and", "while i was at it",
        ]

        for turn in agent_turns:
            content_lower = turn.content.lower()
            for indicator in scope_indicators:
                if indicator in content_lower:
                    issues.append({
                        "type": "scope_creep",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Potential scope creep: '{indicator}'",
                    })
                    break

        return issues[:2]


class TurnAwareCoordinationFailureDetector(TurnAwareDetector):
    """Detects F11: Coordination Failure across conversation turns.

    Analyzes multi-agent conversations for:
    1. Conflicting actions - agents doing contradictory things
    2. Redundant work - multiple agents doing the same task
    3. Missed handoffs - expected agent input that never comes
    4. Role confusion - agents taking on wrong responsibilities
    5. Inconsistent state - agents having different views of progress

    This is the most common failure mode in MAST (40% prevalence).
    """

    name = "TurnAwareCoordinationFailureDetector"
    version = "1.0"
    supported_failure_modes = ["F11"]

    # Conflict indicators - stronger signals of inter-agent disagreement
    # Tuned to reduce FP from common words like "however", "error"
    CONFLICT_INDICATORS = [
        "i disagree", "that's wrong", "you made a mistake",
        "let me correct", "that's not correct", "should not have",
        "you shouldn't", "incorrect approach", "wrong approach",
        "redo this", "start over", "conflicting with", "contradicts",
        "not what i asked", "misunderstood", "that's incorrect",
    ]

    # Redundancy indicators - signs of duplicate work
    REDUNDANCY_INDICATORS = [
        "already done", "already completed", "duplicate", "same as",
        "just did that", "already implemented", "implemented earlier",
        "was done by", "redundant", "again?", "repeated",
    ]

    # Handoff phrases - expecting input from others
    HANDOFF_PHRASES = [
        "waiting for", "need input from", "once you", "after you",
        "please provide", "send me", "pass to", "hand off",
        "your turn", "over to you", "expecting", "depends on",
    ]

    def __init__(
        self,
        min_agents: int = 2,
        conflict_threshold: float = 0.1,
        redundancy_threshold: float = 0.6,  # Raised from 0.3 - avoid FPs on similar discussions
        min_issues_to_flag: int = 2,  # Balanced: was 5 (too strict), now 2
    ):
        self.min_agents = min_agents
        self.conflict_threshold = conflict_threshold
        self.redundancy_threshold = redundancy_threshold
        self.min_issues_to_flag = min_issues_to_flag

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect coordination failures in multi-agent conversation."""
        # Extract unique agents
        agents = set()
        for turn in turns:
            if turn.participant_type == "agent":
                agents.add(turn.participant_id)

        # Need multiple agents for coordination failure
        if len(agents) < self.min_agents:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Single agent conversation - no coordination needed",
                detector_name=self.name,
            )

        agent_turns = [t for t in turns if t.participant_type == "agent"]
        if len(agent_turns) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few agent turns to detect coordination issues",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for conflicting statements
        conflict_issues = self._detect_conflicts(agent_turns)
        issues.extend(conflict_issues)
        for issue in conflict_issues:
            affected_turns.extend(issue.get("turns", []))

        # 2. Check for redundant work
        redundancy_issues = self._detect_redundancy(agent_turns)
        issues.extend(redundancy_issues)
        for issue in redundancy_issues:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for missed handoffs
        handoff_issues = self._detect_missed_handoffs(agent_turns, agents)
        issues.extend(handoff_issues)
        for issue in handoff_issues:
            affected_turns.extend(issue.get("turns", []))

        # 4. Check for role confusion (agent doing work outside its role)
        role_issues = self._detect_role_confusion(agent_turns, agents)
        issues.extend(role_issues)
        for issue in role_issues:
            affected_turns.extend(issue.get("turns", []))

        # Require multiple issues to flag coordination failure (avoid FPs)
        if len(issues) < self.min_issues_to_flag:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation=f"Insufficient evidence ({len(issues)} issue(s), need {self.min_issues_to_flag}+)",
                detector_name=self.name,
            )

        # Determine severity based on number and type of issues
        if len(issues) >= 4 or any(i["type"] == "conflict" for i in issues):
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 3:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.9, 0.5 + len(issues) * 0.15)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F11",
            explanation=f"Coordination failure detected: {len(issues)} issues found across {len(agents)} agents",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": issues,
                "num_agents": len(agents),
                "agents": list(agents),
            },
            suggested_fix=(
                "Improve agent coordination by: 1) Adding explicit handoff protocols, "
                "2) Implementing shared state management, 3) Adding coordination checkpoints, "
                "4) Defining clear role boundaries."
            ),
            detector_name=self.name,
        )

    def _detect_conflicts(self, agent_turns: List[TurnSnapshot]) -> List[Dict]:
        """Detect conflicting statements between agents."""
        issues = []
        for i, turn in enumerate(agent_turns):
            content_lower = turn.content.lower()
            for indicator in self.CONFLICT_INDICATORS:
                if indicator in content_lower:
                    # Check if this conflicts with a previous turn from different agent
                    for j in range(max(0, i - 3), i):
                        prev_turn = agent_turns[j]
                        if prev_turn.participant_id != turn.participant_id:
                            issues.append({
                                "type": "conflict",
                                "turns": [prev_turn.turn_number, turn.turn_number],
                                "indicator": indicator,
                                "agents": [prev_turn.participant_id, turn.participant_id],
                                "description": f"Potential conflict: agent uses '{indicator}'",
                            })
                            break
                    break  # Only one issue per turn
        return issues[:3]  # Limit to first 3

    def _detect_redundancy(self, agent_turns: List[TurnSnapshot]) -> List[Dict]:
        """Detect redundant work between agents."""
        issues = []

        # Check for explicit redundancy indicators
        for turn in agent_turns:
            content_lower = turn.content.lower()
            for indicator in self.REDUNDANCY_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "redundancy",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Redundancy indicator: '{indicator}'",
                    })
                    break

        # Check for similar content from different agents
        for i, turn1 in enumerate(agent_turns):
            for j, turn2 in enumerate(agent_turns[i + 1:], i + 1):
                if turn1.participant_id != turn2.participant_id:
                    similarity = self._content_similarity(turn1.content, turn2.content)
                    if similarity > self.redundancy_threshold:
                        issues.append({
                            "type": "redundant_work",
                            "turns": [turn1.turn_number, turn2.turn_number],
                            "similarity": similarity,
                            "agents": [turn1.participant_id, turn2.participant_id],
                            "description": f"Similar work by different agents ({similarity:.0%} overlap)",
                        })
                        if len(issues) >= 3:
                            return issues

        return issues[:3]

    def _detect_missed_handoffs(
        self, agent_turns: List[TurnSnapshot], agents: set
    ) -> List[Dict]:
        """Detect missed handoffs where expected input never comes."""
        issues = []

        for i, turn in enumerate(agent_turns):
            content_lower = turn.content.lower()
            for phrase in self.HANDOFF_PHRASES:
                if phrase in content_lower:
                    # Check if subsequent turns address the handoff
                    handoff_addressed = False
                    for j in range(i + 1, min(i + 5, len(agent_turns))):
                        next_turn = agent_turns[j]
                        if next_turn.participant_id != turn.participant_id:
                            handoff_addressed = True
                            break

                    if not handoff_addressed:
                        issues.append({
                            "type": "missed_handoff",
                            "turns": [turn.turn_number],
                            "phrase": phrase,
                            "description": f"Handoff expected ('{phrase}') but not addressed",
                        })
                        break

        return issues[:2]

    def _detect_role_confusion(
        self, agent_turns: List[TurnSnapshot], agents: set
    ) -> List[Dict]:
        """Detect role confusion where agents step outside their roles."""
        # Extract role names from agent IDs
        role_keywords = {}
        for agent in agents:
            # Parse role from IDs like "chatdev:CEO" or "metagpt:Architect"
            if ":" in agent:
                role = agent.split(":")[-1].lower()
                role_keywords[agent] = role

        if len(role_keywords) < 2:
            return []

        issues = []

        # Check for role-inconsistent actions
        for turn in agent_turns:
            agent_role = role_keywords.get(turn.participant_id, "")
            content_lower = turn.content.lower()

            # CEO/Manager shouldn't write code
            if agent_role in ["ceo", "manager", "productmanager", "pm"]:
                if "def " in content_lower or "class " in content_lower or "```python" in content_lower:
                    issues.append({
                        "type": "role_confusion",
                        "turns": [turn.turn_number],
                        "agent": turn.participant_id,
                        "expected_role": agent_role,
                        "description": f"Manager/CEO agent writing code (role confusion)",
                    })

            # Coder/Programmer shouldn't be making product decisions
            if agent_role in ["programmer", "coder", "developer", "engineer"]:
                if any(phrase in content_lower for phrase in [
                    "product decision", "user story", "requirement is",
                    "we should pivot", "market analysis"
                ]):
                    issues.append({
                        "type": "role_confusion",
                        "turns": [turn.turn_number],
                        "agent": turn.participant_id,
                        "expected_role": agent_role,
                        "description": f"Developer making product decisions (role confusion)",
                    })

        return issues[:2]

    def _content_similarity(self, content1: str, content2: str) -> float:
        """Calculate simple word overlap similarity."""
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        return len(intersection) / len(union) if union else 0.0


class TurnAwareResourceMisallocationDetector(TurnAwareDetector):
    """Detects F3: Resource Misallocation in multi-agent conversations.

    Analyzes whether agents have appropriate resources:
    1. Missing tools/capabilities - agent needs something they don't have
    2. Wrong agent for task - task assigned to agent without required skills
    3. Resource overload - one agent given too much work
    4. Underutilized agents - some agents doing nothing while others overloaded
    5. Tool/API failures - resources not working as expected

    This is the 2nd most common failure mode in MAST (36% prevalence).
    """

    name = "TurnAwareResourceMisallocationDetector"
    version = "1.0"
    supported_failure_modes = ["F3"]

    # Resource complaint indicators - made more specific to reduce FPs
    RESOURCE_COMPLAINTS = [
        "don't have access to", "no access to the", "cannot access the",
        "missing required", "resource not available", "resource unavailable",
        "need permission to", "not authorized to", "access denied for",
        "tool not found:", "api error:", "api failure",
        "resource missing", "not installed on", "import error:",
    ]

    # Capability mismatch indicators - made more specific
    CAPABILITY_MISMATCH = [
        "not my area of expertise", "outside my designated scope",
        "i am not qualified to", "i don't know how to",
        "beyond my capabilities as", "not designed for this",
        "should be handled by another agent", "need a specialist for",
    ]

    # Overload indicators - made more specific
    OVERLOAD_INDICATORS = [
        "too many tasks assigned", "system is overloaded",
        "can't handle all these", "workload is too high",
        "queue is full", "rate limit exceeded", "being throttled",
        "operation timed out", "request timed out",
    ]

    def __init__(
        self,
        min_turns: int = 2,
        min_issues_to_flag: int = 2,  # Lowered for better recall (was 3)
    ):
        self.min_turns = min_turns
        self.min_issues_to_flag = min_issues_to_flag

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect resource misallocation issues."""
        agent_turns = [t for t in turns if t.participant_type == "agent"]
        tool_turns = [t for t in turns if t.participant_type == "tool"]

        if len(agent_turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few agent turns to analyze",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for resource complaints
        resource_issues = self._detect_resource_complaints(agent_turns + tool_turns)
        issues.extend(resource_issues)
        for issue in resource_issues:
            affected_turns.extend(issue.get("turns", []))

        # 2. Check for capability mismatches
        capability_issues = self._detect_capability_mismatch(agent_turns)
        issues.extend(capability_issues)
        for issue in capability_issues:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for overload indicators
        overload_issues = self._detect_overload(agent_turns)
        issues.extend(overload_issues)
        for issue in overload_issues:
            affected_turns.extend(issue.get("turns", []))

        # 4. Check for tool/API failures in tool responses
        tool_issues = self._detect_tool_failures(tool_turns)
        issues.extend(tool_issues)
        for issue in tool_issues:
            affected_turns.extend(issue.get("turns", []))

        # 5. Check for uneven work distribution (multi-agent)
        distribution_issues = self._detect_uneven_distribution(agent_turns)
        issues.extend(distribution_issues)

        # Require multiple issues to reduce false positives
        if len(issues) < self.min_issues_to_flag:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Insufficient evidence ({len(issues)} issue(s), need {self.min_issues_to_flag}+)",
                detector_name=self.name,
            )

        # Severity based on issue count and types
        if len(issues) >= 4 or any(i["type"] == "tool_failure" for i in issues):
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 3:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F3",
            explanation=f"Resource misallocation: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Review resource allocation: 1) Ensure agents have required tools/access, "
                "2) Match agent capabilities to task requirements, "
                "3) Balance workload across agents, 4) Add fallback resources."
            ),
            detector_name=self.name,
        )

    def _detect_resource_complaints(self, turns: List[TurnSnapshot]) -> list:
        """Detect complaints about missing resources."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.RESOURCE_COMPLAINTS:
                if indicator in content_lower:
                    issues.append({
                        "type": "resource_complaint",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Resource issue: '{indicator}'",
                    })
                    break
        return issues[:4]

    def _detect_capability_mismatch(self, agent_turns: List[TurnSnapshot]) -> list:
        """Detect agents saying they can't do something."""
        issues = []
        for turn in agent_turns:
            content_lower = turn.content.lower()
            for indicator in self.CAPABILITY_MISMATCH:
                if indicator in content_lower:
                    issues.append({
                        "type": "capability_mismatch",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Capability mismatch: '{indicator}'",
                    })
                    break
        return issues[:3]

    def _detect_overload(self, agent_turns: List[TurnSnapshot]) -> list:
        """Detect overload complaints."""
        issues = []
        for turn in agent_turns:
            content_lower = turn.content.lower()
            for indicator in self.OVERLOAD_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "overload",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Overload indicator: '{indicator}'",
                    })
                    break
        return issues[:2]

    def _detect_tool_failures(self, tool_turns: List[TurnSnapshot]) -> list:
        """Detect tool/API failures in tool responses."""
        issues = []
        # Made patterns more specific to reduce FPs - require error context
        failure_indicators = [
            "error:", "error occurred", "error returned",
            "failed to", "operation failed", "request failed",
            "exception:", "traceback:", "stack trace",
            "http 404", "http 500", "status 401", "status 403",
            "connection refused", "connection failed", "timed out",
        ]
        for turn in tool_turns:
            content_lower = turn.content.lower()
            for indicator in failure_indicators:
                if indicator in content_lower:
                    issues.append({
                        "type": "tool_failure",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Tool failure: '{indicator}'",
                    })
                    break
        return issues[:3]

    def _detect_uneven_distribution(self, agent_turns: List[TurnSnapshot]) -> list:
        """Detect uneven work distribution across agents."""
        from collections import Counter
        agent_counts = Counter(t.participant_id for t in agent_turns)

        if len(agent_counts) < 2:
            return []

        counts = list(agent_counts.values())
        max_count = max(counts)
        min_count = min(counts)

        # Only flag severe imbalance: 5x+ more turns and at least 8 turns for most active
        # This is a high bar to reduce FPs - true misallocation is extreme
        if max_count >= 5 * min_count and max_count >= 8:
            most_active = max(agent_counts, key=agent_counts.get)
            least_active = min(agent_counts, key=agent_counts.get)
            return [{
                "type": "uneven_distribution",
                "most_active": most_active,
                "least_active": least_active,
                "ratio": max_count / min_count if min_count > 0 else max_count,
                "description": f"Uneven workload: {most_active} has {max_count} turns vs {min_count} for {least_active}",
            }]
        return []


class TurnAwareConversationHistoryDetector(TurnAwareDetector):
    """Detects F4: Loss of Conversation History in multi-agent conversations.

    Per MAST (FM-1.4): Unexpected context truncation, disregarding recent
    interaction history and reverting to an antecedent conversational state.

    Detects:
    1. Repeated questions - asking questions already answered earlier
    2. Lost decisions - contradicting or ignoring previous agreements
    3. Context reset - treating conversation as if starting fresh
    4. Forgotten constraints - ignoring previously stated requirements
    """

    name = "TurnAwareConversationHistoryDetector"
    version = "1.0"
    supported_failure_modes = ["F4"]

    # Context loss indicators - phrases suggesting forgotten context
    CONTEXT_LOSS_INDICATORS = [
        "what programming language", "what technology should",
        "what did we decide", "remind me what",
        "what was the original", "forgot you said",
        "what framework", "which database",
        "what approach", "what method should",
        "didn't know you wanted", "wasn't aware",
    ]

    # Contradiction indicators - phrases suggesting reversal
    CONTRADICTION_INDICATORS = [
        "changed my mind", "override that",
        "actually, not that", "ignore what i said",
        "let me correct", "wait, no",
        "scratch that", "forget what i said",
        "disregard the previous", "ignore my earlier",
    ]

    # Reset indicators - phrases suggesting fresh start
    RESET_PATTERNS = [
        "let's start over", "from the beginning",
        "as if we just started", "fresh start",
        "start from scratch", "begin again",
        "reset everything", "clear the slate",
    ]

    # Question words for detecting repeated questions
    QUESTION_WORDS = ["what", "how", "when", "where", "why", "which", "who", "can", "could", "should"]

    def __init__(self, min_turns: int = 3, min_issues_to_flag: int = 2):
        self.min_turns = min_turns
        self.min_issues_to_flag = min_issues_to_flag

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect conversation history loss patterns."""
        agent_turns = [t for t in turns if t.participant_type == "agent"]

        if len(agent_turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few agent turns to analyze",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Detect context loss indicators
        context_issues = self._detect_context_loss(agent_turns)
        issues.extend(context_issues)
        for issue in context_issues:
            affected_turns.extend(issue.get("turns", []))

        # 2. Detect contradictions
        contradiction_issues = self._detect_contradictions(agent_turns)
        issues.extend(contradiction_issues)
        for issue in contradiction_issues:
            affected_turns.extend(issue.get("turns", []))

        # 3. Detect reset patterns
        reset_issues = self._detect_reset_patterns(agent_turns)
        issues.extend(reset_issues)
        for issue in reset_issues:
            affected_turns.extend(issue.get("turns", []))

        # 4. Detect repeated questions
        repeated_issues = self._detect_repeated_questions(turns)
        issues.extend(repeated_issues)
        for issue in repeated_issues:
            affected_turns.extend(issue.get("turns", []))

        if len(issues) < self.min_issues_to_flag:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Insufficient evidence ({len(issues)} issue(s), need {self.min_issues_to_flag}+)",
                detector_name=self.name,
            )

        if len(issues) >= 4:
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 3:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F4",
            explanation=f"Conversation history loss: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Improve context retention: 1) Maintain full conversation in context, "
                "2) Reference prior decisions explicitly, 3) Validate understanding before proceeding, "
                "4) Use conversation summaries for long discussions."
            ),
            detector_name=self.name,
        )

    def _detect_context_loss(self, agent_turns: List[TurnSnapshot]) -> list:
        """Detect indicators of lost context."""
        issues = []
        for i, turn in enumerate(agent_turns):
            # Only flag context loss after a few turns (not at start)
            if i < 2:
                continue

            content_lower = turn.content.lower()
            for indicator in self.CONTEXT_LOSS_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "context_loss",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Context loss indicator: '{indicator}'",
                    })
                    break
        return issues[:3]

    def _detect_contradictions(self, agent_turns: List[TurnSnapshot]) -> list:
        """Detect contradictions of earlier statements."""
        issues = []
        for turn in agent_turns:
            content_lower = turn.content.lower()
            for indicator in self.CONTRADICTION_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "contradiction",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Decision contradicted: '{indicator}'",
                    })
                    break
        return issues[:2]

    def _detect_reset_patterns(self, agent_turns: List[TurnSnapshot]) -> list:
        """Detect conversation reset patterns."""
        issues = []
        for i, turn in enumerate(agent_turns):
            # Only flag resets after conversation is established
            if i < 3:
                continue

            content_lower = turn.content.lower()
            for pattern in self.RESET_PATTERNS:
                if pattern in content_lower:
                    issues.append({
                        "type": "context_reset",
                        "turns": [turn.turn_number],
                        "pattern": pattern,
                        "description": f"Conversation reset: '{pattern}'",
                    })
                    break
        return issues[:2]

    def _detect_repeated_questions(self, turns: List[TurnSnapshot]) -> list:
        """Detect questions that were already answered earlier."""
        issues = []
        # Track question topics by extracting key phrases
        question_topics = {}

        for turn in turns:
            if "?" not in turn.content:
                continue

            content_lower = turn.content.lower()

            # Extract question topic (simplified heuristic)
            for word in self.QUESTION_WORDS:
                if word in content_lower:
                    # Use first 50 chars after question word as topic signature
                    idx = content_lower.find(word)
                    topic = content_lower[idx:idx+50]

                    if topic in question_topics:
                        # Found repeated question
                        first_turn = question_topics[topic]
                        if turn.turn_number - first_turn > 2:  # At least 2 turns apart
                            issues.append({
                                "type": "repeated_question",
                                "turns": [turn.turn_number],
                                "first_asked": first_turn,
                                "description": f"Question repeated (first asked at turn {first_turn})",
                            })
                    else:
                        question_topics[topic] = turn.turn_number
                    break

        return issues[:3]


class TurnAwareInformationWithholdingDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F8: Information Withholding in conversations.

    Analyzes whether agents properly share information:
    1. Unanswered questions - agent asks but gets no answer
    2. Missing context - agent responds without using provided info
    3. Incomplete sharing - partial information provided
    4. Ignored requests - explicit requests for info not addressed

    Enhanced with semantic analysis (v2.0):
    - Information density scoring for response completeness
    - Semantic similarity for question-answer relevance
    - Entity tracking across turns

    Based on MAST research (NeurIPS 2025): FM-2.4 Information Withholding (12%)
    """

    name = "TurnAwareInformationWithholdingDetector"
    version = "2.0"  # Semantic enhancement
    supported_failure_modes = ["F8"]

    # Question indicators
    QUESTION_PATTERNS = [
        "?", "what is", "how do", "can you", "could you",
        "please provide", "please share", "need to know",
        "tell me", "explain", "clarify", "which",
    ]

    # Withholding indicators in responses - enhanced for MAST
    WITHHOLDING_INDICATORS = [
        "can't share", "cannot disclose", "not allowed to",
        "confidential", "private", "restricted",
        "don't have that", "no information", "unknown",
        "not sure", "i don't know", "unclear",
        # Added for better MAST recall
        "didn't provide", "didn't include", "didn't mention",
        "missing", "not provided", "incomplete",
        "omitted", "left out", "didn't answer",
        "you didn't", "wasn't included", "should have",
    ]

    # Missing context indicators
    MISSING_CONTEXT = [
        "what do you mean", "more context", "be more specific",
        "unclear what", "don't understand", "confused about",
        "missing information", "need more details", "incomplete",
    ]

    def __init__(
        self,
        min_turns: int = 2,  # Lowered from 3 for better MAST recall
        min_issues_to_flag: int = 2,  # Added to reduce FPs (18.2% FPR)
    ):
        self.min_turns = min_turns
        self.min_issues_to_flag = min_issues_to_flag

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect information withholding issues."""
        if len(turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to analyze",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for unanswered questions
        unanswered = self._detect_unanswered_questions(turns)
        issues.extend(unanswered)
        for issue in unanswered:
            affected_turns.extend(issue.get("turns", []))

        # 2. Check for withholding indicators
        withholding = self._detect_withholding(turns)
        issues.extend(withholding)
        for issue in withholding:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for missing context complaints
        missing = self._detect_missing_context(turns)
        issues.extend(missing)
        for issue in missing:
            affected_turns.extend(issue.get("turns", []))

        # 4. Check for ignored information requests
        ignored = self._detect_ignored_requests(turns)
        issues.extend(ignored)
        for issue in ignored:
            affected_turns.extend(issue.get("turns", []))

        if len(issues) < self.min_issues_to_flag:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Insufficient evidence ({len(issues)} issues < {self.min_issues_to_flag} required)",
                detector_name=self.name,
            )

        if len(issues) >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F8",
            explanation=f"Information withholding: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Improve information sharing: 1) Ensure all questions are addressed, "
                "2) Share full context when responding, 3) Proactively share relevant info, "
                "4) Ask clarifying questions when info is incomplete."
            ),
            detector_name=self.name,
        )

    def _detect_unanswered_questions(self, turns: List[TurnSnapshot]) -> list:
        """Detect questions that weren't answered.

        Enhanced with semantic similarity (v2.0):
        - Uses embedding similarity to check if response addresses question
        - Also checks information density of response
        """
        issues = []
        for i, turn in enumerate(turns[:-1]):
            content = turn.content
            # Check if this turn contains a question
            if "?" in content:
                # Look at next 2 turns for an answer
                answered = False
                answer_quality = "none"

                for j in range(i + 1, min(i + 3, len(turns))):
                    next_turn = turns[j]
                    # Different participant responding
                    if next_turn.participant_id != turn.participant_id:
                        # Check semantic relevance of response to question
                        similarity = self.semantic_similarity(content, next_turn.content)

                        if similarity >= 0:  # Embeddings available
                            if similarity >= 0.5:  # Raised from 0.4 to reduce FPs
                                response_density = self.compute_information_density(next_turn.content)
                                if response_density >= 0.3:  # Substantive response
                                    answered = True
                                    answer_quality = "good"
                                else:
                                    answer_quality = "low_density"
                                break
                        else:
                            # Fallback: length-based check
                            if len(next_turn.content) > 50:
                                answered = True
                                answer_quality = "length_only"
                                break

                if not answered:
                    issues.append({
                        "type": "unanswered_question",
                        "turns": [turn.turn_number],
                        "description": "Question appears unanswered",
                        "answer_quality": answer_quality,
                    })
        return issues[:3]

    def _detect_withholding(self, turns: List[TurnSnapshot]) -> list:
        """Detect explicit withholding of information."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.WITHHOLDING_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "explicit_withholding",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Info withheld: '{indicator}'",
                    })
                    break
        return issues[:3]

    def _detect_missing_context(self, turns: List[TurnSnapshot]) -> list:
        """Detect complaints about missing context."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.MISSING_CONTEXT:
                if indicator in content_lower:
                    issues.append({
                        "type": "missing_context",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Missing context: '{indicator}'",
                    })
                    break
        return issues[:3]

    def _detect_ignored_requests(self, turns: List[TurnSnapshot]) -> list:
        """Detect explicit info requests that were ignored."""
        issues = []
        request_phrases = [
            "please provide", "please share", "send me",
            "give me", "need the", "what about",
        ]

        for i, turn in enumerate(turns[:-1]):
            content_lower = turn.content.lower()
            for phrase in request_phrases:
                if phrase in content_lower:
                    # Check if next response addresses it
                    addressed = False
                    for j in range(i + 1, min(i + 3, len(turns))):
                        next_turn = turns[j]
                        if next_turn.participant_id != turn.participant_id:
                            # Check for substantive response
                            if len(next_turn.content) > 100:
                                addressed = True
                                break
                    if not addressed:
                        issues.append({
                            "type": "ignored_request",
                            "turns": [turn.turn_number],
                            "phrase": phrase,
                            "description": f"Request ignored: '{phrase}'",
                        })
                    break
        return issues[:2]


class TurnAwareRoleUsurpationDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F9: Role Usurpation in conversations.

    Analyzes whether agents act outside their designated roles:
    1. Role boundary violation - agent performs tasks outside role scope
    2. Role ambiguity - unclear or conflicting role assignments
    3. Unauthorized actions - agent exceeds permission boundaries
    4. Role drift - gradual deviation from assigned responsibilities

    Phase 2 Enhancement (v2.0): Uses semantic similarity to:
    - Better infer agent roles from conversation context
    - Detect semantic role boundary violations (not just keyword matching)
    - Track role consistency across conversation turns
    - Identify implicit role conflicts through embedding analysis

    Based on MAST research (NeurIPS 2025): FM-2.5 Role Usurpation (3%)
    """

    name = "TurnAwareRoleUsurpationDetector"
    version = "2.0"  # Phase 2: Enhanced with semantic analysis
    supported_failure_modes = ["F9"]

    # Role definitions with semantic descriptions
    ROLE_DEFINITIONS = {
        "coordinator": {
            "description": "Orchestrates workflow, delegates tasks, manages communication between agents",
            "indicators": ["i will assign", "let me delegate", "i'll coordinate", "as coordinator",
                         "orchestrating", "managing the team", "distributing work"],
            "actions": ["assign", "delegate", "coordinate", "organize", "manage team", "distribute"],
        },
        "executor": {
            "description": "Implements solutions, executes code, performs concrete actions",
            "indicators": ["executing now", "i will implement", "implementing the", "as executor",
                         "running the code", "performing the task", "making changes"],
            "actions": ["execute", "implement", "run", "perform", "build", "create", "modify"],
        },
        "reviewer": {
            "description": "Evaluates work quality, provides feedback, validates outputs",
            "indicators": ["reviewing your", "let me review", "my review shows", "as reviewer",
                         "upon review", "checking the quality", "validating output"],
            "actions": ["review", "evaluate", "validate", "check quality", "assess", "critique"],
        },
        "researcher": {
            "description": "Gathers information, investigates problems, analyzes data",
            "indicators": ["researching this", "my research shows", "investigating the", "as researcher",
                         "analyzing the data", "gathering information", "exploring options"],
            "actions": ["research", "investigate", "analyze", "gather info", "explore", "study"],
        },
        "planner": {
            "description": "Designs strategies, creates plans, outlines approaches",
            "indicators": ["planning the approach", "let me plan", "my plan is", "as planner",
                         "designing the strategy", "outlining steps", "creating roadmap"],
            "actions": ["plan", "design", "strategize", "outline", "architect", "blueprint"],
        },
        "tester": {
            "description": "Tests functionality, verifies correctness, finds bugs",
            "indicators": ["testing this", "let me test", "my tests show", "as tester",
                         "verifying functionality", "checking for bugs", "running tests"],
            "actions": ["test", "verify", "debug", "check", "validate functionality", "qa"],
        },
    }

    def __init__(self, min_turns: int = 3, strict_mode: bool = False):
        self.min_turns = min_turns
        self.strict_mode = strict_mode  # If True, be more aggressive in detection

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect role usurpation issues."""
        if len(turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to analyze",
                detector_name=self.name,
            )

        # Track agent roles across conversation
        agent_roles = self._infer_agent_roles(turns)

        # Detect various types of role violations
        violations = []
        affected_turns = []

        # 1. Boundary violations (agent acting outside assigned role)
        boundary_violations = self._detect_boundary_violations(turns, agent_roles)
        violations.extend(boundary_violations)
        for v in boundary_violations:
            affected_turns.extend(v.get("turns", []))

        # 2. Role conflicts (multiple agents claiming same role)
        role_conflicts = self._detect_role_conflicts(turns, agent_roles)
        violations.extend(role_conflicts)
        for v in role_conflicts:
            affected_turns.extend(v.get("turns", []))

        # 3. Unauthorized actions (agent performing actions outside permission scope)
        unauthorized = self._detect_unauthorized_actions(turns, agent_roles)
        violations.extend(unauthorized)
        for v in unauthorized:
            affected_turns.extend(v.get("turns", []))

        if not violations:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation="No role usurpation detected",
                detector_name=self.name,
            )

        # Severity based on violation count and types
        critical_violations = [v for v in violations if v.get("severity") == "critical"]
        if len(critical_violations) >= 2 or len(violations) >= 5:
            severity = TurnAwareSeverity.SEVERE
        elif len(violations) >= 3:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.88, 0.45 + len(violations) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F9",
            explanation=f"Role usurpation: {len(violations)} violations found across {len(set(affected_turns))} turns",
            affected_turns=list(set(affected_turns)),
            evidence={
                "violations": violations[:5],  # Top 5 violations
                "agent_roles": agent_roles,
                "critical_violations": len(critical_violations),
            },
            suggested_fix=(
                "Enforce role boundaries: 1) Clearly define agent roles upfront, "
                "2) Add permission checks before actions, 3) Use role-based access control, "
                "4) Monitor for role drift and conflicts."
            ),
            detector_name=self.name,
        )

    def _infer_agent_roles(self, turns: List[TurnSnapshot]) -> Dict[str, Dict[str, Any]]:
        """Infer agent roles from conversation using semantic analysis.

        Phase 2 Enhancement: Uses embeddings to match agent behavior to role descriptions.
        """
        agent_roles = {}
        agent_turns = {}

        # Collect turns by agent
        for turn in turns:
            agent_id = turn.participant_id or "unknown"
            if agent_id not in agent_turns:
                agent_turns[agent_id] = []
            agent_turns[agent_id].append(turn)

        # Infer role for each agent
        for agent_id, agent_turn_list in agent_turns.items():
            # Combine first few turns for role inference
            combined_content = " ".join([t.content[:200] for t in agent_turn_list[:3]])

            # Method 1: Semantic similarity to role descriptions (if embeddings available)
            if self.embedder:
                best_role = self._semantic_role_matching(combined_content)
                if best_role:
                    agent_roles[agent_id] = best_role
                    continue

            # Method 2: Keyword-based fallback
            keyword_role = self._keyword_role_matching(agent_id, combined_content)
            if keyword_role:
                agent_roles[agent_id] = keyword_role
            else:
                # No clear role detected
                agent_roles[agent_id] = {
                    "role": "unclear",
                    "confidence": 0.2,
                    "method": "none",
                }

        return agent_roles

    def _semantic_role_matching(self, content: str) -> Optional[Dict[str, Any]]:
        """Use semantic similarity to match agent content to role descriptions.

        Phase 2: Core semantic enhancement for better role inference.
        """
        if not self.embedder:
            return None

        try:
            # Compare content to each role description
            role_similarities = {}
            for role_name, role_def in self.ROLE_DEFINITIONS.items():
                # Use role description for semantic matching
                similarity = self.semantic_similarity(content, role_def["description"])
                if similarity >= 0:  # Valid similarity score
                    role_similarities[role_name] = similarity

            if not role_similarities:
                return None

            # Get best matching role
            best_role = max(role_similarities, key=role_similarities.get)
            best_score = role_similarities[best_role]

            # Require reasonable confidence threshold
            if best_score >= 0.50:  # Semantic similarity threshold
                return {
                    "role": best_role,
                    "confidence": best_score,
                    "method": "semantic",
                    "description": self.ROLE_DEFINITIONS[best_role]["description"],
                }

        except Exception as e:
            logger.debug(f"Semantic role matching failed: {e}")

        return None

    def _keyword_role_matching(self, agent_id: str, content: str) -> Optional[Dict[str, Any]]:
        """Fallback keyword-based role matching."""
        agent_lower = agent_id.lower()
        content_lower = content.lower()

        # Check agent ID
        for role_name, role_def in self.ROLE_DEFINITIONS.items():
            if role_name in agent_lower:
                return {
                    "role": role_name,
                    "confidence": 0.75,
                    "method": "agent_id",
                    "description": role_def["description"],
                }

        # Check content indicators
        role_scores = {}
        for role_name, role_def in self.ROLE_DEFINITIONS.items():
            score = sum(1 for indicator in role_def["indicators"] if indicator in content_lower)
            if score > 0:
                role_scores[role_name] = score

        if role_scores:
            best_role = max(role_scores, key=role_scores.get)
            score = role_scores[best_role]
            return {
                "role": best_role,
                "confidence": min(0.70, 0.4 + score * 0.15),
                "method": "keyword",
                "description": self.ROLE_DEFINITIONS[best_role]["description"],
            }

        return None

    def _detect_boundary_violations(
        self,
        turns: List[TurnSnapshot],
        agent_roles: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect agents acting outside their role boundaries.

        Phase 2: Uses semantic similarity to detect boundary violations beyond keywords.
        """
        violations = []

        for turn in turns:
            agent_id = turn.participant_id or "unknown"

            # Skip if no clear role assigned
            if agent_id not in agent_roles or agent_roles[agent_id]["role"] == "unclear":
                continue

            assigned_role = agent_roles[agent_id]["role"]
            content = turn.content

            # Check if agent is performing actions from other roles
            for other_role, role_def in self.ROLE_DEFINITIONS.items():
                if other_role == assigned_role:
                    continue

                # Semantic boundary check (if embeddings available)
                if self.embedder:
                    # Check similarity to other role's description
                    similarity = self.semantic_similarity(content[:300], role_def["description"])
                    if similarity >= 0 and similarity >= 0.65:  # High similarity to other role
                        violations.append({
                            "type": "boundary_violation",
                            "turns": [turn.turn_number],
                            "agent": agent_id,
                            "assigned_role": assigned_role,
                            "violated_role": other_role,
                            "similarity": similarity,
                            "severity": "moderate",
                            "description": f"{agent_id} ({assigned_role}) acting as {other_role}",
                        })
                        break  # Only report first violation per turn

                # Keyword fallback
                else:
                    content_lower = content.lower()
                    matches = sum(1 for indicator in role_def["indicators"] if indicator in content_lower)
                    if matches >= 2:  # Multiple indicators = likely violation
                        violations.append({
                            "type": "boundary_violation",
                            "turns": [turn.turn_number],
                            "agent": agent_id,
                            "assigned_role": assigned_role,
                            "violated_role": other_role,
                            "matches": matches,
                            "severity": "moderate",
                            "description": f"{agent_id} ({assigned_role}) using {other_role} patterns",
                        })
                        break

        return violations[:5]  # Limit to top 5

    def _detect_role_conflicts(
        self,
        turns: List[TurnSnapshot],
        agent_roles: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect multiple agents claiming or performing the same role."""
        conflicts = []

        # Group agents by role
        role_to_agents = {}
        for agent_id, role_info in agent_roles.items():
            role = role_info["role"]
            if role == "unclear":
                continue
            if role not in role_to_agents:
                role_to_agents[role] = []
            role_to_agents[role].append(agent_id)

        # Check for conflicts (multiple agents with same role)
        for role, agents in role_to_agents.items():
            if len(agents) > 1:
                # Find turns where both agents act in that role
                conflict_turns = []
                for turn in turns:
                    agent_id = turn.participant_id or "unknown"
                    if agent_id in agents:
                        conflict_turns.append(turn.turn_number)

                if len(conflict_turns) >= 2:  # Actual conflict (both agents active)
                    conflicts.append({
                        "type": "role_conflict",
                        "turns": conflict_turns[:3],  # Sample turns
                        "role": role,
                        "agents": agents,
                        "severity": "critical",  # Role conflicts are serious
                        "description": f"Multiple agents ({', '.join(agents)}) assigned {role} role",
                    })

        return conflicts

    def _detect_unauthorized_actions(
        self,
        turns: List[TurnSnapshot],
        agent_roles: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect agents performing actions outside their permission scope."""
        unauthorized = []

        # High-privilege actions that require specific roles
        sensitive_actions = {
            "delete": ["executor", "coordinator"],  # Only these roles can delete
            "deploy": ["executor", "coordinator"],
            "approve": ["reviewer", "coordinator"],
            "reject": ["reviewer", "coordinator"],
            "assign": ["coordinator"],  # Only coordinator can assign
            "delegate": ["coordinator"],
        }

        for turn in turns:
            agent_id = turn.participant_id or "unknown"

            # Skip if no role assigned
            if agent_id not in agent_roles or agent_roles[agent_id]["role"] == "unclear":
                continue

            assigned_role = agent_roles[agent_id]["role"]
            content_lower = turn.content.lower()

            # Check for sensitive actions
            for action, allowed_roles in sensitive_actions.items():
                if action in content_lower and assigned_role not in allowed_roles:
                    unauthorized.append({
                        "type": "unauthorized_action",
                        "turns": [turn.turn_number],
                        "agent": agent_id,
                        "assigned_role": assigned_role,
                        "action": action,
                        "allowed_roles": allowed_roles,
                        "severity": "critical",
                        "description": f"{agent_id} ({assigned_role}) attempted '{action}' (requires {allowed_roles})",
                    })

        return unauthorized[:3]  # Limit to top 3


class TurnAwareOutputValidationDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F12: Output Validation Failure in conversations.

    Analyzes whether agent outputs are properly validated:
    1. Missing validation - outputs produced without checking
    2. Failed validation - validation ran but output doesn't pass
    3. Uncaught errors - errors in output that weren't caught
    4. Format issues - output doesn't match expected format
    5. Incomplete output - missing required components

    Enhanced with semantic analysis (v2.0):
    - Error-after-success pattern detection using semantic shift
    - Output quality scoring based on information density
    - Validation completeness analysis

    Based on MAST research (NeurIPS 2025): FM-3.3 Incorrect Verification (28%)
    """

    name = "TurnAwareOutputValidationDetector"
    version = "2.1"  # Phase 1: Framework-specific completion signals
    supported_failure_modes = ["F12"]

    # Validation failure indicators
    VALIDATION_FAILURES = [
        "validation failed", "invalid output", "doesn't validate",
        "failed to validate", "validation error", "schema error",
        "type error", "format error", "malformed",
        "doesn't match", "expected format", "invalid format",
        "parsing error", "parse failed", "couldn't parse",
    ]

    # Missing validation indicators
    MISSING_VALIDATION = [
        "didn't check", "forgot to validate", "skipped validation",
        "no validation", "without checking", "unchecked",
        "assumed correct", "didn't verify", "unverified",
    ]

    # Output error indicators
    OUTPUT_ERRORS = [
        "output error", "result is wrong", "incorrect output",
        "wrong result", "bad output", "output incorrect",
        "doesn't work", "broken", "buggy", "syntax error",
        "runtime error", "compile error", "execution failed",
    ]

    # Phase 1: Framework-specific completion signals (indicators of successful completion)
    COMPLETION_SIGNALS = {
        "ChatDev": [
            r"task (?:is )?completed",
            r"successfully (?:completed|finished|delivered)",
            r"project (?:is )?complete",
            r"deliverables? (?:ready|complete)",
            r"all requirements? met",
            r"passed (?:all )?tests?",
        ],
        "AG2": [
            r"(?:task|problem) solved",
            r"answer (?:is|:)",
            r"final (?:answer|result|solution)",
            r"conclude that",
            r"therefore",
            r"in conclusion",
        ],
        "MetaGPT": [
            r"implementation complete",
            r"code (?:is )?ready",
            r"deliverable complete",
            r"phase complete",
        ],
        "Magentic": [
            r"result returned",
            r"function completed",
            r"output generated",
        ],
        "default": [
            r"completed successfully",
            r"task (?:is )?done",
            r"finished",
            r"ready (?:for|to)",
            r"here (?:is|are) (?:the|your)",
            r"i'?ve completed",
        ],
    }

    def __init__(self, min_turns: int = 2, min_issues_to_flag: int = 3, framework: Optional[str] = None):
        self.min_turns = min_turns
        self.min_issues_to_flag = min_issues_to_flag  # Raised to 3 to reduce FPs (17.8% FPR)
        self.framework = framework

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect output validation failures."""
        agent_turns = [t for t in turns if t.participant_type == "agent"]

        if len(agent_turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few agent turns to analyze",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for validation failure indicators
        validation_issues = self._detect_validation_failures(turns)
        issues.extend(validation_issues)
        for issue in validation_issues:
            affected_turns.extend(issue.get("turns", []))

        # 2. Check for missing validation
        missing_issues = self._detect_missing_validation(turns)
        issues.extend(missing_issues)
        for issue in missing_issues:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for output errors
        error_issues = self._detect_output_errors(turns)
        issues.extend(error_issues)
        for issue in error_issues:
            affected_turns.extend(issue.get("turns", []))

        # 4. Check for code that doesn't run/compile
        code_issues = self._detect_broken_code(agent_turns)
        issues.extend(code_issues)
        for issue in code_issues:
            affected_turns.extend(issue.get("turns", []))

        # Phase 1: Check for completion signals that indicate successful output
        has_completion_signal = self._has_completion_signals(turns)
        if has_completion_signal:
            # If we have strong completion signals, be more lenient
            # Allow 1 more issue before flagging (reduce false positives)
            min_issues = self.min_issues_to_flag + 1
        else:
            min_issues = self.min_issues_to_flag

        # Require multiple issues to reduce false positives
        if len(issues) < min_issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Insufficient evidence ({len(issues)} issue(s), need {self.min_issues_to_flag}+)",
                detector_name=self.name,
            )

        if len(issues) >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F12",
            explanation=f"Output validation failure: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Add output validation: 1) Validate all outputs against schema, "
                "2) Run tests before returning results, 3) Check for common errors, "
                "4) Verify output format matches expectations."
            ),
            detector_name=self.name,
        )

    def _has_completion_signals(self, turns: List[TurnSnapshot]) -> bool:
        """Phase 1: Check if conversation contains framework-specific completion signals."""
        # Get patterns for this framework (or default)
        framework_key = self.framework if self.framework in self.COMPLETION_SIGNALS else "default"
        patterns = self.COMPLETION_SIGNALS.get(framework_key, [])
        patterns.extend(self.COMPLETION_SIGNALS["default"])  # Always include default patterns

        # Check last few agent turns for completion signals
        agent_turns = [t for t in turns if t.participant_type == "agent"]
        last_turns = agent_turns[-3:] if len(agent_turns) >= 3 else agent_turns

        import re
        for turn in last_turns:
            content_lower = turn.content.lower()
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    return True
        return False

    def _detect_validation_failures(self, turns: List[TurnSnapshot]) -> list:
        """Detect explicit validation failures."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.VALIDATION_FAILURES:
                if indicator in content_lower:
                    issues.append({
                        "type": "validation_failure",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Validation failure: '{indicator}'",
                    })
                    break
        return issues[:3]

    def _detect_missing_validation(self, turns: List[TurnSnapshot]) -> list:
        """Detect missing validation."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.MISSING_VALIDATION:
                if indicator in content_lower:
                    issues.append({
                        "type": "missing_validation",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Missing validation: '{indicator}'",
                    })
                    break
        return issues[:2]

    def _detect_output_errors(self, turns: List[TurnSnapshot]) -> list:
        """Detect output errors."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.OUTPUT_ERRORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "output_error",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Output error: '{indicator}'",
                    })
                    break
        return issues[:3]

    def _detect_broken_code(self, agent_turns: List[TurnSnapshot]) -> list:
        """Detect code blocks followed by error mentions."""
        issues = []
        for i, turn in enumerate(agent_turns):
            # Check if this turn has code
            has_code = "```" in turn.content or "def " in turn.content or "class " in turn.content
            if has_code and i < len(agent_turns) - 1:
                # Check next turns for error indicators
                for j in range(i + 1, min(i + 3, len(agent_turns))):
                    next_content = agent_turns[j].content.lower()
                    if any(err in next_content for err in ["error", "failed", "doesn't work", "bug", "fix"]):
                        issues.append({
                            "type": "broken_code",
                            "turns": [turn.turn_number, agent_turns[j].turn_number],
                            "description": "Code followed by error discussion",
                        })
                        break
        return issues[:2]


class TurnAwareQualityGateBypassDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F13: Quality Gate Bypass in conversations.

    Analyzes whether quality checks are properly followed:
    1. Skipped reviews - code review or QA steps skipped
    2. Ignored warnings - warnings present but ignored
    3. Bypassed checks - explicitly skipping quality gates
    4. Missing tests - no testing before deployment/completion
    5. Rush to completion - moving forward despite issues

    Enhanced with semantic analysis (v2.0):
    - Sentiment shift detection (positive → negative)
    - Quality discussion density scoring
    - Verification completeness tracking

    Based on MAST research (NeurIPS 2025): FM-3.2 No/Incomplete Verification (50%)
    """

    name = "TurnAwareQualityGateBypassDetector"
    version = "2.1"  # Added rubber-stamp verification detection
    supported_failure_modes = ["F13"]

    # Bypass indicators - made more specific to reduce FPs
    # Removed single words like "later", "v2" that are too common
    BYPASS_INDICATORS = [
        "skip the review", "let's skip testing", "skipping the test",
        "bypass the check", "bypass validation",
        "ignore the warning", "ignoring the error",
        "no need to test", "skip testing", "skip review",
        "good enough for now", "ship it anyway", "move on anyway",
        "we can fix it later", "TODO: fix later", "FIXME: later",
        # Deferral patterns - stricter
        "defer to next release", "post-release fix",
        "add this in v2", "phase 2 feature", "next sprint item",
        "out of scope for now", "future work item",
        # Added for improved recall (v2.1)
        "moving forward without", "accepting the risk",
        "deploying despite", "skipping for now",
        "we can test later", "test this later",
        "proceed without testing", "no time to test",
        "pushing without review", "merge without approval",
    ]

    # Warning ignore indicators - stricter
    WARNING_IGNORES = [
        "ignore this warning", "suppress this warning", "disable warning for",
        "warning ignored because", "warnings disabled for",
        "lint disable for", "noqa:", "pylint: disable=",
        "eslint-disable-next", "despite the warning", "@suppress(",
        # Error handling - stricter
        "ignoring this error", "error ignored because", "skip this error",
        "known issue in", "accepted risk for", "won't fix because",
        "proceed anyway because", "continue anyway despite",
    ]

    # Missing quality steps - stricter
    MISSING_QUALITY = [
        "no tests written", "without any testing", "untested code",
        "no review done", "without code review", "unreviewed code",
        "no qa performed", "skip qa step", "no quality check",
        "didn't test this", "haven't tested yet", "not tested yet",
        # Incomplete verification - stricter
        "no verification done", "unverified changes", "not verified yet",
        "no validation performed", "not validated yet",
        "assume it's correct", "trust me on this",
    ]

    # Rush indicators - stricter
    RUSH_INDICATORS = [
        "quick and dirty fix", "just ship it", "good enough for now",
        "will fix this later", "temporary workaround", "hack for now",
        "workaround for the", "shortcut to avoid", "quick fix for",
        "time constraint forces", "deadline pressure",
        # Rush patterns - stricter
        "crunch mode", "time pressure on", "minimal viable product",
        "bare minimum for", "cut corners on", "expedite at cost",
    ]

    # Verifier role indicators (v2.1 - rubber-stamp detection)
    VERIFIER_ROLE_INDICATORS = [
        "verifier", "validator", "reviewer", "checker", "qa",
        "agent_verifier", "verify_agent", "verification",
    ]

    # Rubber-stamp verification patterns (weak verification without rigor)
    # Note: Removed patterns that can indicate other failure modes (F12, F14)
    RUBBER_STAMP_PATTERNS = [
        # Explicit rubber-stamping without checking
        "looks correct without", "seems correct but",
        "looks good to me", "lgtm",
        # Acceptance without evidence
        "approve without review", "skip verification",
        "no review needed", "verification not required",
        "skip the check", "bypass the review",
    ]

    # Weak verification phrases (verification claimed but no substance)
    WEAK_VERIFICATION_PHRASES = [
        "verified", "validation complete", "check complete",
        "review complete", "qa passed", "looks good",
        "all good", "approved", "accepted",
    ]

    def __init__(self, min_turns: int = 2, min_issues_to_flag: int = 1):
        self.min_turns = min_turns
        self.min_issues_to_flag = min_issues_to_flag  # Lowered for recall: was 2, now 1

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect quality gate bypass issues."""
        agent_turns = [t for t in turns if t.participant_type == "agent"]

        if len(agent_turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few agent turns to analyze",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for bypass indicators
        bypass_issues = self._detect_bypass(turns)
        issues.extend(bypass_issues)
        for issue in bypass_issues:
            affected_turns.extend(issue.get("turns", []))

        # 2. Check for warning ignores
        warning_issues = self._detect_warning_ignores(turns)
        issues.extend(warning_issues)
        for issue in warning_issues:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for missing quality steps
        missing_issues = self._detect_missing_quality(turns)
        issues.extend(missing_issues)
        for issue in missing_issues:
            affected_turns.extend(issue.get("turns", []))

        # 4. Check for rush indicators
        rush_issues = self._detect_rush(turns)
        issues.extend(rush_issues)
        for issue in rush_issues:
            affected_turns.extend(issue.get("turns", []))

        # 5. Check for rubber-stamp verification (v2.1)
        rubber_stamp_issues = self._detect_rubber_stamp_verification(turns)
        issues.extend(rubber_stamp_issues)
        for issue in rubber_stamp_issues:
            affected_turns.extend(issue.get("turns", []))

        # 6. Check for absent verification (v2.1)
        absent_issues = self._detect_absent_verification(turns)
        issues.extend(absent_issues)
        for issue in absent_issues:
            affected_turns.extend(issue.get("turns", []))

        # Require at least one strong evidence issue for detection
        # Semantic-only evidence or weak_verification alone is too prone to false positives
        strong_types = {"bypass", "warning_ignore", "rush", "rubber_stamp", "absent_verification"}
        has_strong_evidence = any(
            issue.get("type") in strong_types and issue.get("method") != "semantic"
            for issue in issues
        )

        # Require minimum issues AND strong evidence to reduce false positives
        if len(issues) < self.min_issues_to_flag or not has_strong_evidence:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Insufficient evidence ({len(issues)} issue(s), need {self.min_issues_to_flag}+)",
                detector_name=self.name,
            )

        if len(issues) >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F13",
            explanation=f"Quality gate bypass: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Enforce quality gates: 1) Don't skip code reviews, "
                "2) Address warnings before proceeding, 3) Write tests before completion, "
                "4) Follow established quality processes."
            ),
            detector_name=self.name,
        )

    def _detect_bypass(self, turns: List[TurnSnapshot]) -> list:
        """Detect explicit bypass of quality gates.

        Phase 2 Enhancement: Uses semantic similarity to detect bypass intentions
        even when not explicitly stated with keywords.
        """
        issues = []

        # Keyword detection (primary method)
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.BYPASS_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "bypass",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Quality bypass: '{indicator}'",
                        "method": "keyword",
                    })
                    break

        # Semantic detection (if embeddings available)
        if self.embedder and len(issues) < 2:  # Only if not enough keyword matches
            bypass_patterns = [
                "Let's skip the testing phase to save time",
                "We can bypass code review this time",
                "Don't need to validate, just ship it",
            ]

            for turn in turns:
                if len(issues) >= 3:  # Limit total issues
                    break

                # Skip if already flagged by keywords
                if any(issue.get("turns") == [turn.turn_number] for issue in issues):
                    continue

                # Check semantic similarity to bypass patterns
                similarities = self.batch_semantic_similarity(turn.content[:300], bypass_patterns)
                if similarities:
                    max_sim = max(similarities)
                    if max_sim >= 0.80:  # High similarity = likely bypass (raised from 0.70)
                        issues.append({
                            "type": "bypass",
                            "turns": [turn.turn_number],
                            "similarity": max_sim,
                            "description": f"Semantic bypass detected (similarity: {max_sim:.2f})",
                            "method": "semantic",
                        })

        return issues[:3]

    def _detect_warning_ignores(self, turns: List[TurnSnapshot]) -> list:
        """Detect ignored warnings."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.WARNING_IGNORES:
                if indicator in content_lower:
                    issues.append({
                        "type": "warning_ignore",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Warning ignored: '{indicator}'",
                    })
                    break
        return issues[:2]

    def _detect_missing_quality(self, turns: List[TurnSnapshot]) -> list:
        """Detect missing quality steps.

        Phase 2 Enhancement: Uses semantic analysis to detect implicit
        admissions of skipped quality processes.
        """
        issues = []

        # Keyword detection
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.MISSING_QUALITY:
                if indicator in content_lower:
                    issues.append({
                        "type": "missing_quality",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Missing quality: '{indicator}'",
                        "method": "keyword",
                    })
                    break

        # Semantic detection (augment keyword findings)
        if self.embedder and len(issues) < 2:
            missing_patterns = [
                "We didn't write tests for this feature",
                "Code review wasn't performed on this change",
                "This needs to be verified but we haven't done that yet",
            ]

            for turn in turns:
                if len(issues) >= 2:
                    break

                if any(issue.get("turns") == [turn.turn_number] for issue in issues):
                    continue

                similarities = self.batch_semantic_similarity(turn.content[:300], missing_patterns)
                if similarities:
                    max_sim = max(similarities)
                    if max_sim >= 0.85:  # Raised from 0.78 to further reduce FPs
                        issues.append({
                            "type": "missing_quality",
                            "turns": [turn.turn_number],
                            "similarity": max_sim,
                            "description": f"Semantic missing quality detected (similarity: {max_sim:.2f})",
                            "method": "semantic",
                        })

        return issues[:2]

    def _detect_rush(self, turns: List[TurnSnapshot]) -> list:
        """Detect rush to completion."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.RUSH_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "rush",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Rush indicator: '{indicator}'",
                    })
                    break
        return issues[:2]

    def _detect_rubber_stamp_verification(self, turns: List[TurnSnapshot]) -> list:
        """Detect superficial/rubber-stamp verification (v2.1).

        This addresses the MAST F13 pattern where:
        - A Verifier role exists but does weak verification
        - Verification just confirms consensus without rigorous checking
        - No actual validation logic or error detection performed

        Returns:
            List of issues with rubber-stamp verification patterns
        """
        issues = []

        # First, check if there's a verifier role in the conversation
        has_verifier_role = False
        verifier_turns = []

        for turn in turns:
            content_lower = turn.content.lower()
            participant_lower = (turn.participant_id or "").lower()

            # Check if this is a verifier role
            is_verifier = False
            for indicator in self.VERIFIER_ROLE_INDICATORS:
                if indicator in participant_lower or f"name': '{indicator}" in content_lower:
                    is_verifier = True
                    has_verifier_role = True
                    break

            if is_verifier:
                verifier_turns.append(turn)

        # If no explicit verifier, look for verification-like turns
        if not verifier_turns:
            for turn in turns:
                content_lower = turn.content.lower()
                if any(phrase in content_lower for phrase in self.WEAK_VERIFICATION_PHRASES):
                    verifier_turns.append(turn)

        # Check verifier turns for rubber-stamp patterns
        for turn in verifier_turns:
            content_lower = turn.content.lower()

            # Check for rubber-stamp patterns
            for pattern in self.RUBBER_STAMP_PATTERNS:
                if pattern in content_lower:
                    # Check if there's actual verification logic
                    has_substance = self._has_verification_substance(turn.content)

                    if not has_substance:
                        issues.append({
                            "type": "rubber_stamp",
                            "turns": [turn.turn_number],
                            "pattern": pattern,
                            "description": f"Rubber-stamp verification: '{pattern}' without rigorous checking",
                        })
                        break  # One issue per turn

        # Also detect when verification is claimed but no evidence provided
        for turn in turns:
            content_lower = turn.content.lower()

            # Check for weak verification without substance
            for phrase in self.WEAK_VERIFICATION_PHRASES:
                if phrase in content_lower:
                    # Skip if already flagged
                    if any(turn.turn_number in issue.get("turns", []) for issue in issues):
                        continue

                    has_substance = self._has_verification_substance(turn.content)
                    if not has_substance:
                        issues.append({
                            "type": "weak_verification",
                            "turns": [turn.turn_number],
                            "phrase": phrase,
                            "description": f"Weak verification claimed: '{phrase}' without evidence",
                        })
                        break

        return issues[:3]  # Limit to avoid false positives

    def _detect_absent_verification(self, turns: List[TurnSnapshot]) -> list:
        """Detect complete absence of verification in completed traces (v2.1).

        F13 is often about verification NOT happening at all, not explicit bypass.
        This detects when a task is completed without any verification step.
        """
        issues = []

        # Check if there's a completion claim
        completion_patterns = [
            "task complete", "done", "finished", "all done",
            "solution_found", "final answer", "implementation complete",
            "here's the solution", "problem solved", "mission accomplished",
        ]

        # Verification-related keywords that should appear somewhere
        verification_keywords = [
            "test", "verify", "validate", "check", "review",
            "confirm", "ensure", "assert", "evaluate", "examine",
        ]

        has_completion = False
        has_verification = False

        for turn in turns:
            content_lower = turn.content.lower()

            # Check for completion
            for pattern in completion_patterns:
                if pattern in content_lower:
                    has_completion = True
                    break

            # Check for verification keywords
            for keyword in verification_keywords:
                if keyword in content_lower:
                    has_verification = True
                    break

        # If completed without verification keywords, flag it
        if has_completion and not has_verification:
            issues.append({
                "type": "absent_verification",
                "turns": [turns[-1].turn_number] if turns else [],
                "description": "Task completed without any verification/testing mentioned",
            })

        return issues

    def _has_verification_substance(self, content: str) -> bool:
        """Check if verification content has substantive checking.

        Substantive verification includes:
        - Error detection/correction
        - Mathematical or logical validation
        - Test execution results
        - Specific issue identification

        Returns:
            True if verification has substance, False if rubber-stamp
        """
        content_lower = content.lower()

        # Indicators of substantive verification
        substance_indicators = [
            # Error detection
            "error found", "bug detected", "issue identified", "problem found",
            "incorrect", "wrong", "mistake", "flaw", "defect",
            # Logical validation
            "because", "since", "therefore", "thus", "hence",
            "the reason is", "this is because", "due to",
            # Mathematical validation
            "calculation shows", "computed as", "evaluates to",
            "=", "equals", "results in",
            # Test execution
            "test passed", "test failed", "execution result",
            "output shows", "returns", "produces",
            # Specific issue identification
            "specifically", "in particular", "notably",
            "line ", "function ", "variable ",
        ]

        substance_count = sum(1 for ind in substance_indicators if ind in content_lower)

        # Require at least 2 substance indicators for real verification
        return substance_count >= 2


class TurnAwareCompletionMisjudgmentDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects F14: Completion Misjudgment in conversations.

    Analyzes whether task completion is correctly assessed:
    1. Premature completion - declaring done when not finished
    2. Incomplete requirements - not all requirements addressed
    3. Unfinished work - obvious gaps in deliverables
    4. False success claims - claiming success despite failures
    5. Missed acceptance criteria - not meeting stated criteria

    Phase 2 Enhancement (v2.0): Uses semantic similarity to:
    - Detect confidence level in completion claims (high confidence vs uncertain)
    - Identify semantic inconsistencies between completion and status
    - Track requirement coverage using embedding similarity
    - Detect incomplete deliverables through semantic gap analysis

    Based on MAST research (NeurIPS 2025): FM-3.1 Completion Misjudgment (23%)
    """

    name = "TurnAwareCompletionMisjudgmentDetector"
    version = "2.0"  # Phase 2: Enhanced with semantic analysis
    supported_failure_modes = ["F14"]

    # Premature completion indicators - made more specific to reduce FPs
    # "done" alone is too common - require more explicit completion claims
    PREMATURE_COMPLETION = [
        "task is complete", "task complete", "task finished",
        "all done", "completely done", "fully completed",
        "mission accomplished", "final version",
        "implementation complete", "development complete",
        "work is complete", "everything is done",
        # Added for improved recall (v2.1) - implicit completion claims
        "here's the solution", "here's the implementation",
        "i've implemented", "i have implemented",
        "solution below", "see attached",
        "here is the final", "here's the finished",
        "ready for review", "ready for deployment",
    ]

    # Incomplete indicators following completion - stricter patterns
    INCOMPLETE_INDICATORS = [
        "still need to", "remaining tasks", "left to do", "not yet finished",
        "missing parts", "incomplete implementation", "partial solution",
        "TODO:", "FIXME:", "TBD:", "WIP:",
        "placeholder code", "stub implementation", "mock data",
        "need to finish", "haven't completed", "not fully",
    ]

    # False success indicators - stricter patterns
    FALSE_SUCCESS = [
        "should probably work", "might not work", "probably won't work",
        "seems to work but", "appears to work but", "looks like it might",
        "assuming it works", "hopefully it works", "fingers crossed",
        "not sure if it works", "haven't tested", "untested code",
    ]

    # Continuation needed indicators - stricter patterns
    CONTINUATION_NEEDED = [
        "next step is to", "then we need to", "after that we need",
        "following that we must", "additionally we need",
        "don't forget to", "remember to also", "make sure to also",
        "still need to complete", "have to also do", "need to also finish",
    ]

    def __init__(self, min_turns: int = 2, min_issues_to_flag: int = 1):
        self.min_turns = min_turns
        self.min_issues_to_flag = min_issues_to_flag  # Lowered for recall: was 2, now 1

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect completion misjudgment issues."""
        if len(turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to analyze",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for completion followed by incompleteness
        completion_issues = self._detect_premature_completion(turns)
        issues.extend(completion_issues)
        for issue in completion_issues:
            affected_turns.extend(issue.get("turns", []))

        # 2. Check for false success claims
        false_success_issues = self._detect_false_success(turns)
        issues.extend(false_success_issues)
        for issue in false_success_issues:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for continuation needed after completion claim
        continuation_issues = self._detect_continuation_needed(turns)
        issues.extend(continuation_issues)
        for issue in continuation_issues:
            affected_turns.extend(issue.get("turns", []))

        # 4. Check for TODO/FIXME in "completed" work
        todo_issues = self._detect_unfinished_markers(turns)
        issues.extend(todo_issues)
        for issue in todo_issues:
            affected_turns.extend(issue.get("turns", []))

        # Require multiple issues to reduce false positives
        if len(issues) < self.min_issues_to_flag:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Insufficient evidence ({len(issues)} issue(s), need {self.min_issues_to_flag}+)",
                detector_name=self.name,
            )

        if len(issues) >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F14",
            explanation=f"Completion misjudgment: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Verify completion properly: 1) Check all requirements are met, "
                "2) Test the output before declaring done, 3) Review for TODOs/FIXMEs, "
                "4) Validate against acceptance criteria."
            ),
            detector_name=self.name,
        )

    def _detect_premature_completion(self, turns: List[TurnSnapshot]) -> list:
        """Detect completion claims followed by incompleteness."""
        issues = []
        for i, turn in enumerate(turns):
            content_lower = turn.content.lower()
            # Check for completion claim
            has_completion = any(ind in content_lower for ind in self.PREMATURE_COMPLETION)
            if has_completion:
                # Check same turn or next turns for incompleteness
                all_content = content_lower
                if i < len(turns) - 1:
                    all_content += " " + turns[i + 1].content.lower()

                for ind in self.INCOMPLETE_INDICATORS:
                    if ind.lower() in all_content:
                        issues.append({
                            "type": "premature_completion",
                            "turns": [turn.turn_number],
                            "indicator": ind,
                            "description": f"Completion claim with incompleteness: '{ind}'",
                        })
                        break
        return issues[:3]

    def _detect_false_success(self, turns: List[TurnSnapshot]) -> list:
        """Detect uncertain success claims.

        Phase 2 Enhancement: Uses semantic similarity to detect lack of confidence
        in completion claims even without explicit uncertainty keywords.
        """
        issues = []

        # Keyword detection
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.FALSE_SUCCESS:
                if indicator in content_lower:
                    issues.append({
                        "type": "false_success",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Uncertain success: '{indicator}'",
                        "method": "keyword",
                    })
                    break

        # Semantic detection - detect uncertain completion claims
        if self.embedder and len(issues) < 2:
            uncertain_completion_patterns = [
                "I think it works, but I'm not completely certain",
                "The solution might be correct, but needs verification",
                "This appears to solve the problem, though untested",
            ]

            confident_completion_patterns = [
                "The task is completed successfully and verified",
                "All requirements have been met and tested",
                "Solution is confirmed working as expected",
            ]

            for turn in turns:
                if len(issues) >= 3:
                    break

                if any(issue.get("turns") == [turn.turn_number] for issue in issues):
                    continue

                content = turn.content[:400]

                # Check for completion claim
                has_completion = any(ind in content.lower() for ind in self.PREMATURE_COMPLETION)
                if not has_completion:
                    continue

                # Compare confidence: uncertain vs confident completion
                uncertain_sims = self.batch_semantic_similarity(content, uncertain_completion_patterns)
                confident_sims = self.batch_semantic_similarity(content, confident_completion_patterns)

                if uncertain_sims and confident_sims:
                    max_uncertain = max(uncertain_sims)
                    max_confident = max(confident_sims)

                    # If more similar to uncertain than confident completion
                    if max_uncertain >= 0.62 and max_uncertain > max_confident + 0.10:
                        issues.append({
                            "type": "false_success",
                            "turns": [turn.turn_number],
                            "uncertainty_score": max_uncertain,
                            "confidence_score": max_confident,
                            "description": f"Semantically uncertain completion claim (uncertainty: {max_uncertain:.2f})",
                            "method": "semantic",
                        })

        return issues[:3]

    def _detect_continuation_needed(self, turns: List[TurnSnapshot]) -> list:
        """Detect continuation needed after completion."""
        issues = []
        completion_found = False

        for turn in turns:
            content_lower = turn.content.lower()

            # Track if completion was claimed
            if any(ind in content_lower for ind in self.PREMATURE_COMPLETION):
                completion_found = True

            # After completion, check for continuation needs
            if completion_found:
                for indicator in self.CONTINUATION_NEEDED:
                    if indicator in content_lower:
                        issues.append({
                            "type": "continuation_needed",
                            "turns": [turn.turn_number],
                            "indicator": indicator,
                            "description": f"More work needed after completion: '{indicator}'",
                        })
                        break
        return issues[:2]

    def _detect_unfinished_markers(self, turns: List[TurnSnapshot]) -> list:
        """Detect TODO/FIXME markers in supposedly complete work."""
        issues = []
        markers = ["TODO", "FIXME", "XXX", "HACK", "TBD", "WIP"]

        for turn in turns:
            content = turn.content
            for marker in markers:
                if marker in content:
                    issues.append({
                        "type": "unfinished_marker",
                        "turns": [turn.turn_number],
                        "marker": marker,
                        "description": f"Unfinished marker: {marker}",
                    })
                    break
        return issues[:3]


class TurnAwareTerminationAwarenessDetector(EmbeddingMixin, TurnAwareDetector):
    """Detects FM-1.5: Unaware of Termination Conditions.

    Based on MAST research (NeurIPS 2025): This is the highest-prevalence
    failure mode in FC1 (40% of system design failures).

    Detects:
    1. Missing termination signals in long conversations
    2. Continuation after explicit termination
    3. Repeated completion claims without actual completion
    4. Infinite processing without progress indicators

    Enhanced with semantic analysis (v2.0):
    - Semantic similarity to detect completion claims
    - Progress tracking via embedding drift
    - Task completion verification

    Reference: https://arxiv.org/abs/2503.13657
    """

    name = "TurnAwareTerminationAwarenessDetector"
    version = "2.0"  # Semantic enhancement
    supported_failure_modes = ["F15"]  # FM-1.5 maps to new F15

    # Explicit termination signals
    TERMINATION_SIGNALS = [
        "terminate", "done", "complete", "finished",
        "task complete", "goal achieved", "mission accomplished",
        "all done", "nothing more", "that's all",
        "successfully completed", "work is done", "task finished",
        "end of task", "completed successfully", "job done",
    ]

    # Signals that conversation continues after termination
    CONTINUATION_AFTER_TERMINATION = [
        "but wait", "actually", "one more thing",
        "let me also", "additionally", "furthermore",
        "however", "also need to", "i should also",
        "before we finish", "wait", "hold on",
    ]

    # Progress indicators that show work is happening
    PROGRESS_INDICATORS = [
        "step", "progress", "moving on", "next",
        "continuing", "proceeding", "working on",
        "now i'll", "let me", "i will",
    ]

    def __init__(
        self,
        max_turns_without_termination: int = 25,
        max_turns_without_progress: int = 10,
    ):
        self.max_turns_without_termination = max_turns_without_termination
        self.max_turns_without_progress = max_turns_without_progress

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect termination awareness failures."""
        if len(turns) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to analyze termination patterns",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for missing termination in long conversations
        missing_term = self._detect_missing_termination(turns)
        issues.extend(missing_term)

        # 2. Check for continuation after termination
        ignored_term = self._detect_ignored_termination(turns)
        issues.extend(ignored_term)
        for issue in ignored_term:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for stalled progress
        stalled = self._detect_stalled_progress(turns)
        issues.extend(stalled)

        # 4. Check for repeated completion claims
        repeated = self._detect_repeated_completion_claims(turns)
        issues.extend(repeated)
        for issue in repeated:
            affected_turns.extend(issue.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation="No termination awareness issues detected",
                detector_name=self.name,
            )

        # Severity based on issue count and type
        has_critical = any(i.get("type") == "ignored_termination" for i in issues)
        if has_critical or len(issues) >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.90, 0.55 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F15",
            explanation=f"Termination awareness failure: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Implement clear termination conditions: 1) Define explicit stopping criteria, "
                "2) Add termination signal recognition, 3) Prevent processing after completion, "
                "4) Add progress indicators and maximum iteration limits."
            ),
            detector_name=self.name,
        )

    def _detect_missing_termination(self, turns: List[TurnSnapshot]) -> list:
        """Detect conversations that run too long without termination."""
        issues = []

        if len(turns) > self.max_turns_without_termination:
            # Check if there's any termination signal in recent turns
            recent_turns = turns[-5:]
            has_termination = any(
                any(sig in t.content.lower() for sig in self.TERMINATION_SIGNALS)
                for t in recent_turns
            )

            if not has_termination:
                issues.append({
                    "type": "missing_termination",
                    "turns": [len(turns)],
                    "description": f"Long conversation ({len(turns)} turns) without termination signal",
                })

        return issues

    def _detect_ignored_termination(self, turns: List[TurnSnapshot]) -> list:
        """Detect when termination signals are ignored."""
        issues = []

        for i, turn in enumerate(turns[:-1]):
            content_lower = turn.content.lower()

            # Check if this turn has termination signal
            has_termination = any(sig in content_lower for sig in self.TERMINATION_SIGNALS)

            if has_termination:
                # Check if next turn continues inappropriately
                next_turn = turns[i + 1]
                next_lower = next_turn.content.lower()

                # Check for continuation markers
                continues = any(cont in next_lower for cont in self.CONTINUATION_AFTER_TERMINATION)

                # Or if the next turn is from same participant continuing work
                same_participant = turn.participant_id == next_turn.participant_id
                substantial_content = len(next_turn.content) > 100

                if continues or (same_participant and substantial_content):
                    issues.append({
                        "type": "ignored_termination",
                        "turns": [turn.turn_number, next_turn.turn_number],
                        "description": "Conversation continues after termination signal",
                    })

        return issues[:2]

    def _detect_stalled_progress(self, turns: List[TurnSnapshot]) -> list:
        """Detect when conversation stalls without progress."""
        issues = []

        if len(turns) < self.max_turns_without_progress:
            return issues

        # Check recent turns for progress indicators
        recent = turns[-self.max_turns_without_progress:]
        progress_count = sum(
            1 for t in recent
            if any(prog in t.content.lower() for prog in self.PROGRESS_INDICATORS)
        )

        # If very few progress indicators in many turns
        if progress_count < 2:
            issues.append({
                "type": "stalled_progress",
                "turns": [t.turn_number for t in recent],
                "description": f"No progress indicators in last {self.max_turns_without_progress} turns",
            })

        return issues

    def _detect_repeated_completion_claims(self, turns: List[TurnSnapshot]) -> list:
        """Detect repeated claims of completion without actual termination."""
        issues = []
        completion_turns = []

        for turn in turns:
            content_lower = turn.content.lower()
            if any(sig in content_lower for sig in self.TERMINATION_SIGNALS[:6]):
                completion_turns.append(turn.turn_number)

        # Multiple completion claims suggests issues
        if len(completion_turns) >= 3:
            issues.append({
                "type": "repeated_completion_claims",
                "turns": completion_turns,
                "description": f"Multiple completion claims ({len(completion_turns)}) without actual termination",
            })

        return issues


class TurnAwareReasoningActionMismatchDetector(TurnAwareDetector):
    """Detects FM-2.6: Reasoning-Action Mismatch.

    Based on MAST research (NeurIPS 2025): This is the highest-prevalence
    failure mode in FC2 (26% of inter-agent misalignment failures).

    Detects discrepancy between stated reasoning and actual actions:
    1. Intent expressed but different action taken
    2. Reasoning suggests one approach, execution uses another
    3. Chain-of-thought diverges from final action
    4. Stated goals don't match actions taken

    Reference: https://arxiv.org/abs/2503.13657
    ReAct Framework: https://arxiv.org/abs/2210.03629
    """

    name = "TurnAwareReasoningActionMismatchDetector"
    version = "1.0"
    supported_failure_modes = ["F16"]  # FM-2.6 maps to new F16

    # Intent markers in reasoning
    INTENT_MARKERS = {
        "search": ["will search", "going to search", "let me search", "searching for", "i'll look up"],
        "write": ["will write", "going to create", "let me write", "i'll generate", "creating"],
        "read": ["will read", "going to read", "let me examine", "i'll review", "reading"],
        "calculate": ["will calculate", "going to compute", "let me figure", "computing"],
        "execute": ["will run", "going to execute", "let me run", "executing", "running"],
        "analyze": ["will analyze", "going to analyze", "let me analyze", "analyzing"],
        "fix": ["will fix", "going to fix", "let me fix", "fixing", "correcting"],
        "test": ["will test", "going to test", "let me test", "testing", "verifying"],
    }

    # Action indicators
    ACTION_INDICATORS = {
        "search": ["searched", "found", "results show", "search returned", "query results"],
        "write": ["wrote", "created", "generated", "here's the code", "here is the"],
        "read": ["read", "examined", "reviewed", "content shows", "file contains"],
        "calculate": ["calculated", "computed", "result is", "equals", "total"],
        "execute": ["ran", "executed", "output:", "returned", "result:"],
        "analyze": ["analyzed", "analysis shows", "found that", "discovered"],
        "fix": ["fixed", "corrected", "updated", "changed", "modified"],
        "test": ["tested", "test passed", "test failed", "verification", "confirmed"],
    }

    # Contradiction patterns
    CONTRADICTIONS = [
        ("will search", "without searching"),
        ("will read", "without reading"),
        ("will test", "skipping test"),
        ("will verify", "assuming correct"),
        ("need to check", "assuming"),
        ("should validate", "looks correct"),
    ]

    def __init__(self, min_turns: int = 3):
        self.min_turns = min_turns

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect reasoning-action mismatches."""
        agent_turns = [t for t in turns if t.participant_type == "agent"]

        if len(agent_turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few agent turns to analyze reasoning patterns",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for intent-action mismatches within turns
        within_turn = self._detect_within_turn_mismatch(agent_turns)
        issues.extend(within_turn)
        for issue in within_turn:
            affected_turns.extend(issue.get("turns", []))

        # 2. Check for cross-turn intent-action mismatches
        cross_turn = self._detect_cross_turn_mismatch(agent_turns)
        issues.extend(cross_turn)
        for issue in cross_turn:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for explicit contradictions
        contradictions = self._detect_contradictions(agent_turns)
        issues.extend(contradictions)
        for issue in contradictions:
            affected_turns.extend(issue.get("turns", []))

        # 4. Check for saying-doing gaps
        saying_doing = self._detect_saying_doing_gap(agent_turns)
        issues.extend(saying_doing)
        for issue in saying_doing:
            affected_turns.extend(issue.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.82,
                failure_mode=None,
                explanation="No reasoning-action mismatches detected",
                detector_name=self.name,
            )

        if len(issues) >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.88, 0.52 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F16",
            explanation=f"Reasoning-action mismatch: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Ensure reasoning aligns with actions: 1) Verify intended actions are executed, "
                "2) Add explicit action logging, 3) Implement thought-action consistency checks, "
                "4) Use ReAct-style structured reasoning with explicit action verification."
            ),
            detector_name=self.name,
        )

    def _detect_within_turn_mismatch(self, turns: List[TurnSnapshot]) -> list:
        """Detect mismatches between reasoning and action within same turn."""
        issues = []

        for turn in turns:
            content_lower = turn.content.lower()

            for action_type, intent_phrases in self.INTENT_MARKERS.items():
                # Check if intent is expressed
                has_intent = any(phrase in content_lower for phrase in intent_phrases)

                if has_intent:
                    # Check if corresponding action is taken
                    action_phrases = self.ACTION_INDICATORS.get(action_type, [])
                    has_action = any(phrase in content_lower for phrase in action_phrases)

                    # If intent without action, might be mismatch
                    # But only flag if turn is substantial (not just planning)
                    if not has_action and len(turn.content) > 200:
                        issues.append({
                            "type": "intent_without_action",
                            "turns": [turn.turn_number],
                            "intent": action_type,
                            "description": f"Expressed intent to '{action_type}' but no action taken",
                        })

        return issues[:2]

    def _detect_cross_turn_mismatch(self, turns: List[TurnSnapshot]) -> list:
        """Detect mismatches between turns (intent in one, no action in next)."""
        issues = []

        for i in range(len(turns) - 1):
            current = turns[i]
            next_turn = turns[i + 1]
            current_lower = current.content.lower()
            next_lower = next_turn.content.lower()

            for action_type, intent_phrases in self.INTENT_MARKERS.items():
                has_intent = any(phrase in current_lower for phrase in intent_phrases)

                if has_intent:
                    # Check if next turn has the action
                    action_phrases = self.ACTION_INDICATORS.get(action_type, [])
                    next_has_action = any(phrase in next_lower for phrase in action_phrases)

                    # Check if next turn abandons the intent
                    abandons = any(phrase in next_lower for phrase in [
                        "instead", "actually", "let me", "different approach",
                        "skip", "ignore", "without"
                    ])

                    if not next_has_action and abandons:
                        issues.append({
                            "type": "abandoned_intent",
                            "turns": [current.turn_number, next_turn.turn_number],
                            "intent": action_type,
                            "description": f"Intent to '{action_type}' abandoned in next turn",
                        })

        return issues[:2]

    def _detect_contradictions(self, turns: List[TurnSnapshot]) -> list:
        """Detect explicit contradictions in reasoning."""
        issues = []

        for turn in turns:
            content_lower = turn.content.lower()

            for intent_phrase, contradiction_phrase in self.CONTRADICTIONS:
                if intent_phrase in content_lower and contradiction_phrase in content_lower:
                    issues.append({
                        "type": "explicit_contradiction",
                        "turns": [turn.turn_number],
                        "intent": intent_phrase,
                        "contradiction": contradiction_phrase,
                        "description": f"Contradiction: '{intent_phrase}' but '{contradiction_phrase}'",
                    })

        return issues[:2]

    def _detect_saying_doing_gap(self, turns: List[TurnSnapshot]) -> list:
        """Detect gaps between what agent says and does."""
        issues = []

        for turn in turns:
            content_lower = turn.content.lower()

            # Check for "I did X" without evidence of X
            claim_action_pairs = [
                ("tested", "test"),
                ("verified", "verif"),
                ("checked", "check"),
                ("validated", "valid"),
                ("confirmed", "confirm"),
            ]

            for claim, evidence in claim_action_pairs:
                if f"i {claim}" in content_lower or f"i have {claim}" in content_lower:
                    # Look for evidence of actual testing/verification
                    evidence_markers = [
                        "output:", "result:", "returned", "shows",
                        "passed", "failed", "error:", "success"
                    ]
                    has_evidence = any(marker in content_lower for marker in evidence_markers)

                    if not has_evidence:
                        issues.append({
                            "type": "claim_without_evidence",
                            "turns": [turn.turn_number],
                            "claim": claim,
                            "description": f"Claims to have {claim} but no evidence shown",
                        })

        return issues[:2]


class TurnAwareClarificationRequestDetector(TurnAwareDetector):
    """Detects FM-2.2: Failure to Ask for Clarification.

    Based on MAST research (NeurIPS 2025): 18% of FC2 failures.
    Agents proceed with ambiguous instructions without seeking clarification.

    Detects:
    1. Ambiguous task with no clarification request
    2. Proceeding despite uncertainty
    3. Making assumptions without verification
    4. Missing clarification in multi-step tasks

    Reference: https://arxiv.org/abs/2503.13657
    """

    name = "TurnAwareClarificationRequestDetector"
    version = "1.0"
    supported_failure_modes = ["F17"]  # FM-2.2 maps to new F17

    # Ambiguity indicators in user/task messages
    AMBIGUITY_MARKERS = [
        "maybe", "perhaps", "could be", "either", "or",
        "not sure", "unclear", "ambiguous", "vague",
        "depending", "depends on", "if needed",
        "something like", "kind of", "sort of",
        "whatever", "anything", "some", "any",
    ]

    # Assumption indicators without clarification
    ASSUMPTION_WITHOUT_CLARIFICATION = [
        "i'll assume", "assuming", "i assume",
        "let me assume", "i'm assuming", "assuming that",
        "i'll go with", "i'll use", "defaulting to",
        "probably means", "likely means", "must mean",
        "interpreting as", "taking this to mean",
    ]

    # Proper clarification request indicators
    CLARIFICATION_REQUESTS = [
        "could you clarify", "can you clarify", "please clarify",
        "what do you mean", "could you explain", "can you specify",
        "which one", "do you mean", "are you referring to",
        "to clarify", "just to confirm", "to make sure",
        "?",  # Questions in general
    ]

    def __init__(self, min_turns: int = 2):
        self.min_turns = min_turns

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect failure to ask for clarification."""
        if len(turns) < self.min_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns to analyze clarification patterns",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # 1. Check for assumptions without clarification
        assumptions = self._detect_assumptions_without_clarification(turns)
        issues.extend(assumptions)
        for issue in assumptions:
            affected_turns.extend(issue.get("turns", []))

        # 2. Check for proceeding with ambiguous input
        ambiguous = self._detect_proceeding_with_ambiguity(turns)
        issues.extend(ambiguous)
        for issue in ambiguous:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for missing clarification in complex tasks
        complex_task = self._detect_complex_task_without_clarification(turns)
        issues.extend(complex_task)
        for issue in complex_task:
            affected_turns.extend(issue.get("turns", []))

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.80,
                failure_mode=None,
                explanation="No clarification request failures detected",
                detector_name=self.name,
            )

        if len(issues) >= 3:
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.50 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F17",
            explanation=f"Clarification request failure: {len(issues)} issues found",
            affected_turns=list(set(affected_turns)),
            evidence={"issues": issues},
            suggested_fix=(
                "Ask for clarification when needed: 1) Identify ambiguous requirements, "
                "2) Ask specific clarifying questions before proceeding, "
                "3) Confirm assumptions with user, 4) Don't proceed on uncertain paths."
            ),
            detector_name=self.name,
        )

    def _detect_assumptions_without_clarification(self, turns: List[TurnSnapshot]) -> list:
        """Detect when agent makes assumptions without asking."""
        issues = []
        agent_turns = [t for t in turns if t.participant_type == "agent"]

        for turn in agent_turns:
            content_lower = turn.content.lower()

            # Check for assumption markers
            has_assumption = any(marker in content_lower for marker in self.ASSUMPTION_WITHOUT_CLARIFICATION)

            if has_assumption:
                # Check if there was a prior clarification request
                prior_turns = [t for t in turns if t.turn_number < turn.turn_number]
                asked_clarification = any(
                    any(req in t.content.lower() for req in self.CLARIFICATION_REQUESTS)
                    for t in prior_turns
                    if t.participant_type == "agent"
                )

                if not asked_clarification:
                    issues.append({
                        "type": "assumption_without_clarification",
                        "turns": [turn.turn_number],
                        "description": "Made assumption without asking for clarification",
                    })

        return issues[:2]

    def _detect_proceeding_with_ambiguity(self, turns: List[TurnSnapshot]) -> list:
        """Detect when agent proceeds despite ambiguous input."""
        issues = []

        # Find user turns with ambiguity
        for i, turn in enumerate(turns):
            if turn.participant_type in ("user", "system"):
                content_lower = turn.content.lower()
                has_ambiguity = any(marker in content_lower for marker in self.AMBIGUITY_MARKERS)

                if has_ambiguity:
                    # Check if next agent turn asks for clarification
                    next_agent_turns = [
                        t for t in turns[i+1:]
                        if t.participant_type == "agent"
                    ][:2]

                    asks_clarification = any(
                        any(req in t.content.lower() for req in self.CLARIFICATION_REQUESTS)
                        for t in next_agent_turns
                    )

                    if not asks_clarification and next_agent_turns:
                        issues.append({
                            "type": "proceeding_with_ambiguity",
                            "turns": [turn.turn_number, next_agent_turns[0].turn_number],
                            "description": "Proceeded with ambiguous input without clarification",
                        })

        return issues[:2]

    def _detect_complex_task_without_clarification(self, turns: List[TurnSnapshot]) -> list:
        """Detect complex multi-part tasks without clarification."""
        issues = []

        # Check first few turns for complex task indicators
        early_turns = turns[:3]
        for turn in early_turns:
            if turn.participant_type in ("user", "system"):
                content = turn.content

                # Indicators of complex/multi-part task
                complex_indicators = [
                    " and ", " then ", " also ", " additionally ",
                    "1.", "2.", "first", "second", "multiple",
                    "several", "various", "different",
                ]

                has_complexity = sum(1 for ind in complex_indicators if ind in content.lower())

                if has_complexity >= 2 and len(content) > 200:
                    # Check if agent asks clarifying questions
                    next_agent_turns = [t for t in turns if t.participant_type == "agent"][:2]
                    asks_questions = any(
                        "?" in t.content
                        for t in next_agent_turns
                    )

                    if not asks_questions:
                        issues.append({
                            "type": "complex_task_no_clarification",
                            "turns": [turn.turn_number],
                            "description": "Complex multi-part task without clarifying questions",
                        })

        return issues[:1]


# Convenience function to run all turn-aware detectors
def analyze_conversation_turns(
    turns: List[TurnSnapshot],
    conversation_metadata: Optional[Dict[str, Any]] = None,
    detectors: Optional[List[TurnAwareDetector]] = None,
    use_summarization: bool = True,
) -> List[TurnAwareDetectionResult]:
    """Run multiple turn-aware detectors on a conversation.

    Args:
        turns: List of conversation turns
        conversation_metadata: Optional metadata
        detectors: Optional list of detectors to run. If None, runs all defaults.
        use_summarization: Whether to use summarization for long conversations

    Returns:
        List of detection results (only those with detected=True)
    """
    if detectors is None:
        detectors = [
            TurnAwareSpecificationMismatchDetector(),  # F1
            TurnAwareTaskDecompositionDetector(),  # F2
            TurnAwareResourceMisallocationDetector(),  # F3
            TurnAwareConversationHistoryDetector(),  # F4
            TurnAwareLoopDetector(),  # F5
            TurnAwareDerailmentDetector(),  # F6
            TurnAwareContextNeglectDetector(),  # F7
            TurnAwareInformationWithholdingDetector(),  # F8
            TurnAwareRoleUsurpationDetector(),  # F9 - was missing!
            TurnAwareCommunicationBreakdownDetector(),  # F10
            TurnAwareCoordinationFailureDetector(),  # F11
            TurnAwareOutputValidationDetector(),  # F12
            TurnAwareQualityGateBypassDetector(),  # F13
            TurnAwareCompletionMisjudgmentDetector(),  # F14
            # New MAST-aligned detectors (NeurIPS 2025)
            TurnAwareTerminationAwarenessDetector(),  # F15 (FM-1.5, 40% of FC1)
            TurnAwareReasoningActionMismatchDetector(),  # F16 (FM-2.6, 26% of FC2)
            TurnAwareClarificationRequestDetector(),  # F17 (FM-2.2, 18% of FC2)
        ]

    # Check if conversation is long enough to need summarization
    working_turns = turns
    summarization_applied = False

    if use_summarization and len(turns) > MAX_TURNS_BEFORE_SUMMARIZATION:
        try:
            from app.core.summarizer import SlidingWindowManager, count_tokens

            # Check total tokens
            total_content = " ".join(t.content for t in turns)
            total_tokens = count_tokens(total_content)

            if total_tokens > MAX_TOKENS_BEFORE_SUMMARIZATION:
                logger.info(
                    f"Long conversation detected ({len(turns)} turns, ~{total_tokens} tokens). "
                    "Using sliding window for detection."
                )

                # For long conversations, we analyze in chunks
                # and aggregate results
                window_manager = SlidingWindowManager()

                # Convert TurnSnapshots to dicts for the window manager
                turn_dicts = [
                    {
                        "turn_number": t.turn_number,
                        "role": t.participant_type,
                        "participant_id": t.participant_id,
                        "content": t.content,
                        "content_hash": t.content_hash,
                    }
                    for t in turns
                ]

                # Get chunks for batch detection
                chunks = window_manager.chunk_for_batch_detection(turn_dicts)
                summarization_applied = True

                # For now, we'll just use the last chunk (most recent context)
                # Future enhancement: aggregate results from all chunks
                if chunks:
                    # Get turns covered by the last chunk
                    last_chunk = chunks[-1]
                    start_turn, end_turn = last_chunk.recent_turns

                    # Filter to recent turns
                    working_turns = [
                        t for t in turns
                        if start_turn <= t.turn_number <= end_turn
                    ]

                    # Always include first turn (task) if not already
                    first_turn = next((t for t in turns if t.turn_number == 1), None)
                    if first_turn and first_turn not in working_turns:
                        working_turns = [first_turn] + working_turns

        except ImportError as e:
            logger.warning(f"Summarizer not available, using full conversation: {e}")
        except Exception as e:
            logger.warning(f"Summarization failed, using full conversation: {e}")

    results = []
    for detector in detectors:
        try:
            result = detector.detect(working_turns, conversation_metadata)
            if result.detected:
                # Add summarization info to evidence if applicable
                if summarization_applied:
                    result.evidence["summarization_applied"] = True
                    result.evidence["original_turns"] = len(turns)
                    result.evidence["analyzed_turns"] = len(working_turns)
                results.append(result)
        except Exception as e:
            logger.error(f"Detector {detector.name} failed: {e}")

    return results


class LLMDerailmentDetector:
    """
    LLM-based F6 (Task Derailment) detector using Claude Opus 4.5.

    Unlike the pattern-based TurnAwareDerailmentDetector which uses keyword drift,
    this detector uses semantic understanding to detect when agents diverge from
    the original task. Required for MAST benchmark where agents stay on-topic
    but derail semantically.

    Usage:
        detector = LLMDerailmentDetector()
        result = detector.detect(snapshots, metadata)
    """

    name = "LLMDerailmentDetector"
    version = "1.0"
    supported_failure_modes = ["F6"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        confidence_threshold: float = 0.6,
    ):
        self.api_key = api_key
        self.confidence_threshold = confidence_threshold
        self._judge = None

    @property
    def judge(self):
        """Lazy-load the LLM judge."""
        if self._judge is None:
            from .mast_llm_judge import MASTLLMJudge
            self._judge = MASTLLMJudge(api_key=self.api_key)
        return self._judge

    def _convert_to_conversation_turns(
        self,
        snapshots: List[TurnSnapshot],
    ) -> List["ConversationTurn"]:
        """Convert TurnSnapshots to ConversationTurns for task extraction."""
        from .task_extractors import ConversationTurn

        turns = []
        for snapshot in snapshots:
            turns.append(ConversationTurn(
                role=snapshot.participant_type,
                content=snapshot.content,
                participant_id=snapshot.participant_id,
                metadata=snapshot.turn_metadata or {},
            ))
        return turns

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """
        Detect F6 (Task Derailment) using LLM verification.

        Args:
            turns: List of turn snapshots
            conversation_metadata: Optional metadata about the conversation

        Returns:
            TurnAwareDetectionResult with LLM-based detection
        """
        if len(turns) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns for LLM derailment analysis",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        metadata = conversation_metadata or {}

        # Convert to ConversationTurns and extract task
        conv_turns = self._convert_to_conversation_turns(turns)

        try:
            from .task_extractors import extract_task
            extraction = extract_task(conv_turns, metadata)
        except Exception as e:
            logger.warning(f"Task extraction failed: {e}")
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation=f"Task extraction failed: {e}",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        if not extraction.task:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="No task found in conversation",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Enhance agent output summary if it's too sparse
        # MAST trajectories often have sparse parsed content but rich raw data
        agent_summary = extraction.agent_output_summary
        if len(agent_summary) < 200:
            # Build summary from actual turn content
            agent_content = []
            for t in turns:
                if t.participant_type == "agent" and len(t.content) > 30:
                    # Skip metadata-only content
                    if not t.content.startswith("[") or len(t.content) > 100:
                        agent_content.append(t.content[:300])
            if agent_content:
                agent_summary = "\n---\n".join(agent_content[:5])

        # Call LLM judge
        try:
            from .mast_llm_judge import MASTFailureMode

            result = self.judge.evaluate(
                failure_mode=MASTFailureMode.F6,
                task=extraction.task[:2000],  # Truncate for token limits
                trace_summary=agent_summary[:2000],  # Use enhanced summary
                key_events=extraction.key_events,
            )
        except Exception as e:
            logger.error(f"LLM judge call failed: {e}")
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation=f"LLM verification failed: {e}",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Convert LLM verdict to detection result
        detected = result.verdict == "YES" and result.confidence >= self.confidence_threshold

        if detected:
            if result.confidence >= 0.85:
                severity = TurnAwareSeverity.SEVERE
            elif result.confidence >= 0.7:
                severity = TurnAwareSeverity.MODERATE
            else:
                severity = TurnAwareSeverity.MINOR
        else:
            severity = TurnAwareSeverity.NONE

        return TurnAwareDetectionResult(
            detected=detected,
            severity=severity,
            confidence=result.confidence,
            failure_mode="F6" if detected else None,
            explanation=result.reasoning if result.reasoning else (
                "LLM detected task derailment" if detected else "LLM found no task derailment"
            ),
            evidence={
                "llm_verdict": result.verdict,
                "llm_confidence": result.confidence,
                "llm_reasoning": result.reasoning,
                "task_extracted": extraction.task[:500],
                "framework_detected": extraction.framework,
                "model_used": result.model_used,
                "tokens_used": result.tokens_used,
                "cost_usd": result.cost_usd,
            },
            suggested_fix=(
                "Review agent focus and add task reminders. Consider: "
                "'Stay focused on: [ORIGINAL_TASK]. Do not address unrelated topics.'"
            ),
            detector_name=self.name,
            detector_version=MODULE_VERSION,
        )


class HybridDerailmentDetector:
    """
    Hybrid F6 (Task Derailment) detector: pattern-first, LLM-escalation.

    Cost optimization strategy:
    1. Run fast pattern detector first (free, <50ms)
    2. If pattern confidence >= 0.7, use pattern result (clear detection or clear negative)
    3. If pattern confidence < 0.7 (ambiguous), escalate to LLM (~$0.03/trace)

    This achieves ~80% cost savings vs LLM-only while maintaining accuracy.

    Usage:
        detector = HybridDerailmentDetector()
        result = detector.detect(snapshots, metadata)
    """

    name = "HybridDerailmentDetector"
    version = "1.0"
    supported_failure_modes = ["F6"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        escalation_threshold: float = 0.7,  # Below this confidence, escalate to LLM
        confidence_threshold: float = 0.6,  # Min confidence for LLM to detect
    ):
        self.api_key = api_key
        self.escalation_threshold = escalation_threshold
        self.confidence_threshold = confidence_threshold
        self._pattern_detector = None
        self._llm_detector = None

    @property
    def pattern_detector(self):
        """Lazy-load pattern detector."""
        if self._pattern_detector is None:
            self._pattern_detector = TurnAwareDerailmentDetector(
                drift_threshold=0.5,  # Sensitive for initial detection
                require_strong_evidence=False,
            )
        return self._pattern_detector

    @property
    def llm_detector(self):
        """Lazy-load LLM detector."""
        if self._llm_detector is None:
            self._llm_detector = LLMDerailmentDetector(
                api_key=self.api_key,
                confidence_threshold=self.confidence_threshold,
            )
        return self._llm_detector

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """
        Detect F6 (Task Derailment) using hybrid approach.

        Strategy:
        - Pattern detector first (fast, free)
        - Escalate to LLM only on ambiguous cases

        Args:
            turns: List of turn snapshots
            conversation_metadata: Optional metadata about the conversation

        Returns:
            TurnAwareDetectionResult with detection decision
        """
        if len(turns) < 3:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Too few turns for derailment analysis",
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Step 1: Run pattern detector
        pattern_result = self.pattern_detector.detect(turns, conversation_metadata)

        # Step 2: Decide if we need LLM escalation
        should_escalate = (
            pattern_result.confidence < self.escalation_threshold
            or (pattern_result.detected and pattern_result.confidence < 0.8)
        )

        if not should_escalate:
            # High confidence from pattern detector - use its result
            return TurnAwareDetectionResult(
                detected=pattern_result.detected,
                severity=pattern_result.severity,
                confidence=pattern_result.confidence,
                failure_mode=pattern_result.failure_mode,
                explanation=f"[Pattern] {pattern_result.explanation}",
                affected_turns=pattern_result.affected_turns,
                evidence={
                    **(pattern_result.evidence or {}),
                    "detection_method": "pattern",
                    "llm_escalated": False,
                },
                suggested_fix=pattern_result.suggested_fix,
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        # Step 3: Escalate to LLM for borderline cases
        try:
            llm_result = self.llm_detector.detect(turns, conversation_metadata)

            # Combine evidence from both detectors
            combined_evidence = {
                **(pattern_result.evidence or {}),
                **(llm_result.evidence or {}),
                "detection_method": "hybrid",
                "llm_escalated": True,
                "pattern_confidence": pattern_result.confidence,
                "pattern_detected": pattern_result.detected,
            }

            return TurnAwareDetectionResult(
                detected=llm_result.detected,
                severity=llm_result.severity,
                confidence=llm_result.confidence,
                failure_mode=llm_result.failure_mode,
                explanation=f"[LLM-verified] {llm_result.explanation}",
                affected_turns=llm_result.affected_turns or pattern_result.affected_turns,
                evidence=combined_evidence,
                suggested_fix=llm_result.suggested_fix,
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )

        except Exception as e:
            # LLM failed - fall back to pattern result
            logger.warning(f"LLM escalation failed, using pattern result: {e}")
            return TurnAwareDetectionResult(
                detected=pattern_result.detected,
                severity=pattern_result.severity,
                confidence=pattern_result.confidence,
                failure_mode=pattern_result.failure_mode,
                explanation=f"[Pattern-fallback] {pattern_result.explanation}",
                affected_turns=pattern_result.affected_turns,
                evidence={
                    **(pattern_result.evidence or {}),
                    "detection_method": "pattern_fallback",
                    "llm_escalated": True,
                    "llm_error": str(e),
                },
                suggested_fix=pattern_result.suggested_fix,
                detector_name=self.name,
                detector_version=MODULE_VERSION,
            )


# ============================================================================
# F2: Task Decomposition Detector (Turn-Aware)
# ============================================================================

class TurnAwareTaskDecompositionDetector(TurnAwareDetector):
    """Detects F2: Poor Task Decomposition in conversations.

    Analyzes whether complex tasks are properly broken down into subtasks:
    1. Missing decomposition - complex task handled as single step
    2. Vague subtasks - non-actionable or unclear steps
    3. Missing dependencies - steps out of order or disconnected
    4. Over-decomposition - simple task broken into too many steps
    5. Circular dependencies - steps that depend on each other

    Based on MAST taxonomy for orchestration failures.
    """

    name = "TurnAwareTaskDecompositionDetector"
    version = "1.0"
    supported_failure_modes = ["F2"]

    # Indicators of task complexity requiring decomposition
    COMPLEX_TASK_INDICATORS = [
        "system", "platform", "application", "service", "architecture",
        "authentication", "authorization", "database", "migration",
        "refactor", "integration", "infrastructure", "deployment",
        "pipeline", "workflow", "multi-step", "end-to-end",
    ]

    # Indicators that decomposition is happening
    DECOMPOSITION_PATTERNS = [
        r"(?:step|phase|stage)\s*\d+",
        r"\d+[.)]\s+\w+",
        r"(?:first|then|next|finally|lastly)[,:]",
        r"[-•*]\s+\w+",
        r"(?:task|subtask|sub-task)\s*\d*[:.]\s*\w+",
    ]

    # Indicators of vague/non-actionable steps
    VAGUE_INDICATORS = [
        "etc", "various", "miscellaneous", "general", "overall",
        "appropriate", "as needed", "if necessary", "possibly",
        "might", "maybe", "could potentially", "consider",
        "high-level", "broadly", "generally speaking",
        "explore options", "look into", "think about",
    ]

    # Action verbs that make steps actionable
    ACTION_VERBS = [
        "create", "build", "implement", "write", "configure",
        "set up", "install", "deploy", "test", "validate",
        "define", "design", "develop", "add", "remove",
        "update", "modify", "fix", "integrate", "connect",
        "display", "show", "render", "format", "parse",
        "fetch", "load", "save", "store", "delete",
        "call", "invoke", "execute", "run", "process",
    ]

    def __init__(
        self,
        min_steps_for_complex: int = 3,
        max_vague_ratio: float = 0.3,
    ):
        self.min_steps_for_complex = min_steps_for_complex
        self.max_vague_ratio = max_vague_ratio

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect poor task decomposition in conversation."""
        import re

        user_turns = [t for t in turns if t.participant_type == "user"]
        agent_turns = [t for t in turns if t.participant_type == "agent"]
        system_turns = [t for t in turns if t.participant_type == "system"]

        # Find the task source (user, system prompt, or first agent)
        task_turns = []
        if user_turns:
            task_turns = user_turns
        elif system_turns and any(len(t.content) > 50 for t in system_turns):
            task_turns = [t for t in system_turns if len(t.content) > 50]
        elif agent_turns:
            task_turns = [agent_turns[0]]

        if not task_turns or not agent_turns:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need task and agent response for decomposition analysis",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # Check if task is complex
        task_content = " ".join([t.content.lower() for t in task_turns])
        is_complex_task = any(
            ind in task_content for ind in self.COMPLEX_TASK_INDICATORS
        )

        # Analyze agent responses for decomposition
        agent_content = " ".join([t.content for t in agent_turns])
        agent_content_lower = agent_content.lower()

        # Check for decomposition patterns
        has_decomposition = any(
            re.search(pattern, agent_content, re.IGNORECASE | re.MULTILINE)
            for pattern in self.DECOMPOSITION_PATTERNS
        )

        # Extract steps if decomposition exists
        steps = self._extract_steps(agent_content)

        # Issue 1: Complex task without decomposition
        if is_complex_task and not has_decomposition:
            issues.append({
                "type": "missing_decomposition",
                "description": "Complex task handled without proper step breakdown",
            })
            for t in task_turns:
                affected_turns.append(t.turn_number)

        # Issue 2: Check for vague steps
        if steps:
            vague_steps = self._find_vague_steps(steps)
            vague_ratio = len(vague_steps) / len(steps) if steps else 0

            if vague_ratio > self.max_vague_ratio:
                issues.append({
                    "type": "vague_subtasks",
                    "vague_count": len(vague_steps),
                    "total_steps": len(steps),
                    "vague_ratio": vague_ratio,
                    "description": f"{len(vague_steps)}/{len(steps)} steps are vague or non-actionable",
                })

        # Issue 3: Check for missing action verbs
        if steps:
            non_actionable = [
                s for s in steps
                if not any(verb in s.lower() for verb in self.ACTION_VERBS)
            ]
            if len(non_actionable) > len(steps) // 2:
                issues.append({
                    "type": "non_actionable_steps",
                    "count": len(non_actionable),
                    "description": f"{len(non_actionable)}/{len(steps)} steps lack clear action verbs",
                })

        # Issue 4: Complex task with too few steps
        if is_complex_task and has_decomposition and len(steps) < self.min_steps_for_complex:
            issues.append({
                "type": "insufficient_decomposition",
                "steps_found": len(steps),
                "min_required": self.min_steps_for_complex,
                "description": f"Complex task has only {len(steps)} steps (minimum {self.min_steps_for_complex} recommended)",
            })

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation=f"Task decomposition appears adequate ({len(steps)} steps found)",
                detector_name=self.name,
            )

        # Determine severity
        if any(i["type"] == "missing_decomposition" for i in issues):
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.15)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F2",
            explanation=f"Task decomposition issues: {len(issues)} problems found",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": issues,
                "is_complex_task": is_complex_task,
                "steps_found": len(steps),
                "has_decomposition": has_decomposition,
            },
            suggested_fix=(
                "Break down complex tasks into clear, actionable steps. "
                "Each step should have a specific action verb and measurable outcome."
            ),
            detector_name=self.name,
        )

    def _extract_steps(self, content: str) -> List[str]:
        """Extract steps/subtasks from agent content."""
        import re
        steps = []

        # Try numbered list first
        numbered = re.findall(r'\d+[.)]\s*([^\n]+)', content)
        if numbered:
            return numbered

        # Try bullet points
        bullets = re.findall(r'[-•*]\s+([^\n]+)', content)
        if bullets:
            return bullets

        # Try step/phase patterns
        step_matches = re.findall(
            r'(?:step|phase|stage)\s*\d*[:.]\s*([^\n]+)',
            content,
            re.IGNORECASE
        )
        if step_matches:
            return step_matches

        return steps

    def _find_vague_steps(self, steps: List[str]) -> List[str]:
        """Find steps that are vague or non-actionable."""
        vague = []
        for step in steps:
            step_lower = step.lower()
            vague_count = sum(1 for ind in self.VAGUE_INDICATORS if ind in step_lower)
            if vague_count >= 1:
                vague.append(step)
            elif len(step.split()) < 3:
                # Very short steps are often vague
                vague.append(step)
        return vague


# ============================================================================
# F10: Communication Breakdown Detector (Turn-Aware)
# ============================================================================

class TurnAwareCommunicationBreakdownDetector(TurnAwareDetector):
    """Detects F10: Communication Breakdown between agents.

    Analyzes inter-agent communication for:
    1. Intent misalignment - sender meant X, receiver understood Y
    2. Format mismatches - expected JSON, got prose
    3. Semantic ambiguity - unclear or ambiguous language
    4. Information loss - key details dropped between agents
    5. Conflicting instructions - contradictory directives

    Particularly important for multi-agent orchestration systems.
    """

    name = "TurnAwareCommunicationBreakdownDetector"
    version = "1.0"
    supported_failure_modes = ["F10"]

    # Intent action verbs for alignment checking
    ACTION_VERBS = [
        "create", "update", "delete", "get", "fetch", "send", "process",
        "analyze", "generate", "search", "find", "calculate", "compare",
        "summarize", "extract", "transform", "validate", "verify",
        "implement", "build", "deploy", "test", "review",
    ]

    # Ambiguous language patterns
    AMBIGUOUS_PATTERNS = [
        (r'\b(it|this|that|these|those)\b(?!\s+(?:is|are|was|were|has|have))', "ambiguous_pronoun"),
        (r'\bsome\s+\w+', "vague_quantifier"),
        (r'\bmaybe|perhaps|possibly|probably\b', "uncertain_language"),
        (r'\betc\.?|and\s+so\s+on|and\s+more\b', "incomplete_enumeration"),
        (r'\bsoon|later|eventually\b', "vague_timeline"),
    ]

    # Misunderstanding indicators
    MISUNDERSTANDING_INDICATORS = [
        "i think you meant", "did you mean", "not sure what",
        "unclear", "confused", "misunderstood", "didn't understand",
        "wrong", "incorrect", "that's not", "actually",
        "let me clarify", "to clarify", "what i meant",
    ]

    # Format expectation keywords
    FORMAT_KEYWORDS = {
        "json": ["json", "object", "dictionary", "{}"],
        "list": ["list", "array", "items", "enumerate"],
        "code": ["code", "implement", "function", "class"],
        "markdown": ["markdown", "formatted", "headers"],
    }

    def __init__(
        self,
        intent_threshold: float = 0.35,
        max_ambiguity_issues: int = 3,
    ):
        self.intent_threshold = intent_threshold
        self.max_ambiguity_issues = max_ambiguity_issues

    def detect(
        self,
        turns: List[TurnSnapshot],
        conversation_metadata: Optional[Dict[str, Any]] = None,
    ) -> TurnAwareDetectionResult:
        """Detect communication breakdowns in multi-turn conversation."""
        import re

        if len(turns) < 2:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.0,
                failure_mode=None,
                explanation="Need at least 2 turns for communication analysis",
                detector_name=self.name,
            )

        issues = []
        affected_turns = []

        # Analyze consecutive turn pairs
        for i in range(len(turns) - 1):
            sender = turns[i]
            receiver = turns[i + 1]

            # Skip if same participant (monologue)
            if sender.participant_id == receiver.participant_id:
                continue

            # Check for misunderstanding indicators
            misunderstanding = self._check_misunderstanding(sender, receiver)
            if misunderstanding:
                issues.append(misunderstanding)
                affected_turns.extend([sender.turn_number, receiver.turn_number])

            # Check intent alignment
            intent_issue = self._check_intent_alignment(sender, receiver)
            if intent_issue:
                issues.append(intent_issue)
                affected_turns.extend([sender.turn_number, receiver.turn_number])

            # Check for format mismatches
            format_issue = self._check_format_compliance(sender, receiver)
            if format_issue:
                issues.append(format_issue)
                affected_turns.extend([sender.turn_number, receiver.turn_number])

        # Check for overall ambiguity in agent messages
        agent_turns = [t for t in turns if t.participant_type == "agent"]
        for turn in agent_turns:
            ambiguity_issues = self._check_ambiguity(turn)
            if len(ambiguity_issues) >= self.max_ambiguity_issues:
                issues.append({
                    "type": "semantic_ambiguity",
                    "turn": turn.turn_number,
                    "issues": ambiguity_issues,
                    "description": f"Turn {turn.turn_number} has {len(ambiguity_issues)} ambiguous language patterns",
                })
                affected_turns.append(turn.turn_number)

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation="Communication appears clear between participants",
                detector_name=self.name,
            )

        # Determine severity
        if any(i["type"] == "intent_mismatch" for i in issues):
            severity = TurnAwareSeverity.SEVERE
        elif any(i["type"] == "explicit_misunderstanding" for i in issues):
            severity = TurnAwareSeverity.MODERATE
        elif len(issues) >= 3:
            severity = TurnAwareSeverity.MODERATE
        else:
            severity = TurnAwareSeverity.MINOR

        confidence = min(0.85, 0.5 + len(issues) * 0.12)

        return TurnAwareDetectionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            failure_mode="F10",
            explanation=f"Communication breakdown: {len(issues)} issues detected",
            affected_turns=list(set(affected_turns)),
            evidence={
                "issues": issues,
                "turn_pairs_analyzed": len(turns) - 1,
            },
            suggested_fix=(
                "Improve communication clarity: 1) Use explicit references instead of pronouns, "
                "2) Specify expected formats clearly, 3) Confirm understanding before proceeding."
            ),
            detector_name=self.name,
        )

    def _check_misunderstanding(
        self,
        sender: TurnSnapshot,
        receiver: TurnSnapshot,
    ) -> Optional[dict]:
        """Check for explicit misunderstanding indicators."""
        receiver_lower = receiver.content.lower()

        for indicator in self.MISUNDERSTANDING_INDICATORS:
            if indicator in receiver_lower:
                return {
                    "type": "explicit_misunderstanding",
                    "indicator": indicator,
                    "sender_turn": sender.turn_number,
                    "receiver_turn": receiver.turn_number,
                    "description": f"Explicit misunderstanding detected: '{indicator}'",
                }
        return None

    def _check_intent_alignment(
        self,
        sender: TurnSnapshot,
        receiver: TurnSnapshot,
    ) -> Optional[dict]:
        """Check if receiver's response aligns with sender's intent."""
        sender_words = set(sender.content.lower().split())
        receiver_words = set(receiver.content.lower().split())

        # Extract actions from both
        sender_actions = sender_words & set(self.ACTION_VERBS)
        receiver_actions = receiver_words & set(self.ACTION_VERBS)

        if not sender_actions:
            # No clear action requested
            return None

        # Check if receiver addressed the requested actions
        action_match = len(sender_actions & receiver_actions) / len(sender_actions)

        # Check for negative indicators (errors, refusals)
        negative_indicators = {"error", "failed", "cannot", "unable", "refused", "sorry", "can't"}
        has_negative = bool(receiver_words & negative_indicators)

        if action_match < self.intent_threshold and not has_negative:
            return {
                "type": "intent_mismatch",
                "sender_turn": sender.turn_number,
                "receiver_turn": receiver.turn_number,
                "alignment_score": action_match,
                "requested_actions": list(sender_actions),
                "addressed_actions": list(receiver_actions),
                "description": f"Response doesn't address requested actions ({action_match:.0%} alignment)",
            }
        return None

    def _check_format_compliance(
        self,
        sender: TurnSnapshot,
        receiver: TurnSnapshot,
    ) -> Optional[dict]:
        """Check if receiver followed expected format."""
        import json as json_lib

        sender_lower = sender.content.lower()
        expected_format = None

        # Detect expected format from sender's message
        for fmt, keywords in self.FORMAT_KEYWORDS.items():
            if any(kw in sender_lower for kw in keywords):
                expected_format = fmt
                break

        if not expected_format:
            return None

        # Check if receiver complied
        receiver_content = receiver.content

        if expected_format == "json":
            try:
                json_lib.loads(receiver_content)
                return None  # Valid JSON
            except:
                # Check for embedded JSON
                import re
                if re.search(r'\{[^{}]+\}', receiver_content):
                    return None  # Has JSON-like content
                return {
                    "type": "format_mismatch",
                    "expected": "json",
                    "sender_turn": sender.turn_number,
                    "receiver_turn": receiver.turn_number,
                    "description": "Expected JSON format but received prose",
                }

        elif expected_format == "code":
            if "```" in receiver_content or "def " in receiver_content or "class " in receiver_content:
                return None  # Has code
            return {
                "type": "format_mismatch",
                "expected": "code",
                "sender_turn": sender.turn_number,
                "receiver_turn": receiver.turn_number,
                "description": "Expected code format but received prose",
            }

        return None

    def _check_ambiguity(self, turn: TurnSnapshot) -> List[str]:
        """Check for ambiguous language in a turn."""
        import re
        issues = []

        for pattern, issue_type in self.AMBIGUOUS_PATTERNS:
            if re.search(pattern, turn.content, re.IGNORECASE):
                issues.append(issue_type)

        return issues
