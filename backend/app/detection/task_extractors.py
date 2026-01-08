"""
Framework-Aware Task Extractors
================================

Different multi-agent frameworks store task information in different places:
- ChatDev: System prompt contains "develop a program..."
- AG2/AutoGen: First user message or initial_message config
- LangGraph: First HumanMessage or invoke input
- MetaGPT: Project description in metadata
- Magentic: Function call parameters

This module provides framework-specific extractors to reliably extract
the original task from any trace format.
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Simplified turn representation for extraction."""
    role: str  # user, agent, system, assistant, tool
    content: str
    participant_id: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ExtractionResult:
    """Result from task extraction."""
    task: str
    confidence: float
    source: str  # Where the task was found
    framework: str
    agent_output_summary: str
    key_events: List[str]


class TaskExtractor(Protocol):
    """Protocol for framework-specific task extractors."""

    framework: str

    def can_extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> bool:
        """Check if this extractor can handle this trace."""
        ...

    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        """Extract task, output summary, and key events from trace."""
        ...


class BaseTaskExtractor(ABC):
    """Base class for task extractors with common utilities."""

    framework: str = "unknown"

    def _summarize_output(self, turns: List[ConversationTurn], max_length: int = 1000) -> str:
        """Summarize agent output from turns."""
        agent_content = []
        for turn in turns:
            if turn.role in ("agent", "assistant"):
                # Skip very short or metadata-like content
                if len(turn.content) > 20 and not turn.content.startswith("{"):
                    agent_content.append(turn.content[:500])

        if not agent_content:
            return "No agent output found"

        combined = "\n---\n".join(agent_content[:5])  # First 5 agent turns
        return combined[:max_length]

    def _extract_key_events(self, turns: List[ConversationTurn], max_events: int = 10) -> List[str]:
        """Extract key events from turns."""
        events = []

        for i, turn in enumerate(turns):
            # Tool calls
            if turn.role == "tool":
                tool_name = turn.metadata.get("tool_name", "tool")
                events.append(f"Tool call: {tool_name}")

            # Errors or failures
            if "error" in turn.content.lower() or "failed" in turn.content.lower():
                snippet = turn.content[:100].replace("\n", " ")
                events.append(f"Error/Failure: {snippet}...")

            # State changes
            if "state" in turn.metadata:
                events.append(f"State change at turn {i}")

            # Agent decisions
            if turn.role in ("agent", "assistant") and len(turn.content) > 50:
                # Extract first action-like sentence
                first_sentence = turn.content.split(".")[0][:100]
                if len(first_sentence) > 20:
                    events.append(f"Agent: {first_sentence}")

        return events[:max_events]

    @abstractmethod
    def can_extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> bool:
        """Check if this extractor can handle this trace."""
        pass

    @abstractmethod
    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        """Extract task, output summary, and key events from trace."""
        pass


class ChatDevExtractor(BaseTaskExtractor):
    """Extractor for ChatDev traces.

    ChatDev structure:
    - System turn contains the task: "develop a program that..."
    - All participants are agents (CEO, Programmer, Reviewer, etc.)
    - No user turns in the conversation
    """

    framework = "chatdev"

    def can_extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> bool:
        # Check metadata for ChatDev indicators
        framework = metadata.get("framework", "").lower()
        if "chatdev" in framework:
            return True

        # Check for ChatDev-specific participant names
        chatdev_roles = {"ceo", "programmer", "reviewer", "tester", "cto", "designer"}
        for turn in turns:
            if turn.participant_id:
                pid_lower = turn.participant_id.lower()
                if any(role in pid_lower for role in chatdev_roles):
                    return True

        # Check for "develop a program" in system prompt
        for turn in turns:
            if turn.role == "system" and "develop a program" in turn.content.lower():
                return True

        return False

    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        task = ""
        confidence = 0.5

        # Look for task in system turn
        for turn in turns:
            if turn.role == "system" and len(turn.content) > 30:
                # ChatDev system prompts typically start with task description
                # Common task keywords: develop, create, design, implement, build, write
                content_lower = turn.content.lower()
                task_keywords = ["develop", "create", "design", "implement", "build", "write", "make"]
                if any(kw in content_lower for kw in task_keywords):
                    task = turn.content
                    confidence = 0.95
                    break

        # Fallback: first non-config agent turn
        if not task:
            for turn in turns:
                if turn.role in ("agent", "assistant"):
                    # Skip JSON config turns
                    if not turn.content.strip().startswith("{"):
                        task = turn.content[:500]
                        confidence = 0.6
                        break

        return ExtractionResult(
            task=task,
            confidence=confidence,
            source="system_prompt" if confidence > 0.8 else "first_agent_turn",
            framework=self.framework,
            agent_output_summary=self._summarize_output(turns),
            key_events=self._extract_key_events(turns),
        )


