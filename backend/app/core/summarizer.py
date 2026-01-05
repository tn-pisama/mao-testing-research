"""
Conversation Summarization for Long Contexts
=============================================

This module provides tools for handling long conversation traces that exceed
context window limits. It includes:

1. ConversationSummarizer - Summarizes conversations using Claude Haiku
2. SlidingWindowManager - Manages context windows with summarization
3. Token counting utilities

Used by the turn-aware detection system to handle MAST-Data traces that
can contain 300K+ character trajectories.

Version: 1.0
"""

import os
import hashlib
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from functools import lru_cache

import httpx
import tiktoken

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MAX_TOKENS = 8000
DEFAULT_SUMMARY_MAX_TOKENS = 2000
DEFAULT_OVERLAP_TOKENS = 500
HAIKU_MODEL = "claude-3-5-haiku-20241022"


def get_anthropic_api_key() -> str:
    """Get Anthropic API key from environment."""
    return os.getenv("ANTHROPIC_API_KEY", "")


@lru_cache(maxsize=1)
def get_tokenizer():
    """Get tiktoken tokenizer for token counting."""
    try:
        return tiktoken.encoding_for_model("gpt-4")
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    if not text:
        return 0
    try:
        tokenizer = get_tokenizer()
        return len(tokenizer.encode(text))
    except Exception:
        # Fallback: rough approximation
        return len(text) // 4


@dataclass
class SummarizationResult:
    """Result from summarizing conversation turns."""
    summary: str
    original_tokens: int
    summary_tokens: int
    compression_ratio: float
    turns_summarized: int
    model_used: str = HAIKU_MODEL
    cached: bool = False


@dataclass
class ContextWindow:
    """A context window with optional summary prefix."""
    content: str
    total_tokens: int
    includes_summary: bool = False
    summary_covers_turns: Tuple[int, int] = (0, 0)  # (start, end) turn numbers
    recent_turns: Tuple[int, int] = (0, 0)  # (start, end) turn numbers


class ConversationSummarizer:
    """Summarizes multi-turn conversations to fit context windows.

    Uses Claude Haiku for fast, cost-effective summarization that
    preserves key information for failure detection.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_summary_tokens: int = DEFAULT_SUMMARY_MAX_TOKENS,
        cache_summaries: bool = True,
    ):
        self.api_key = api_key or get_anthropic_api_key()
        self.max_summary_tokens = max_summary_tokens
        self.cache_summaries = cache_summaries
        self._cache: Dict[str, SummarizationResult] = {}

    def _get_cache_key(self, turns: List[Dict[str, Any]]) -> str:
        """Generate cache key from turn content hashes."""
        content = "".join(t.get("content_hash", t.get("content", ""))[:100] for t in turns)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def summarize_turns(
        self,
        turns: List[Dict[str, Any]],
        max_output_tokens: int = DEFAULT_SUMMARY_MAX_TOKENS,
        preserve_task: bool = True,
        preserve_failures: bool = True,
    ) -> SummarizationResult:
        """Summarize conversation turns.

        Args:
            turns: List of turn dicts with 'role', 'participant_id', 'content' keys
            max_output_tokens: Maximum tokens for summary
            preserve_task: Explicitly preserve the original task/goal
            preserve_failures: Explicitly preserve failure indicators

        Returns:
            SummarizationResult with summary and metadata
        """
        if not turns:
            return SummarizationResult(
                summary="",
                original_tokens=0,
                summary_tokens=0,
                compression_ratio=1.0,
                turns_summarized=0,
            )

        # Check cache
        if self.cache_summaries:
            cache_key = self._get_cache_key(turns)
            if cache_key in self._cache:
                result = self._cache[cache_key]
                result.cached = True
                return result

        # Build conversation text
        conv_text = self._format_turns(turns)
        original_tokens = count_tokens(conv_text)

        # If already under limit, return as-is
        if original_tokens <= max_output_tokens:
            return SummarizationResult(
                summary=conv_text,
                original_tokens=original_tokens,
                summary_tokens=original_tokens,
                compression_ratio=1.0,
                turns_summarized=len(turns),
            )

        # Build summarization prompt
        prompt = self._build_summarization_prompt(
            conv_text,
            max_output_tokens,
            preserve_task,
            preserve_failures,
        )

        # Call Claude Haiku
        summary = self._call_claude(prompt, max_output_tokens)
        summary_tokens = count_tokens(summary)

        result = SummarizationResult(
            summary=summary,
            original_tokens=original_tokens,
            summary_tokens=summary_tokens,
            compression_ratio=summary_tokens / original_tokens if original_tokens > 0 else 1.0,
            turns_summarized=len(turns),
        )

        # Cache result
        if self.cache_summaries:
            self._cache[cache_key] = result

        return result

    def _format_turns(self, turns: List[Dict[str, Any]]) -> str:
        """Format turns into conversation text."""
        lines = []
        for t in turns:
            role = t.get("role", t.get("participant_type", "unknown"))
            participant = t.get("participant_id", "unknown")
            content = t.get("content", "")
            turn_num = t.get("turn_number", "?")
            lines.append(f"[Turn {turn_num}] [{role}:{participant}]\n{content}")
        return "\n\n".join(lines)

    def _build_summarization_prompt(
        self,
        conv_text: str,
        max_tokens: int,
        preserve_task: bool,
        preserve_failures: bool,
    ) -> str:
        """Build the summarization prompt."""
        preservation_instructions = []
        if preserve_task:
            preservation_instructions.append(
                "- The original task/goal from the first user message"
            )
        if preserve_failures:
            preservation_instructions.append(
                "- Any errors, failures, or problems encountered"
            )
            preservation_instructions.append(
                "- Signs of context neglect (ignoring previous information)"
            )
            preservation_instructions.append(
                "- Signs of task derailment (going off-topic)"
            )
            preservation_instructions.append(
                "- Repetitive or looping behavior"
            )

        preservation_text = "\n".join(preservation_instructions) if preservation_instructions else ""

        # Truncate input to prevent API limits
        max_input_chars = 100000  # ~25K tokens
        truncated_text = conv_text[:max_input_chars]
        if len(conv_text) > max_input_chars:
            truncated_text += "\n\n[... conversation truncated ...]"

        return f"""Summarize this multi-agent conversation concisely. The summary will be used for failure detection analysis.

