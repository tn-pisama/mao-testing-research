"""Fix generators for context overflow detections."""

from typing import List, Dict, Any

from .generator import BaseFixGenerator
from .models import FixSuggestion, FixType, FixConfidence, CodeChange


class OverflowFixGenerator(BaseFixGenerator):
    """Generates fixes for context overflow detections."""

    def can_handle(self, detection_type: str) -> bool:
        return detection_type in ("overflow", "context_overflow")

    def generate_fixes(
        self,
        detection: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[FixSuggestion]:
        fixes = []
        detection_id = detection.get("id", "")
        details = detection.get("details", {})

        fixes.append(self._context_pruning_fix(detection_id, details, context))
        fixes.append(self._summarization_fix(detection_id, details, context))
        fixes.append(self._window_management_fix(detection_id, details, context))

        return fixes

    def _context_pruning_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import time


class MessagePriority(Enum):
    SYSTEM = 0       # Never prune system messages
    PINNED = 1       # User-pinned important context
    RECENT = 2       # Recent conversation turns
    TOOL_RESULT = 3  # Tool call results
    HISTORICAL = 4   # Older conversation turns
    VERBOSE = 5      # Low-info messages (acks, greetings)


@dataclass
class ContextMessage:
    """A message in the context window with metadata for pruning decisions."""
    role: str
    content: str
    token_count: int
    timestamp: float
    priority: MessagePriority = MessagePriority.HISTORICAL
    pinned: bool = False


class ContextPruner:
    """
    Trims old and low-priority context to keep the conversation
    within the model's context window. Uses a priority-based
    eviction strategy that preserves the most important information.
    """

    def __init__(self, max_tokens: int = 128000, target_ratio: float = 0.85):
        self.max_tokens = max_tokens
        self.target_tokens = int(max_tokens * target_ratio)
        self._pruned_count = 0
        self._pruned_tokens = 0

    def calculate_usage(self, messages: List[ContextMessage]) -> Dict[str, Any]:
        """Calculate current context window usage."""
        total = sum(m.token_count for m in messages)
        return {
            "total_tokens": total,
            "max_tokens": self.max_tokens,
            "usage_ratio": total / self.max_tokens,
            "remaining": self.max_tokens - total,
            "needs_pruning": total > self.target_tokens,
        }

    def prune(self, messages: List[ContextMessage]) -> List[ContextMessage]:
        """Prune messages to fit within the target token budget."""
        usage = self.calculate_usage(messages)
        if not usage["needs_pruning"]:
            return messages

        tokens_to_remove = usage["total_tokens"] - self.target_tokens

        # Sort by pruning priority (highest priority number = prune first)
        candidates = [
            (i, m) for i, m in enumerate(messages)
            if m.priority != MessagePriority.SYSTEM and not m.pinned
        ]
        candidates.sort(key=lambda x: (-x[1].priority.value, x[1].timestamp))

        indices_to_remove = set()
        removed_tokens = 0

        for idx, msg in candidates:
            if removed_tokens >= tokens_to_remove:
                break
            indices_to_remove.add(idx)
            removed_tokens += msg.token_count

        self._pruned_count += len(indices_to_remove)
        self._pruned_tokens += removed_tokens

        return [m for i, m in enumerate(messages) if i not in indices_to_remove]

    def classify_priority(self, message: Dict[str, str], position: int, total: int) -> MessagePriority:
        """Assign pruning priority to a message based on its characteristics."""
        role = message.get("role", "user")
        content = message.get("content", "")

        if role == "system":
            return MessagePriority.SYSTEM

        # Recent messages (last 20%) get higher priority
        if position >= total * 0.8:
            return MessagePriority.RECENT

        # Tool results
        if role == "tool" or message.get("tool_call_id"):
            return MessagePriority.TOOL_RESULT

        # Short low-info messages
        if len(content) < 20:
            return MessagePriority.VERBOSE

        return MessagePriority.HISTORICAL

    def prepare_messages(self, raw_messages: List[Dict[str, str]]) -> List[ContextMessage]:
        """Convert raw messages to ContextMessage objects with priorities."""
        total = len(raw_messages)
        result = []
        for i, msg in enumerate(raw_messages):
            priority = self.classify_priority(msg, i, total)
            # Rough token estimate: 1 token per 4 chars
            token_est = len(msg.get("content", "")) // 4
            result.append(ContextMessage(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                token_count=max(token_est, 1),
                timestamp=time.time() - (total - i),
                priority=priority,
            ))
        return result

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "pruned_messages": self._pruned_count,
            "pruned_tokens": self._pruned_tokens,
        }'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="overflow",
            fix_type=FixType.CONTEXT_PRUNING,
            confidence=FixConfidence.HIGH,
            title="Trim old context with priority-based eviction",
            description="Implement a context pruner that assigns priority levels to messages and evicts low-priority, older messages when the context window approaches its limit.",
            rationale="Context overflow occurs when accumulated conversation history exceeds the model's window. Priority-based pruning preserves system instructions and recent turns while evicting low-value historical messages, keeping the model operational.",
            code_changes=[
                CodeChange(
                    file_path="utils/context_pruner.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Priority-based context pruner with configurable token budgets and message classification",
                )
            ],
            estimated_impact="Prevents context overflow by automatically evicting low-priority messages",
            tags=["overflow", "context-pruning", "token-management"],
        )

    def _summarization_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class SummarizationResult:
    """Result of summarizing a context segment."""
    original_token_count: int
    summarized_token_count: int
    summary: str
    compression_ratio: float
    segments_summarized: int


