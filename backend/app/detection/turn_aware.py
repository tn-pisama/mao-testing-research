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

    # Resource complaint indicators
    RESOURCE_COMPLAINTS = [
        "don't have access", "no access to", "cannot access",
        "missing", "not available", "unavailable",
        "need permission", "not authorized", "access denied",
        "tool not found", "function not", "api error",
        "unable to", "can't find", "doesn't exist",
        "no such", "not installed", "import error",
    ]

    # Capability mismatch indicators
    CAPABILITY_MISMATCH = [
        "not my expertise", "outside my scope", "not qualified",
        "don't know how to", "unfamiliar with", "not trained",
        "beyond my capabilities", "can't do that", "not designed for",
        "wrong agent", "should be handled by", "need specialist",
    ]

    # Overload indicators
    OVERLOAD_INDICATORS = [
        "too many tasks", "overloaded", "too much work",
        "overwhelmed", "can't handle all", "backed up",
        "queue is full", "rate limit", "throttled",
        "timeout", "timed out", "slow response",
    ]

    def __init__(
        self,
        min_turns: int = 2,
    ):
        self.min_turns = min_turns

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

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation="No resource misallocation detected",
                detector_name=self.name,
            )

        # Severity based on issue count and types
        if len(issues) >= 3 or any(i["type"] == "tool_failure" for i in issues):
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
        failure_indicators = [
            "error", "failed", "exception", "traceback",
            "404", "500", "401", "403", "timeout",
            "connection refused", "not found", "invalid",
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

        # If one agent has 3x+ more turns than another
        if max_count >= 3 * min_count and max_count >= 4:
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


class TurnAwareInformationWithholdingDetector(TurnAwareDetector):
    """Detects F8: Information Withholding in conversations.

    Analyzes whether agents properly share information:
    1. Unanswered questions - agent asks but gets no answer
    2. Missing context - agent responds without using provided info
    3. Incomplete sharing - partial information provided
    4. Ignored requests - explicit requests for info not addressed

    F8 has 18% prevalence in MAST.
    """

    name = "TurnAwareInformationWithholdingDetector"
    version = "1.0"
    supported_failure_modes = ["F8"]

    # Question indicators
    QUESTION_PATTERNS = [
        "?", "what is", "how do", "can you", "could you",
        "please provide", "please share", "need to know",
        "tell me", "explain", "clarify", "which",
    ]

    # Withholding indicators in responses
    WITHHOLDING_INDICATORS = [
        "can't share", "cannot disclose", "not allowed to",
        "confidential", "private", "restricted",
        "don't have that", "no information", "unknown",
        "not sure", "i don't know", "unclear",
    ]

    # Missing context indicators
    MISSING_CONTEXT = [
        "what do you mean", "more context", "be more specific",
        "unclear what", "don't understand", "confused about",
        "missing information", "need more details", "incomplete",
    ]

    def __init__(
        self,
        min_turns: int = 3,
    ):
        self.min_turns = min_turns

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

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation="No information withholding detected",
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
        """Detect questions that weren't answered."""
        issues = []
        for i, turn in enumerate(turns[:-1]):
            content = turn.content
            # Check if this turn contains a question
            if "?" in content:
                # Look at next 2 turns for an answer
                answered = False
                for j in range(i + 1, min(i + 3, len(turns))):
                    next_turn = turns[j]
                    # Different participant responding
                    if next_turn.participant_id != turn.participant_id:
                        # Check if response is substantive (not just acknowledgment)
                        if len(next_turn.content) > 50:
                            answered = True
                            break
                if not answered:
                    issues.append({
                        "type": "unanswered_question",
                        "turns": [turn.turn_number],
                        "description": "Question appears unanswered",
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


class TurnAwareOutputValidationDetector(TurnAwareDetector):
    """Detects F12: Output Validation Failure in conversations.

    Analyzes whether agent outputs are properly validated:
    1. Missing validation - outputs produced without checking
    2. Failed validation - validation ran but output doesn't pass
    3. Uncaught errors - errors in output that weren't caught
    4. Format issues - output doesn't match expected format
    5. Incomplete output - missing required components

    F12 has 17% prevalence in MAST.
    """

    name = "TurnAwareOutputValidationDetector"
    version = "1.0"
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

    def __init__(self, min_turns: int = 2):
        self.min_turns = min_turns

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

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation="No output validation failures detected",
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


class TurnAwareQualityGateBypassDetector(TurnAwareDetector):
    """Detects F13: Quality Gate Bypass in conversations.

    Analyzes whether quality checks are properly followed:
    1. Skipped reviews - code review or QA steps skipped
    2. Ignored warnings - warnings present but ignored
    3. Bypassed checks - explicitly skipping quality gates
    4. Missing tests - no testing before deployment/completion
    5. Rush to completion - moving forward despite issues

    F13 has 17% prevalence in MAST.
    """

    name = "TurnAwareQualityGateBypassDetector"
    version = "1.0"
    supported_failure_modes = ["F13"]

    # Bypass indicators
    BYPASS_INDICATORS = [
        "skip the", "let's skip", "skipping", "bypass",
        "ignore the", "ignoring", "don't need to",
        "no need to test", "skip testing", "skip review",
        "good enough", "ship it", "move on",
        "later", "we can fix later", "TODO", "FIXME",
    ]

    # Warning ignore indicators
    WARNING_IGNORES = [
        "ignore warning", "suppress warning", "disable warning",
        "warning ignored", "warnings disabled", "lint disable",
        "noqa", "pylint: disable", "eslint-disable",
        "despite warning", "warning but", "@suppress",
    ]

    # Missing quality steps
    MISSING_QUALITY = [
        "no tests", "without testing", "untested",
        "no review", "without review", "unreviewed",
        "no qa", "skip qa", "no quality",
        "didn't test", "haven't tested", "not tested",
    ]

    # Rush indicators
    RUSH_INDICATORS = [
        "quick and dirty", "just ship", "good for now",
        "will fix later", "temporary", "hack",
        "workaround", "shortcut", "quick fix",
        "time constraint", "deadline", "rush",
    ]

    def __init__(self, min_turns: int = 2):
        self.min_turns = min_turns

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

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation="No quality gate bypass detected",
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
        """Detect explicit bypass of quality gates."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.BYPASS_INDICATORS:
                if indicator in content_lower:
                    issues.append({
                        "type": "bypass",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Quality bypass: '{indicator}'",
                    })
                    break
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
        """Detect missing quality steps."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.MISSING_QUALITY:
                if indicator in content_lower:
                    issues.append({
                        "type": "missing_quality",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Missing quality: '{indicator}'",
                    })
                    break
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


class TurnAwareCompletionMisjudgmentDetector(TurnAwareDetector):
    """Detects F14: Completion Misjudgment in conversations.

    Analyzes whether task completion is correctly assessed:
    1. Premature completion - declaring done when not finished
    2. Incomplete requirements - not all requirements addressed
    3. Unfinished work - obvious gaps in deliverables
    4. False success claims - claiming success despite failures
    5. Missed acceptance criteria - not meeting stated criteria

    F14 has 23% prevalence in MAST.
    """

    name = "TurnAwareCompletionMisjudgmentDetector"
    version = "1.0"
    supported_failure_modes = ["F14"]

    # Premature completion indicators
    PREMATURE_COMPLETION = [
        "done", "completed", "finished", "all done",
        "task complete", "mission accomplished", "that's it",
        "here you go", "here's the result", "final version",
    ]

    # Incomplete indicators following completion
    INCOMPLETE_INDICATORS = [
        "but", "however", "except", "still need",
        "remaining", "left to do", "not yet",
        "missing", "incomplete", "partial",
        "TODO", "FIXME", "TBD", "WIP",
        "placeholder", "stub", "mock",
    ]

    # False success indicators
    FALSE_SUCCESS = [
        "should work", "might work", "probably works",
        "seems to work", "appears to", "looks like it",
        "assuming", "hopefully", "fingers crossed",
        "not sure if", "haven't verified", "untested",
    ]

    # Continuation needed indicators
    CONTINUATION_NEEDED = [
        "next step", "then we need", "after that",
        "following that", "additionally", "also need",
        "don't forget", "remember to", "make sure to",
        "still need to", "have to also", "need to also",
    ]

    def __init__(self, min_turns: int = 2):
        self.min_turns = min_turns

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

        if not issues:
            return TurnAwareDetectionResult(
                detected=False,
                severity=TurnAwareSeverity.NONE,
                confidence=0.8,
                failure_mode=None,
                explanation="No completion misjudgment detected",
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
        """Detect uncertain success claims."""
        issues = []
        for turn in turns:
            content_lower = turn.content.lower()
            for indicator in self.FALSE_SUCCESS:
                if indicator in content_lower:
                    issues.append({
                        "type": "false_success",
                        "turns": [turn.turn_number],
                        "indicator": indicator,
                        "description": f"Uncertain success: '{indicator}'",
                    })
                    break
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


class TurnAwareTerminationAwarenessDetector(TurnAwareDetector):
    """Detects FM-1.5: Unaware of Termination Conditions.

    Based on MAST research (NeurIPS 2025): This is the highest-prevalence
    failure mode in FC1 (40% of system design failures).

    Detects:
    1. Missing termination signals in long conversations
    2. Continuation after explicit termination
    3. Repeated completion claims without actual completion
    4. Infinite processing without progress indicators

    Reference: https://arxiv.org/abs/2503.13657
    """

    name = "TurnAwareTerminationAwarenessDetector"
    version = "1.0"
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
            TurnAwareResourceMisallocationDetector(),  # F3
            TurnAwareLoopDetector(),  # F5
            TurnAwareDerailmentDetector(),  # F6
            TurnAwareContextNeglectDetector(),  # F7
            TurnAwareInformationWithholdingDetector(),  # F8
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