PRESERVE THESE ELEMENTS:
{preservation_text}
- Key decisions and actions taken by each agent
- The sequence of events and handoffs
- The final outcome or current state

CONVERSATION:
{truncated_text}

Provide a structured summary that captures the conversation flow. Maximum {max_tokens} tokens.

SUMMARY:"""

    def _call_claude(self, prompt: str, max_tokens: int) -> str:
        """Call Claude API for summarization."""
        if not self.api_key:
            logger.warning("No Anthropic API key configured, using fallback summarization")
            return self._fallback_summarize(prompt)

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": HAIKU_MODEL,
                        "max_tokens": max_tokens,
                        "messages": [
                            {"role": "user", "content": prompt},
                        ],
                    },
                )

                if response.status_code != 200:
                    logger.error(f"Claude API error: {response.status_code} - {response.text}")
                    return self._fallback_summarize(prompt)

                data = response.json()
                return data["content"][0]["text"]

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            return self._fallback_summarize(prompt)

    def _fallback_summarize(self, prompt: str) -> str:
        """Fallback summarization when API is unavailable.

        Uses simple extraction of key sentences.
        """
        # Extract conversation from prompt
        conv_start = prompt.find("CONVERSATION:")
        conv_end = prompt.find("SUMMARY:")

        if conv_start == -1:
            return "Summary unavailable (API error)"

        conv_text = prompt[conv_start + 13:conv_end].strip()

        # Simple extractive summarization
        lines = conv_text.split("\n")

        # Keep first line (usually task), sample of middle, last few lines
        summary_lines = []

        # First turn (usually contains task)
        if lines:
            summary_lines.append(lines[0][:500])

        # Sample from middle (every Nth line)
        n = max(1, len(lines) // 10)
        for i in range(n, len(lines) - 5, n):
            if lines[i].strip():
                summary_lines.append(lines[i][:300])
            if len(summary_lines) > 15:
                break

        # Last few lines (recent context)
        for line in lines[-5:]:
            if line.strip() and line not in summary_lines:
                summary_lines.append(line[:300])

        return "\n".join(summary_lines)

    def clear_cache(self):
        """Clear the summary cache."""
        self._cache.clear()


class SlidingWindowManager:
    """Manages conversation context with sliding window and summarization.

    For long conversations, maintains a context window that includes:
    1. A summary of early turns
    2. Full content of recent turns

    This ensures detection algorithms have both historical context
    and detailed recent information.
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
        recent_turns_to_keep: int = 10,
        summarizer: Optional[ConversationSummarizer] = None,
    ):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.recent_turns_to_keep = recent_turns_to_keep
        self.summarizer = summarizer or ConversationSummarizer()

    def get_context_for_turn(
        self,
        turns: List[Dict[str, Any]],
        focus_turn: int,
    ) -> ContextWindow:
        """Get optimal context window for a specific turn.

        Args:
            turns: All conversation turns
            focus_turn: The turn number to focus on (1-indexed)

        Returns:
            ContextWindow with content and metadata
        """
        if not turns:
            return ContextWindow(
                content="",
                total_tokens=0,
            )

        # Always include first turn (task) and recent turns around focus
        essential_turn_nums = {1}  # First turn (task)

        # Recent turns around focus
        start = max(1, focus_turn - self.recent_turns_to_keep // 2)
        end = min(len(turns), focus_turn + self.recent_turns_to_keep // 2)

        for i in range(start, end + 1):
            essential_turn_nums.add(i)

        # Build context from essential turns
        essential_turns = [t for t in turns if t.get("turn_number") in essential_turn_nums]
        context = self.summarizer._format_turns(essential_turns)

        total_tokens = count_tokens(context)

        # If under limit, return as-is
        if total_tokens <= self.max_tokens:
            return ContextWindow(
                content=context,
                total_tokens=total_tokens,
                includes_summary=False,
                recent_turns=(start, end),
            )

        # Need summarization - summarize early turns
        early_end = max(1, start - 1)
        early_turns = [t for t in turns if t.get("turn_number", 0) > 1 and t.get("turn_number", 0) <= early_end]

        if early_turns:
            summary_result = self.summarizer.summarize_turns(
                early_turns,
                max_output_tokens=self.max_tokens // 3,  # Reserve 1/3 for summary
            )

            # Build combined context
            first_turn = [t for t in turns if t.get("turn_number") == 1]
            recent_turns = [t for t in turns if t.get("turn_number") in essential_turn_nums and t.get("turn_number") != 1]

            first_content = self.summarizer._format_turns(first_turn) if first_turn else ""
            recent_content = self.summarizer._format_turns(recent_turns)

            combined = f"{first_content}\n\n[SUMMARY of turns 2-{early_end}]\n{summary_result.summary}\n\n{recent_content}"

            return ContextWindow(
                content=combined,
                total_tokens=count_tokens(combined),
                includes_summary=True,
                summary_covers_turns=(2, early_end),
                recent_turns=(start, end),
            )

        # No early turns to summarize
        return ContextWindow(
            content=context,
            total_tokens=total_tokens,
            includes_summary=False,
            recent_turns=(start, end),
        )

    def get_detection_context(
        self,
        turns: List[Dict[str, Any]],
    ) -> ContextWindow:
        """Get context window optimized for detection.

        Focuses on the end of the conversation where failures
        are most likely to manifest.

        Args:
            turns: All conversation turns

        Returns:
            ContextWindow optimized for failure detection
        """
        if not turns:
            return ContextWindow(content="", total_tokens=0)

        # Focus on the last turn
        last_turn_num = max(t.get("turn_number", 0) for t in turns)
        return self.get_context_for_turn(turns, last_turn_num)

    def chunk_for_batch_detection(
        self,
        turns: List[Dict[str, Any]],
    ) -> List[ContextWindow]:
        """Split conversation into overlapping chunks for batch detection.

        Each chunk has some overlap with adjacent chunks to ensure
        cross-turn patterns are detected.

        Args:
            turns: All conversation turns

        Returns:
            List of ContextWindows covering the full conversation
        """
        if not turns:
            return []

        chunks = []
        total_turns = len(turns)

        # Calculate chunk boundaries
        chunk_size = self.recent_turns_to_keep
        step = chunk_size - (self.overlap_tokens // 100)  # Rough overlap in turns

        i = 0
        while i < total_turns:
            end = min(i + chunk_size, total_turns)
            chunk_turns = turns[i:end]

            # Include first turn (task) in each chunk for context
            if i > 0:
                first_turn = [t for t in turns if t.get("turn_number") == 1]
                chunk_turns = first_turn + chunk_turns

            context = self.summarizer._format_turns(chunk_turns)

            chunks.append(ContextWindow(
                content=context,
                total_tokens=count_tokens(context),
                includes_summary=False,
                recent_turns=(i + 1, end),
            ))

            i += step

            # Prevent infinite loop
            if step <= 0:
                break

        return chunks


# Convenience instance
_default_summarizer: Optional[ConversationSummarizer] = None
_default_window_manager: Optional[SlidingWindowManager] = None


def get_summarizer() -> ConversationSummarizer:
    """Get default summarizer instance."""
    global _default_summarizer
    if _default_summarizer is None:
        _default_summarizer = ConversationSummarizer()
    return _default_summarizer


def get_window_manager() -> SlidingWindowManager:
    """Get default sliding window manager instance."""
    global _default_window_manager
    if _default_window_manager is None:
        _default_window_manager = SlidingWindowManager()
    return _default_window_manager
