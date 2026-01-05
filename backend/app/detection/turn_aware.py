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
MODULE_VERSION = "1.0"


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


class TurnAwareContextNeglectDetector(TurnAwareDetector):
    """Detects F7: Context Neglect across conversation turns.

    Analyzes whether agents properly utilize context from:
    1. Previous turns in the conversation
    2. User instructions and requirements
    3. Tool/system outputs

    Uses accumulated context tracking to detect when information
    is "lost" or ignored as the conversation progresses.

    Tuned to reduce false positives:
    - Code responses have different vocabulary than questions
    - Low word overlap doesn't mean neglect if topic is addressed
    - Repetition is F5's job, not context neglect
    """

    name = "TurnAwareContextNeglectDetector"
    version = "1.1"  # Version bump for tuning
    supported_failure_modes = ["F7"]

    # Code patterns that indicate a code response
    CODE_PATTERNS = [
        "def ", "class ", "import ", "from ", "function ",
        "const ", "let ", "var ", "return ", "if (", "if(",
        "for (", "for(", "while ", "=>", "```", "{", "}",
        "self.", "this.", "async ", "await ",
    ]

    # Explicit neglect indicators - agent explicitly ignoring or misunderstanding
    NEGLECT_INDICATORS = [
        "instead", "rather than", "not what you asked",
        "different topic", "unrelated", "i'll analyze",
        "let me look at", "i'll check",
    ]

    def __init__(
        self,
        utilization_threshold: float = 0.1,  # Lowered from 0.3
        min_context_length: int = 50,
        check_user_instructions: bool = True,
        check_tool_outputs: bool = True,
        require_explicit_neglect: bool = True,  # New: require stronger evidence
    ):
        self.utilization_threshold = utilization_threshold
        self.min_context_length = min_context_length
        self.check_user_instructions = check_user_instructions
        self.check_tool_outputs = check_tool_outputs
        self.require_explicit_neglect = require_explicit_neglect

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

        neglect_issues = []
        affected_turns = []

        # Check 1: Agent responses vs user instructions
        if self.check_user_instructions and user_turns and agent_turns:
            for agent_turn in agent_turns:
                # Find the most recent user turn before this agent turn
                prior_user_turns = [
                    u for u in user_turns
                    if u.turn_number < agent_turn.turn_number
                ]
                if not prior_user_turns:
                    continue

                # Get the immediately preceding user turn for comparison
                immediate_user = max(prior_user_turns, key=lambda u: u.turn_number)
                user_context = immediate_user.content

                # Skip if agent response is code and user asked for code
                if self._is_code_response(agent_turn.content):
                    if self._is_code_request(user_context):
                        continue  # Code response to code request = OK

                # Check for explicit neglect patterns
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
                    # Only check utilization if not requiring explicit neglect
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

        if not neglect_issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.9,
                failure_mode=None,
                explanation="Agent properly utilized context across all turns",
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
        topic_indicators = {
            "sales", "data", "analysis", "report", "weather", "temperature",
            "calculator", "function", "code", "implementation", "database",
            "user", "authentication", "api", "server", "client", "file",
            "error", "bug", "test", "performance", "security", "config",
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
        """Compute how much of the context is reflected in the output."""
        context_words = set(w.lower() for w in context.split() if len(w) > 3)
        output_words = set(w.lower() for w in output.split() if len(w) > 3)

        if not context_words:
            return 1.0

        overlap = context_words & output_words
        return len(overlap) / len(context_words)


class TurnAwareDerailmentDetector(TurnAwareDetector):
    """Detects F6: Task Derailment across conversation turns.

    Tracks topic consistency and task focus across the conversation,
    detecting when:
    1. Agent responses drift from the original task
    2. Conversation topic changes unexpectedly
    3. Agent addresses wrong task or substitutes tasks

    Uses sliding window analysis to detect gradual drift.

    Tuned to reduce false positives:
    - Code responses have different vocabulary than task descriptions
    - Requires stronger evidence (task substitution OR progressive drift)
    - Single-turn drift alone is not sufficient
    """

    name = "TurnAwareDerailmentDetector"
    version = "1.1"  # Version bump for tuning
    supported_failure_modes = ["F6"]

    # Code patterns (shared with F7 detector logic)
    CODE_PATTERNS = [
        "def ", "class ", "import ", "from ", "function ",
        "const ", "let ", "var ", "return ", "if (", "if(",
        "for (", "for(", "while ", "=>", "```", "{", "}",
        "self.", "this.", "async ", "await ",
    ]

    def __init__(
        self,
        drift_threshold: float = 0.75,  # Raised from 0.5 to reduce FPs
        min_turns_for_analysis: int = 3,
        window_size: int = 5,
        require_strong_evidence: bool = True,  # New: require multiple signals
    ):
        self.drift_threshold = drift_threshold
        self.min_turns_for_analysis = min_turns_for_analysis
        self.window_size = window_size
        self.require_strong_evidence = require_strong_evidence
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

        # Handle multi-agent systems where all participants are "agent" role
        # (e.g., ChatDev where CEO gives task to Programmer)
        if not user_turns and agent_turns:
            # Treat first agent as task-giver, rest as executors
            initial_task = agent_turns[0].content
            agent_turns = agent_turns[1:]  # Remaining agents to check for derailment
        elif user_turns and agent_turns:
            initial_task = user_turns[0].content
        else:
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

        # Check each agent response for task alignment
        for agent_turn in agent_turns:
            # Skip drift check for code responses to code tasks
            if is_code_task and self._is_code_response(agent_turn.content):
                continue  # Code response to code task - don't flag as drift

            drift_score, coverage = self._compute_topic_drift(
                initial_task, agent_turn.content
            )

            if drift_score > self.drift_threshold:
                high_drift_count += 1
                # Only add as issue if NOT requiring strong evidence
                # OR if we have multiple high-drift turns
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
        progressive_drift = {"detected": False}
        if len(agent_turns) >= 3:
            progressive_drift = self._detect_progressive_drift(
                initial_task, agent_turns, is_code_task
            )
            if progressive_drift["detected"]:
                derailment_issues.append({
                    "type": "progressive_drift",
                    "turn": progressive_drift["worst_turn"],
                    "description": "Agent responses progressively drifting from task",
                    "drift_progression": progressive_drift["drift_scores"],
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
    ) -> tuple:
        """Compute topic drift and task coverage.

        Returns:
            (drift_score, coverage) tuple
        """
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
        """Detect if agent responses are progressively drifting."""
        drift_scores = []

        for turn in agent_turns:
            # Skip code responses for code tasks
            if is_code_task and self._is_code_response(turn.content):
                continue

            drift, _ = self._compute_topic_drift(initial_task, turn.content)
            drift_scores.append({
                "turn": turn.turn_number,
                "drift": drift,
            })

        # Check if drift is increasing
        if len(drift_scores) >= 3:
            scores = [d["drift"] for d in drift_scores]
            # Simple trend detection: is later half worse than first half?
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
                }

        return {"detected": False}

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


class TurnAwareLoopDetector(TurnAwareDetector):
    """Detects F5: Infinite Loop / Repetitive Behavior across conversation turns.

    Analyzes conversation for:
    1. Repetitive agent responses
    2. Cyclic conversation patterns
    3. Stuck loops where same content repeats
    """

    name = "TurnAwareLoopDetector"
    version = "1.0"
    supported_failure_modes = ["F5"]

    def __init__(
        self,
        repetition_threshold: float = 0.9,
        min_repetitions: int = 2,
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


class TurnAwareSpecificationMismatchDetector(TurnAwareDetector):
    """Detects F1: Specification Mismatch in conversations.

    Analyzes whether agent outputs match the user's requirements:
    1. Missing required features - user asked for X but agent didn't provide
    2. Extra unrequested features - agent added things user didn't ask for
    3. Misinterpreted requirements - agent did something different than asked
    4. Incomplete implementation - partial fulfillment of requirements

    This is the 3rd most common failure mode in MAST (30% prevalence).
    """

    name = "TurnAwareSpecificationMismatchDetector"
    version = "1.0"
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
        coverage_threshold: float = 0.4,
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

        if not user_turns or not agent_turns:
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

        # Extract requirements from user turns
        requirements = self._extract_requirements(user_turns)

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
        agent_content = " ".join([t.content for t in agent_turns])

        # 1. Check requirement coverage
        coverage_result = self._check_coverage(requirements, agent_content)
        if coverage_result["uncovered"]:
            issues.append({
                "type": "missing_requirements",
                "uncovered": coverage_result["uncovered"][:5],
                "coverage_ratio": coverage_result["coverage"],
                "description": f"Missing requirements: {', '.join(coverage_result['uncovered'][:3])}",
            })
            for ut in user_turns:
                affected_turns.append(ut.turn_number)

        # 2. Check for explicit mismatch indicators
        mismatch_issues = self._check_mismatch_indicators(agent_turns)
        issues.extend(mismatch_issues)
        for issue in mismatch_issues:
            affected_turns.extend(issue.get("turns", []))

        # 3. Check for scope creep (unrequested additions)
        scope_issues = self._check_scope_creep(user_turns, agent_turns)
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

    def _check_coverage(self, requirements: set, agent_content: str) -> dict:
        """Check how many requirements are addressed in agent output."""
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
        }

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

    # Conflict indicators - words suggesting disagreement or contradiction
    CONFLICT_INDICATORS = [
        "instead", "rather", "however", "but actually", "not correct",
        "wrong", "mistake", "error", "should not", "shouldn't",
        "incorrect", "that's not", "actually", "no,", "wait,",
        "let me correct", "correction", "fix that", "redo",
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
        redundancy_threshold: float = 0.3,
    ):
        self.min_agents = min_agents
        self.conflict_threshold = conflict_threshold
        self.redundancy_threshold = redundancy_threshold

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

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.85,
                failure_mode=None,
                explanation="No coordination failures detected",
                detector_name=self.name,
            )

        # Determine severity based on number and type of issues
        if len(issues) >= 3 or any(i["type"] == "conflict" for i in issues):
            severity = TurnAwareSeverity.SEVERE
        elif len(issues) >= 2:
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
            TurnAwareLoopDetector(),  # F5
            TurnAwareDerailmentDetector(),  # F6
            TurnAwareContextNeglectDetector(),  # F7
            TurnAwareCoordinationFailureDetector(),  # F11
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