class ContextSummarizer:
    """
    Summarizes long context segments to reduce token usage while
    preserving key information. Replaces detailed historical turns
    with concise summaries when the context window fills up.
    """

    SUMMARIZE_PROMPT = (
        "Summarize the following conversation segment concisely. "
        "Preserve: key decisions, facts mentioned, action items, and "
        "any constraints established. Omit: greetings, filler, repeated info.\\n\\n"
        "{segment}"
    )

    def __init__(
        self,
        llm_call: Optional[Callable] = None,
        max_segment_tokens: int = 4000,
        summary_target_ratio: float = 0.25,
    ):
        self._llm_call = llm_call
        self.max_segment_tokens = max_segment_tokens
        self.summary_target_ratio = summary_target_ratio
        self._summaries_created = 0

    def should_summarize(self, messages: List[Dict[str, str]], max_tokens: int) -> bool:
        """Check if the context needs summarization."""
        total_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
        return total_tokens > max_tokens * 0.75

    def identify_segments(
        self,
        messages: List[Dict[str, str]],
        protected_recent: int = 10,
    ) -> List[List[Dict[str, str]]]:
        """Identify message segments that can be summarized."""
        # Protect system messages and recent turns
        summarizable = []
        current_segment: List[Dict[str, str]] = []
        segment_tokens = 0

        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                if current_segment:
                    summarizable.append(current_segment)
                    current_segment = []
                    segment_tokens = 0
                continue

            if i >= len(messages) - protected_recent:
                break

            token_est = len(msg.get("content", "")) // 4

            if segment_tokens + token_est > self.max_segment_tokens:
                if current_segment:
                    summarizable.append(current_segment)
                current_segment = [msg]
                segment_tokens = token_est
            else:
                current_segment.append(msg)
                segment_tokens += token_est

        if current_segment:
            summarizable.append(current_segment)

        return summarizable

    def summarize_segment(self, segment: List[Dict[str, str]]) -> Dict[str, str]:
        """Summarize a segment of messages into a single summary message."""
        segment_text = "\\n".join(
            f"{m['role']}: {m.get('content', '')}" for m in segment
        )

        if self._llm_call:
            prompt = self.SUMMARIZE_PROMPT.format(segment=segment_text)
            summary = self._llm_call(prompt)
        else:
            # Fallback: extractive summary (take first sentence of each message)
            lines = []
            for msg in segment:
                content = msg.get("content", "")
                first_sentence = content.split(".")[0] + "." if content else ""
                if first_sentence and len(first_sentence) > 10:
                    lines.append(f"{msg['role']}: {first_sentence}")
            summary = "\\n".join(lines[:10])

        self._summaries_created += 1
        return {
            "role": "system",
            "content": f"[CONTEXT SUMMARY]\\n{summary}",
        }

    def compact(
        self,
        messages: List[Dict[str, str]],
        protected_recent: int = 10,
    ) -> Dict[str, Any]:
        """Compact the full message list by summarizing old segments."""
        segments = self.identify_segments(messages, protected_recent)

        if not segments:
            return {"messages": messages, "compacted": False}

        original_tokens = sum(len(m.get("content", "")) // 4 for m in messages)

        # Build compacted message list
        compacted = [m for m in messages if m.get("role") == "system"]

        for segment in segments:
            summary_msg = self.summarize_segment(segment)
            compacted.append(summary_msg)

        # Add protected recent messages
        recent = messages[-protected_recent:]
        compacted.extend(recent)

        new_tokens = sum(len(m.get("content", "")) // 4 for m in compacted)

        return {
            "messages": compacted,
            "compacted": True,
            "original_tokens": original_tokens,
            "new_tokens": new_tokens,
            "compression_ratio": new_tokens / max(original_tokens, 1),
            "segments_summarized": len(segments),
        }'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="overflow",
            fix_type=FixType.SUMMARIZATION,
            confidence=FixConfidence.MEDIUM,
            title="Summarize long context to reduce token usage",
            description="Replace detailed historical conversation segments with concise summaries, preserving key decisions and facts while dramatically reducing token count.",
            rationale="Rather than simply dropping old context (losing information), summarization compresses it. This preserves the semantic content of earlier turns while freeing token budget for new interactions, maintaining conversation coherence.",
            code_changes=[
                CodeChange(
                    file_path="utils/context_summarizer.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Context summarizer with segment identification, LLM-based compression, and extractive fallback",
                )
            ],
            estimated_impact="Reduces context size by 60-75% while preserving key information",
            tags=["overflow", "summarization", "compression", "context-management"],
        )

    def _window_management_fix(
        self,
        detection_id: str,
        details: Dict[str, Any],
        context: Dict[str, Any],
    ) -> FixSuggestion:
        code = '''from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class WindowSnapshot:
    """A snapshot of context window usage at a point in time."""
    timestamp: float
    total_tokens: int
    max_tokens: int
    usage_ratio: float
    message_count: int


class ContextWindowManager:
    """
    Tracks and manages context window usage across LLM calls.
    Monitors token consumption trends, predicts when overflow
    will occur, and triggers preventive actions.
    """

    # Thresholds for different alert levels
    THRESHOLDS = {
        "green": 0.50,    # Under 50% - healthy
        "yellow": 0.70,   # 70% - start monitoring
        "orange": 0.85,   # 85% - start pruning
        "red": 0.95,      # 95% - aggressive action needed
    }

    def __init__(self, max_tokens: int = 128000):
        self.max_tokens = max_tokens
        self._history: List[WindowSnapshot] = []
        self._callbacks: Dict[str, List] = {
            "yellow": [],
            "orange": [],
            "red": [],
        }

    def on_threshold(self, level: str, callback) -> None:
        """Register a callback for when a threshold is crossed."""
        if level in self._callbacks:
            self._callbacks[level].append(callback)

    def record(self, messages: List[Dict[str, str]]) -> WindowSnapshot:
        """Record current window usage and check thresholds."""
        total_tokens = sum(
            len(m.get("content", "")) // 4 for m in messages
        )

        snapshot = WindowSnapshot(
            timestamp=time.time(),
            total_tokens=total_tokens,
            max_tokens=self.max_tokens,
            usage_ratio=total_tokens / self.max_tokens,
            message_count=len(messages),
        )
        self._history.append(snapshot)

        # Check thresholds
        self._check_thresholds(snapshot)

        return snapshot

    def predict_overflow(self, lookahead_turns: int = 5) -> Dict[str, Any]:
        """Predict when context overflow will occur based on usage trends."""
        if len(self._history) < 2:
            return {"predicted": False, "reason": "Insufficient history"}

        recent = self._history[-10:]
        if len(recent) < 2:
            return {"predicted": False, "reason": "Insufficient data"}

        # Calculate token growth rate per turn
        growth_rates = []
        for i in range(1, len(recent)):
            delta = recent[i].total_tokens - recent[i - 1].total_tokens
            growth_rates.append(delta)

        avg_growth = sum(growth_rates) / len(growth_rates)
        current = recent[-1].total_tokens
        projected = current + (avg_growth * lookahead_turns)

        return {
            "predicted": projected > self.max_tokens,
            "current_tokens": current,
            "avg_growth_per_turn": round(avg_growth),
            "projected_tokens": round(projected),
            "turns_until_overflow": max(
                round((self.max_tokens - current) / max(avg_growth, 1)), 0
            ) if avg_growth > 0 else None,
            "recommendation": self._recommend(current / self.max_tokens, avg_growth),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current window management status."""
        if not self._history:
            return {"status": "no_data"}

        latest = self._history[-1]
        level = self._get_level(latest.usage_ratio)
        prediction = self.predict_overflow()

        return {
            "level": level,
            "usage_ratio": round(latest.usage_ratio, 3),
            "total_tokens": latest.total_tokens,
            "max_tokens": self.max_tokens,
            "remaining_tokens": self.max_tokens - latest.total_tokens,
            "message_count": latest.message_count,
            "prediction": prediction,
            "history_length": len(self._history),
        }

    def _check_thresholds(self, snapshot: WindowSnapshot) -> None:
        """Fire callbacks when thresholds are crossed."""
        previous_ratio = self._history[-2].usage_ratio if len(self._history) >= 2 else 0.0

        for level in ["yellow", "orange", "red"]:
            threshold = self.THRESHOLDS[level]
            if previous_ratio < threshold <= snapshot.usage_ratio:
                logger.warning(
                    f"Context window hit {level} threshold: "
                    f"{snapshot.usage_ratio:.1%} ({snapshot.total_tokens}/{self.max_tokens})"
                )
                for cb in self._callbacks.get(level, []):
                    cb(snapshot)

    def _get_level(self, ratio: float) -> str:
        if ratio >= self.THRESHOLDS["red"]:
            return "red"
        elif ratio >= self.THRESHOLDS["orange"]:
            return "orange"
        elif ratio >= self.THRESHOLDS["yellow"]:
            return "yellow"
        return "green"

    def _recommend(self, ratio: float, growth_rate: float) -> str:
        if ratio >= 0.9:
            return "immediate_pruning"
        elif ratio >= 0.75 or growth_rate > 2000:
            return "summarize_history"
        elif ratio >= 0.5:
            return "monitor"
        return "healthy"'''

        return self._create_suggestion(
            detection_id=detection_id,
            detection_type="overflow",
            fix_type=FixType.WINDOW_MANAGEMENT,
            confidence=FixConfidence.MEDIUM,
            title="Track and manage context window usage proactively",
            description="Add a context window manager that tracks token consumption over time, predicts overflow based on growth trends, and triggers preventive actions at configurable thresholds.",
            rationale="Context overflow is often sudden and catastrophic. By continuously monitoring token usage and growth rates, this manager provides early warning and triggers pruning or summarization before the window fills up, preventing mid-conversation failures.",
            code_changes=[
                CodeChange(
                    file_path="utils/window_manager.py",
                    language="python",
                    original_code=None,
                    suggested_code=code,
                    description="Context window manager with threshold alerts, overflow prediction, and usage tracking",
                )
            ],
            estimated_impact="Prevents surprise overflow by predicting and acting before the window fills",
            tags=["overflow", "window-management", "monitoring", "proactive"],
        )