class AG2Extractor(BaseTaskExtractor):
    """Extractor for AG2/AutoGen traces.

    AG2 structure:
    - First user message contains the task
    - Or initial_message in metadata/config
    - Multi-agent conversation follows
    """

    framework = "ag2"

    def can_extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> bool:
        framework = metadata.get("framework", "").lower()
        if any(x in framework for x in ["ag2", "autogen", "auto-gen"]):
            return True

        # Check for AG2-specific patterns in metadata
        if "initial_message" in metadata or "config" in metadata:
            return True

        return False

    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        task = ""
        confidence = 0.5
        source = "unknown"

        # Check metadata for initial_message
        if "initial_message" in metadata:
            task = metadata["initial_message"]
            confidence = 0.95
            source = "metadata.initial_message"
        elif "config" in metadata and isinstance(metadata["config"], dict):
            if "initial_message" in metadata["config"]:
                task = metadata["config"]["initial_message"]
                confidence = 0.95
                source = "metadata.config.initial_message"

        # Fallback: first user turn
        if not task:
            for turn in turns:
                if turn.role == "user" and len(turn.content) > 10:
                    task = turn.content
                    confidence = 0.85
                    source = "first_user_turn"
                    break

        # Second fallback: first non-empty turn
        if not task:
            for turn in turns:
                if len(turn.content) > 20 and not turn.content.startswith("{"):
                    task = turn.content[:500]
                    confidence = 0.5
                    source = "first_content_turn"
                    break

        return ExtractionResult(
            task=task,
            confidence=confidence,
            source=source,
            framework=self.framework,
            agent_output_summary=self._summarize_output(turns),
            key_events=self._extract_key_events(turns),
        )


class LangGraphExtractor(BaseTaskExtractor):
    """Extractor for LangGraph traces.

    LangGraph structure:
    - First HumanMessage contains the task
    - Or invoke() input in metadata
    - State-based conversation with checkpoints
    """

    framework = "langgraph"

    def can_extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> bool:
        framework = metadata.get("framework", "").lower()
        if "langgraph" in framework:
            return True

        # Check for LangGraph-specific metadata
        if "checkpoint" in metadata or "thread_id" in metadata:
            return True

        return False

    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        task = ""
        confidence = 0.5
        source = "unknown"

        # Check for invoke input in metadata
        if "input" in metadata and isinstance(metadata["input"], dict):
            if "messages" in metadata["input"]:
                messages = metadata["input"]["messages"]
                if messages and len(messages) > 0:
                    first_msg = messages[0]
                    if isinstance(first_msg, dict):
                        task = first_msg.get("content", "")
                    else:
                        task = str(first_msg)
                    confidence = 0.95
                    source = "metadata.input.messages[0]"

        # Fallback: first human/user turn
        if not task:
            for turn in turns:
                if turn.role in ("user", "human") and len(turn.content) > 10:
                    task = turn.content
                    confidence = 0.85
                    source = "first_human_turn"
                    break

        return ExtractionResult(
            task=task,
            confidence=confidence,
            source=source,
            framework=self.framework,
            agent_output_summary=self._summarize_output(turns),
            key_events=self._extract_key_events(turns),
        )


class MetaGPTExtractor(BaseTaskExtractor):
    """Extractor for MetaGPT traces.

    MetaGPT structure:
    - Project description in metadata or first message
    - Role-based agents (ProductManager, Architect, etc.)
    """

    framework = "metagpt"

    def can_extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> bool:
        framework = metadata.get("framework", "").lower()
        if "metagpt" in framework:
            return True

        # Check for MetaGPT-specific roles
        metagpt_roles = {"productmanager", "architect", "engineer", "qaengineer"}
        for turn in turns:
            if turn.participant_id:
                pid_lower = turn.participant_id.lower().replace("_", "").replace("-", "")
                if any(role in pid_lower for role in metagpt_roles):
                    return True

        return False

    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        task = ""
        confidence = 0.5
        source = "unknown"

        # Check metadata for project description
        for key in ["project", "description", "requirement", "task"]:
            if key in metadata and isinstance(metadata[key], str):
                task = metadata[key]
                confidence = 0.9
                source = f"metadata.{key}"
                break

        # Fallback: first user or system message
        if not task:
            for turn in turns:
                if turn.role in ("user", "system") and len(turn.content) > 20:
                    task = turn.content[:500]
                    confidence = 0.7
                    source = f"first_{turn.role}_turn"
                    break

        return ExtractionResult(
            task=task,
            confidence=confidence,
            source=source,
            framework=self.framework,
            agent_output_summary=self._summarize_output(turns),
            key_events=self._extract_key_events(turns),
        )


class MagenticExtractor(BaseTaskExtractor):
    """Extractor for Magentic traces.

    Magentic structure:
    - Function call patterns
    - Prompt templates with parameters
    """

    framework = "magentic"

    def can_extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> bool:
        framework = metadata.get("framework", "").lower()
        return "magentic" in framework

    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        task = ""
        confidence = 0.5
        source = "unknown"

        # Check for function parameters in metadata
        if "parameters" in metadata:
            task = str(metadata["parameters"])
            confidence = 0.85
            source = "metadata.parameters"

        # Fallback: first user turn
        if not task:
            for turn in turns:
                if turn.role == "user" and len(turn.content) > 10:
                    task = turn.content
                    confidence = 0.75
                    source = "first_user_turn"
                    break

        return ExtractionResult(
            task=task,
            confidence=confidence,
            source=source,
            framework=self.framework,
            agent_output_summary=self._summarize_output(turns),
            key_events=self._extract_key_events(turns),
        )


