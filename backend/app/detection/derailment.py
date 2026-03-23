"""
F6: Task Derailment Detection (MAST Taxonomy)
=============================================

Detects when an agent goes off-topic or deviates from the assigned task.
One of the most common failures (7.4% in MAST-Data).

Detection Methods:
1. Semantic similarity between task and output
2. Topic drift via embedding distance
3. Keyword extraction and matching
4. Task coverage verification (v1.1+)

Version History:
- v1.0: Initial implementation with Jaccard similarity and topic drift
- v1.1: Added task coverage check to reduce over-detection on helpful expansions
- v1.2: Fixed remaining edge cases:
  - Added related topic recognition (review->style issues is OK)
  - Added task substitution detection (authentication vs authorization)
- v1.3: Improved task substitution with semantic clusters
  - Counts related terms to determine actual focus
  - E.g., "access control", "permissions", "roles" indicate authorization focus
- v1.4: Fixed remaining Phase 2 adversarial cases:
  - Better documentation detection (API docs with examples = still docs)
  - Focus mismatch detection for research tasks (pricing vs features)
  - Content-type matching for writing tasks
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
import numpy as np

logger = logging.getLogger(__name__)

# Detector version for tracking
DETECTOR_VERSION = "1.5"
DETECTOR_NAME = "TaskDerailmentDetector"

# v1.3: Semantic clusters for related task concepts
# Each cluster maps a concept to related terms that indicate focus on that concept
TASK_CLUSTERS = {
    "authentication": ["authenticate", "login", "password", "credential", "identity", "sign in", "sign-in", "logged in"],
    "authorization": ["authorize", "permission", "access control", "role", "rbac", "acl", "privilege", "allowed"],
    "encrypt": ["encrypt", "encryption", "cipher", "encode"],
    "decrypt": ["decrypt", "decryption", "decipher", "decode"],
    "upload": ["upload", "uploading", "send file", "put file"],
    "download": ["download", "downloading", "get file", "fetch file"],
    "create": ["create", "creating", "add new", "insert", "generate"],
    "delete": ["delete", "deleting", "remove", "drop", "destroy"],
    "frontend": ["frontend", "front-end", "ui", "user interface", "client-side", "react", "vue", "angular"],
    "backend": ["backend", "back-end", "server-side", "api", "database", "server"],
    "unit test": ["unit test", "unit testing", "isolated test", "mock"],
    "integration test": ["integration test", "integration testing", "e2e", "end-to-end"],
}

# v1.3: Substitution pairs map task concept to commonly confused concept
SUBSTITUTION_PAIRS = [
    ("authentication", "authorization"),
    ("authorization", "authentication"),
    ("encrypt", "decrypt"),
    ("decrypt", "encrypt"),
    ("upload", "download"),
    ("download", "upload"),
    ("create", "delete"),
    ("delete", "create"),
    ("frontend", "backend"),
    ("backend", "frontend"),
    ("unit test", "integration test"),
    ("integration test", "unit test"),
]

# v1.4: Research/analysis focus terms - what the task asks for vs what might be delivered
RESEARCH_FOCUS_CLUSTERS = {
    "pricing": ["price", "pricing", "cost", "rate", "fee", "subscription", "tier", "plan", "dollar", "$", "budget", "expense"],
    "features": ["feature", "functionality", "capability", "function", "tool", "option", "integration"],
    "market": ["market", "positioning", "segment", "target", "audience", "demographic"],
    "technical": ["technical", "architecture", "stack", "technology", "infrastructure", "performance"],
    "competitor": ["competitor", "competition", "rival", "alternative", "versus", "vs"],
    "strategy": ["strategy", "strategic", "approach", "roadmap", "vision", "plan"],
}

# v1.4: Content-type patterns for writing tasks
CONTENT_TYPE_PATTERNS = {
    "documentation": ["#", "##", "###", "overview", "guide", "reference", "api", "endpoint", "parameter", "return", "example", "usage", "method", "function"],
    "report": ["summary", "findings", "analysis", "conclusion", "recommendation", "result", "data", "metric"],
    "code": ["def ", "function ", "class ", "import ", "const ", "let ", "var ", "return ", "if ", "for ", "while "],
}

# v1.5: Framework-specific benign patterns
# These patterns are common in multi-agent frameworks and should not be flagged
FRAMEWORK_BENIGN_PATTERNS = {
    "AG2": [
        r"\b(?:tool_code|tool_result|human_input)\b",
        r"\b(?:terminate|TERMINATE)\b",  # AG2 termination signal
        r"\b(?:groupchat|speaker_selection)\b",
        r"\b(?:UserProxy|AssistantAgent|ConversableAgent)\b",
    ],
    "MetaGPT": [
        r"\b(?:ProductManager|Architect|ProjectManager|Engineer|QAEngineer)\b",
        r"\b(?:WriteDesign|WritePRD|WriteCode|WriteTest)\b",
        r"\b(?:Message|ActionOutput|RoleReactMode)\b",
        r"\b(?:memory|working_memory|recovered)\b",
    ],
    "ChatDev": [
        r"\b(?:CEO|CTO|CPO|Programmer|Reviewer|Designer|Tester)\b",
        r"\b(?:PhaseType|ChatChain|RolePlay)\b",
        r"\b(?:software_info|chat_env)\b",
    ],
    "Camel": [
        r"\b(?:AI_USER|AI_ASSISTANT|TASK_SPECIFIER)\b",
        r"\b(?:role_playing|inception_prompt)\b",
        r"\b(?:SystemMessage|ChatMessage)\b",
    ],
    "LangGraph": [
        r"\b(?:StateGraph|MessageGraph|CompiledGraph)\b",
        r"\b(?:add_node|add_edge|add_conditional_edges)\b",
        r"\b(?:START|END|should_continue)\b",
    ],
    "CrewAI": [
        r"\b(?:Agent|Task|Crew|Process)\b",
        r"\b(?:backstory|goal|expected_output)\b",
        r"\b(?:sequential|hierarchical)\b",
    ],
}

# v1.5: Common agent coordination patterns (benign)
COORDINATION_PATTERNS = [
    r"\b(?:delegating to|handing off to|passing to|coordinating with)\b",
    r"\b(?:agent \d+|step \d+|phase \d+)\b",
    r"\b(?:my role|my task|assigned to me)\b",
    r"\b(?:waiting for|blocked on|depends on)\b",
    r"\b(?:reporting back|returning result|providing feedback)\b",
]


class DerailmentSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass
class DerailmentResult:
    detected: bool
    severity: DerailmentSeverity
    confidence: float
    task_output_similarity: float
    topic_drift_score: float
    explanation: str
    suggested_fix: Optional[str] = None
    raw_score: Optional[float] = None
    evidence: Optional[dict] = None
    task_coverage: float = 0.0  # v1.1: How much of the task is addressed
    version: str = DETECTOR_VERSION


class TaskDerailmentDetector:
    """
    Detects F6: Task Derailment - when an agent goes off-topic.
    
    Uses semantic similarity and topic modeling to detect drift
    between the assigned task and the agent's output.
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.3,
        drift_threshold: float = 0.5,
        min_output_length: int = 20,
        confidence_scaling: float = 1.0,
        task_coverage_threshold: float = 0.6,  # Raised from 0.5 — require stronger task coverage to avoid FNs on hard cases
        framework: Optional[str] = None,  # v1.5: Framework for benign pattern matching
    ):
        self.similarity_threshold = similarity_threshold
        self.drift_threshold = drift_threshold
        self.min_output_length = min_output_length
        self.confidence_scaling = confidence_scaling
        self.task_coverage_threshold = task_coverage_threshold
        self.framework = framework
        self._embedder = None
    
    def _calibrate_confidence(
        self,
        similarity: float,
        drift_score: float,
        severity: DerailmentSeverity,
        output_length: int,
    ) -> float:
        """Calibrate confidence based on evidence strength."""
        severity_weight = {
            DerailmentSeverity.NONE: 0.0,
            DerailmentSeverity.MINOR: 0.6,
            DerailmentSeverity.MODERATE: 0.75,
            DerailmentSeverity.SEVERE: 0.9,
        }.get(severity, 0.5)
        
        length_factor = min(1.0, output_length / 200)
        signal_strength = (drift_score + (1 - similarity)) / 2
        
        base_confidence = severity_weight * 0.4 + signal_strength * 0.4 + length_factor * 0.2
        calibrated = min(0.99, base_confidence * self.confidence_scaling)
        
        return round(calibrated, 4)

    def _get_embedder(self):
        if self._embedder is None:
            try:
                from app.core.embeddings import get_embedder
                self._embedder = get_embedder()
            except ImportError:
                logger.warning("EmbeddingService not available, using fallback")
                self._embedder = "fallback"
        return self._embedder

    def _has_framework_benign_pattern(self, text: str) -> bool:
        """
        v1.5: Check if text contains framework-specific benign patterns.

        Multi-agent frameworks often have coordination messages that may
        look like derailment but are actually normal operation.
        """
        import re

        # Check framework-specific patterns
        if self.framework and self.framework in FRAMEWORK_BENIGN_PATTERNS:
            for pattern in FRAMEWORK_BENIGN_PATTERNS[self.framework]:
                if re.search(pattern, text, re.IGNORECASE):
                    return True

        # Check general coordination patterns
        for pattern in COORDINATION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _compute_similarity(self, text1: str, text2: str) -> float:
        embedder = self._get_embedder()
        
        if embedder == "fallback":
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            intersection = words1 & words2
            union = words1 | words2
            return len(intersection) / len(union)
        
        try:
            embeddings = embedder.encode([text1, text2])
            return embedder.similarity(embeddings[0], embeddings[1])
        except Exception as e:
            logger.warning(f"Embedding failed, using fallback: {e}")
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0.0
            return len(words1 & words2) / len(words1 | words2)

    def _extract_key_terms(self, text: str) -> set[str]:
        words = text.lower().split()
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "under", "again", "further", "then", "once",
            "and", "but", "or", "nor", "so", "yet", "both", "either",
            "neither", "not", "only", "own", "same", "than", "too", "very",
            "just", "can", "don", "now", "it", "its", "this", "that",
        }
        return {w for w in words if len(w) > 2 and w not in stopwords}

    def _compute_topic_drift(
        self,
        task: str,
        output: str,
        context: Optional[str] = None,
    ) -> tuple[float, float]:
        """Compute topic drift and task coverage.

        Returns:
            tuple: (drift_score, task_coverage)
        """
        task_terms = self._extract_key_terms(task)
        output_terms = self._extract_key_terms(output)

        if not task_terms:
            return 0.0, 1.0

        overlap = task_terms & output_terms
        coverage = len(overlap) / len(task_terms)

        if context:
            context_terms = self._extract_key_terms(context)
            new_terms = output_terms - task_terms - context_terms
            novelty_ratio = len(new_terms) / max(len(output_terms), 1)
        else:
            new_terms = output_terms - task_terms
            novelty_ratio = len(new_terms) / max(len(output_terms), 1)

        drift_score = (1 - coverage) * 0.6 + novelty_ratio * 0.4
        return min(drift_score, 1.0), coverage

    def _count_cluster_matches(self, text: str, concept: str) -> int:
        """Count how many terms from a concept's cluster appear in text."""
        if concept not in TASK_CLUSTERS:
            return 1 if concept in text else 0

        count = 0
        text_lower = text.lower()
        for term in TASK_CLUSTERS[concept]:
            if term in text_lower:
                count += 1
        # Also count the concept itself
        if concept in text_lower:
            count += 1
        return count

    def _count_focus_matches(self, text: str, focus: str) -> int:
        """v1.4: Count matches for a research focus cluster."""
        if focus not in RESEARCH_FOCUS_CLUSTERS:
            return 1 if focus in text.lower() else 0

        count = 0
        text_lower = text.lower()
        for term in RESEARCH_FOCUS_CLUSTERS[focus]:
            if term in text_lower:
                count += 1
        return count

    def _detect_research_focus_mismatch(
        self,
        task: str,
        output: str,
    ) -> tuple[bool, Optional[str]]:
        """v1.4: Detect when research/analysis focuses on wrong aspect.

        E.g., task asks for "pricing" research but output focuses on "features".
        """
        task_lower = task.lower()
        output_lower = output.lower()

        # Check for research/analysis tasks
        research_indicators = ["research", "analyze", "analysis", "study", "investigate", "examine", "evaluate"]
        is_research_task = any(ind in task_lower for ind in research_indicators)

        if not is_research_task:
            return False, None

        # Find requested focus in task
        requested_focus = None
        for focus in RESEARCH_FOCUS_CLUSTERS.keys():
            if focus in task_lower:
                requested_focus = focus
                break

        if not requested_focus:
            return False, None

        # Count matches for each focus in output
        focus_counts = {}
        for focus in RESEARCH_FOCUS_CLUSTERS.keys():
            focus_counts[focus] = self._count_focus_matches(output_lower, focus)

        requested_count = focus_counts.get(requested_focus, 0)

        # Find if another focus dominates
        for other_focus, other_count in focus_counts.items():
            if other_focus != requested_focus and other_count >= 2 and other_count > requested_count * 1.5:  # Lowered from 3/2x to 2/1.5x
                return True, (
                    f"Task asks for '{requested_focus}' research but output focuses on "
                    f"'{other_focus}' ({other_count} matches vs {requested_count} for {requested_focus})"
                )

        return False, None

    def _matches_content_type(self, output: str, content_type: str) -> bool:
        """v1.4: Check if output matches the expected content type."""
        if content_type not in CONTENT_TYPE_PATTERNS:
            return False

        patterns = CONTENT_TYPE_PATTERNS[content_type]
        output_lower = output.lower()

        # Count how many patterns match
        matches = sum(1 for p in patterns if p.lower() in output_lower)

        # Need at least 3 matches to confirm content type
        return matches >= 3

    def _is_writing_task(self, task: str) -> tuple[bool, Optional[str]]:
        """v1.4: Check if task is a writing task and identify expected content type."""
        task_lower = task.lower()

        writing_indicators = {
            "documentation": ["write documentation", "create documentation", "document", "api documentation", "write docs"],
            "report": ["write report", "create report", "prepare report", "generate report"],
            "code": ["write code", "create code", "implement", "develop", "build"],
        }

        for content_type, indicators in writing_indicators.items():
            if any(ind in task_lower for ind in indicators):
                return True, content_type

        return False, None

    def _detect_task_substitution(
        self,
        task: str,
        output: str,
    ) -> tuple[bool, Optional[str]]:
        """Detect if the output addresses a different but related task.

        v1.3: Uses semantic clusters to detect when output focuses on
        a related but different concept than what the task requested.
        E.g., tests authorization (permissions, roles) when asked to
        test authentication (login, credentials).

        Returns:
            tuple: (substitution_detected, description)
        """
        task_lower = task.lower()
        output_lower = output.lower()

        for task_concept, wrong_concept in SUBSTITUTION_PAIRS:
            # Check if task mentions this concept
            if task_concept not in task_lower:
                continue

            # Count how many terms from each cluster appear in the output
            task_concept_count = self._count_cluster_matches(output_lower, task_concept)
            wrong_concept_count = self._count_cluster_matches(output_lower, wrong_concept)

            # Substitution detected if output focuses more on wrong concept
            # Require at least 2 matches in wrong cluster to avoid false positives
            if wrong_concept_count >= 2 and wrong_concept_count > task_concept_count:
                return True, (
                    f"Task asks for '{task_concept}' but output focuses on "
                    f"'{wrong_concept}' ({wrong_concept_count} matches vs {task_concept_count})"
                )

        return False, None

    def _is_task_addressed(
        self,
        task: str,
        output: str,
        coverage: float,
    ) -> bool:
        """Check if the core task is addressed in the output.

        v1.1: Added to reduce over-detection on outputs that complete
        the task but include helpful additional information.
        v1.2: Improved patterns for code review and related topics.

        Args:
            task: The original task
            output: The agent output
            coverage: Pre-computed task term coverage

        Returns:
            True if the task appears to be addressed
        """
        # If task terms are well-covered, consider task addressed
        if coverage >= self.task_coverage_threshold:
            return True

        # Check for task action verbs being addressed
        task_lower = task.lower()
        output_lower = output.lower()

        # v1.2: Enhanced action patterns with related topics
        # Each pattern: (action_verb, indicators, related_topics_allowed)
        action_patterns = [
            ("analyze", ["analysis", "analyzed", "analyzing", "findings", "results", "examined"]),
            ("debug", ["fixed", "bug", "issue", "resolved", "debugging", "error", "problem"]),
            ("fix", ["fixed", "resolved", "corrected", "patched", "repaired"]),
            # v1.2: Review can include bugs, issues, style, quality, improvements
            ("review", ["review", "reviewed", "reviewing", "found", "identified", "issue",
                       "bug", "problem", "style", "suggestion", "improvement", "code"]),
            ("write", ["here", "following", "created", "written", "wrote"]),
            ("create", ["created", "here", "following", "built", "made"]),
            ("test", ["tested", "testing", "test", "passed", "failed", "verified", "checked"]),
            ("optimize", ["optimized", "improved", "faster", "performance", "efficient"]),
            ("document", ["documentation", "documented", "docs", "description"]),
            ("implement", ["implemented", "implementation", "built", "created", "added"]),
            ("check", ["checked", "verified", "confirmed", "validated", "found"]),
            ("validate", ["validated", "verified", "confirmed", "checked"]),
        ]

        for action, indicators in action_patterns:
            if action in task_lower:
                if any(ind in output_lower for ind in indicators):
                    return True

        # v1.2: Additional check for compound tasks like "review code for bugs"
        # If task mentions a specific focus (bugs, security, performance),
        # output addressing that focus counts as task addressed
        focus_terms = {
            "bug": ["bug", "issue", "error", "problem", "defect", "fix"],
            "security": ["security", "vulnerability", "secure", "auth", "permission"],
            "performance": ["performance", "speed", "fast", "slow", "optimize", "efficient"],
            "style": ["style", "format", "convention", "naming", "readable"],
            "quality": ["quality", "clean", "maintainable", "readable", "best practice"],
        }

        for focus, related_terms in focus_terms.items():
            if focus in task_lower:
                if any(term in output_lower for term in related_terms):
                    return True

        return False

    def detect(
        self,
        task: str,
        output: str,
        context: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> DerailmentResult:
        if len(output) < self.min_output_length:
            return DerailmentResult(
                detected=False,
                severity=DerailmentSeverity.NONE,
                confidence=0.0,
                task_output_similarity=1.0,
                topic_drift_score=0.0,
                explanation="Output too short to analyze",
                task_coverage=1.0,
            )

        similarity = self._compute_similarity(task, output)
        drift_score, task_coverage = self._compute_topic_drift(task, output, context)

        # v1.4: Check for writing tasks with matching content type
        # If task asks for documentation and output IS documentation, don't flag
        is_writing, expected_content_type = self._is_writing_task(task)
        if is_writing and expected_content_type:
            if self._matches_content_type(output, expected_content_type):
                # Output matches expected content type - not a derailment
                return DerailmentResult(
                    detected=False,
                    severity=DerailmentSeverity.NONE,
                    confidence=0.9,
                    task_output_similarity=similarity,
                    topic_drift_score=drift_score,
                    explanation=f"Output matches expected content type: {expected_content_type}",
                    task_coverage=task_coverage,
                )

        # v1.4: Check for research focus mismatch (e.g., pricing vs features)
        focus_mismatch, focus_desc = self._detect_research_focus_mismatch(task, output)

        # v1.2: Check for task substitution (e.g., authorization vs authentication)
        substitution_detected, substitution_desc = self._detect_task_substitution(task, output)

        # v1.1: Check if task is addressed before flagging derailment
        # This prevents over-detection when agent completes task + adds helpful info
        task_addressed = self._is_task_addressed(task, output, task_coverage)

        # v1.5: Check for framework-specific benign patterns
        has_framework_benign = self._has_framework_benign_pattern(output)

        # Detection logic:
        # 1. Task substitution is always a derailment (wrong task entirely)
        # 2. Research focus mismatch is a derailment (wrong aspect)
        # 3. Framework benign patterns exempt from detection (coordination)
        # 4. If task is addressed, only flag for severe cases
        # 5. Otherwise, use standard thresholds
        if substitution_detected:
            # v1.2: Task substitution is a clear derailment
            detected = True
        elif focus_mismatch:
            # v1.4: Research focus mismatch is a derailment
            detected = True
        elif has_framework_benign and task_addressed:
            # v1.5: Framework coordination with task addressed - not derailment
            detected = False
        elif task_addressed:
            # Task is addressed - only flag for severe cases (completely unrelated output)
            detected = similarity < 0.1  # Very strict threshold when task is addressed
        else:
            # Task not addressed - use standard thresholds
            detected = similarity < self.similarity_threshold or drift_score > self.drift_threshold

        raw_score = drift_score
        evidence = {
            "similarity": round(similarity, 4),
            "drift_score": round(drift_score, 4),
            "task_coverage": round(task_coverage, 4),
            "task_addressed": task_addressed,
            "substitution_detected": substitution_detected,
            "substitution_description": substitution_desc,
            "focus_mismatch_detected": focus_mismatch,
            "focus_mismatch_description": focus_desc,
            "framework_benign_pattern": has_framework_benign,  # v1.5
            "framework": self.framework,  # v1.5
            "similarity_threshold": self.similarity_threshold,
            "drift_threshold": self.drift_threshold,
            "task_coverage_threshold": self.task_coverage_threshold,
            "output_length": len(output),
            "detector_version": DETECTOR_VERSION,
        }

        if not detected:
            explanation = "Agent stayed on task"
            if task_addressed and drift_score > self.drift_threshold:
                explanation = "Agent addressed the task with helpful additional context"

            return DerailmentResult(
                detected=False,
                severity=DerailmentSeverity.NONE,
                confidence=1.0 - drift_score,
                task_output_similarity=similarity,
                topic_drift_score=drift_score,
                explanation=explanation,
                raw_score=raw_score,
                evidence=evidence,
                task_coverage=task_coverage,
            )

        if drift_score > 0.8 or similarity < 0.1:
            severity = DerailmentSeverity.SEVERE
        elif drift_score > 0.6 or similarity < 0.2:
            severity = DerailmentSeverity.MODERATE
        else:
            severity = DerailmentSeverity.MINOR

        confidence = self._calibrate_confidence(
            similarity=similarity,
            drift_score=drift_score,
            severity=severity,
            output_length=len(output),
        )

        agent_prefix = f"Agent '{agent_name}'" if agent_name else "Agent"
        explanation = (
            f"{agent_prefix} deviated from the assigned task. "
            f"Task-output similarity: {similarity:.2f} (threshold: {self.similarity_threshold}). "
            f"Topic drift score: {drift_score:.2f} (threshold: {self.drift_threshold}). "
            f"Task coverage: {task_coverage:.2f}."
        )

        suggested_fix = (
            "Add explicit task reminders in the prompt. Consider using: "
            "'Stay focused on the following task: [TASK]. Do not address unrelated topics.'"
        )

        return DerailmentResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            task_output_similarity=similarity,
            topic_drift_score=drift_score,
            explanation=explanation,
            suggested_fix=suggested_fix,
            raw_score=raw_score,
            evidence=evidence,
            task_coverage=task_coverage,
        )

    def get_config(self) -> dict:
        """Return detector configuration for versioning."""
        return {
            "name": DETECTOR_NAME,
            "version": DETECTOR_VERSION,
            "thresholds": {
                "similarity_threshold": self.similarity_threshold,
                "drift_threshold": self.drift_threshold,
                "task_coverage_threshold": self.task_coverage_threshold,
                "min_output_length": self.min_output_length,
            },
            "description": "Task derailment detection with task coverage verification",
        }

    def detect_from_trace(
        self,
        trace: dict,
    ) -> list[DerailmentResult]:
        results = []
        
        spans = trace.get("spans", [])
        for span in spans:
            task = span.get("input", {}).get("task", "")
            output = span.get("output", {}).get("content", "")
            context = span.get("input", {}).get("context", "")
            agent_name = span.get("name", "")
            
            if task and output:
                result = self.detect(
                    task=task,
                    output=output,
                    context=context,
                    agent_name=agent_name,
                )
                if result.detected:
                    results.append(result)
        
        return results