class OpenManusExtractor(BaseTaskExtractor):
    """Extractor for OpenManus traces."""

    framework = "openmanus"

    def can_extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> bool:
        framework = metadata.get("framework", "").lower()
        return "openmanus" in framework or "manus" in framework

    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        task = ""
        confidence = 0.5
        source = "unknown"

        # Check metadata
        if "task" in metadata:
            task = metadata["task"]
            confidence = 0.9
            source = "metadata.task"

        # Fallback: first user turn
        if not task:
            for turn in turns:
                if turn.role == "user" and len(turn.content) > 10:
                    task = turn.content
                    confidence = 0.75
                    source = "first_user_turn"
                    break

        return ExtractionResult(
            task=task,
            confidence=confidence,
            source=source,
            framework=self.framework,
            agent_output_summary=self._summarize_output(turns),
            key_events=self._extract_key_events(turns),
        )


class GenericExtractor(BaseTaskExtractor):
    """Generic fallback extractor for unknown frameworks.

    Uses heuristics to find the task:
    1. First user message
    2. System prompt (if substantial)
    3. First non-JSON content
    """

    framework = "generic"

    def can_extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> bool:
        # Always can extract as fallback
        return True

    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        task = ""
        confidence = 0.0
        source = "none"

        # Priority 1: User turns
        for turn in turns:
            if turn.role == "user" and len(turn.content) > 10:
                task = turn.content
                confidence = 0.7
                source = "first_user_turn"
                break

        # Priority 2: System turns with substantial content
        if not task:
            for turn in turns:
                if turn.role == "system" and len(turn.content) > 50:
                    # Check it's not just a system prompt template
                    if not any(x in turn.content.lower() for x in ["you are", "assistant", "helpful"]):
                        task = turn.content[:500]
                        confidence = 0.6
                        source = "system_turn"
                        break

        # Priority 3: First agent turn that gives task
        if not task:
            for turn in turns:
                if turn.role in ("agent", "assistant"):
                    # Look for task-giving patterns
                    content_lower = turn.content.lower()
                    if any(x in content_lower for x in ["develop", "create", "implement", "build", "write"]):
                        task = turn.content[:500]
                        confidence = 0.5
                        source = "first_agent_task"
                        break

        # Priority 4: Any substantial content
        if not task:
            for turn in turns:
                if len(turn.content) > 30 and not turn.content.startswith("{"):
                    task = turn.content[:500]
                    confidence = 0.3
                    source = "first_content"
                    break

        return ExtractionResult(
            task=task if task else "Unknown task",
            confidence=confidence,
            source=source,
            framework=metadata.get("framework", "unknown"),
            agent_output_summary=self._summarize_output(turns),
            key_events=self._extract_key_events(turns),
        )


class TaskExtractorRegistry:
    """Registry of task extractors with automatic framework detection."""

    def __init__(self):
        self._extractors: List[BaseTaskExtractor] = [
            ChatDevExtractor(),
            AG2Extractor(),
            LangGraphExtractor(),
            MetaGPTExtractor(),
            MagenticExtractor(),
            OpenManusExtractor(),
            GenericExtractor(),  # Fallback, always last
        ]

    def detect_framework(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> str:
        """Detect the framework from trace data."""
        # Check explicit metadata first
        if "framework" in metadata:
            return metadata["framework"].lower()

        # Try each extractor
        for extractor in self._extractors[:-1]:  # Skip generic
            if extractor.can_extract(turns, metadata):
                return extractor.framework

        return "unknown"

    def extract(self, turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
        """Extract task using the best matching extractor."""
        for extractor in self._extractors:
            if extractor.can_extract(turns, metadata):
                result = extractor.extract(turns, metadata)
                logger.debug(
                    f"Extracted task using {extractor.framework} extractor "
                    f"(confidence={result.confidence:.2f}, source={result.source})"
                )
                return result

        # Should never reach here due to GenericExtractor
        return GenericExtractor().extract(turns, metadata)


# Global registry instance
_registry = TaskExtractorRegistry()


def extract_task(turns: List[ConversationTurn], metadata: Dict[str, Any]) -> ExtractionResult:
    """Extract task from trace using framework-aware extraction.

    Args:
        turns: List of conversation turns
        metadata: Trace metadata dict

    Returns:
        ExtractionResult with task, output summary, and key events
    """
    return _registry.extract(turns, metadata)


def detect_framework(turns: List[ConversationTurn], metadata: Dict[str, Any]) -> str:
    """Detect framework from trace data.

    Args:
        turns: List of conversation turns
        metadata: Trace metadata dict

    Returns:
        Framework name (lowercase)
    """
    return _registry.detect_framework(turns, metadata)
