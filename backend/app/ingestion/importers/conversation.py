"""Base conversation importer for multi-turn trace formats.

Handles parsing of various conversation formats into ConversationTrace:
- MAST-Data trajectory logs
- OpenAI messages format
- Claude conversation format
- Generic turn-based formats
"""

import json
import re
import uuid
import hashlib
from abc import abstractmethod
from typing import Iterator, Optional, List, Dict, Any

from app.ingestion.importers.base import BaseImporter
from app.ingestion.conversation_trace import ConversationTrace, ConversationTurnData
from app.ingestion.universal_trace import UniversalTrace


class ConversationImporter(BaseImporter):
    """Base class for conversation trace importers."""

    @property
    def format_name(self) -> str:
        return "conversation"

    def import_trace(self, content: str) -> UniversalTrace:
        """Import as UniversalTrace for compatibility.

        Converts conversation format to UniversalTrace by first parsing
        as ConversationTrace, then converting spans.
        """
        conv_trace = self.import_conversation(content)
        spans = conv_trace.to_universal_spans()

        trace = UniversalTrace(
            trace_id=conv_trace.trace_id,
            spans=spans,
            source_format=f"conversation:{conv_trace.source_format}",
            total_tokens=conv_trace.total_tokens,
            metadata={
                "framework": conv_trace.framework,
                "total_turns": conv_trace.total_turns,
                "participants": conv_trace.participants,
                **conv_trace.extra,
            },
        )
        return trace

    def import_spans(self, content: str) -> Iterator:
        """Import spans as iterator."""
        conv_trace = self.import_conversation(content)
        for turn in conv_trace.turns:
            yield turn.to_universal_span(conv_trace.trace_id)

    def import_conversation(self, content: str) -> ConversationTrace:
        """Parse conversation content into ConversationTrace.

        Detects format and delegates to appropriate parser.

        Args:
            content: Raw conversation content (JSON or trajectory text)

        Returns:
            Parsed ConversationTrace
        """
        # Detect format and delegate
        if self._is_mast_format(content):
            return self._parse_mast(content)
        elif self._is_openai_format(content):
            return self._parse_openai(content)
        elif self._is_claude_format(content):
            return self._parse_claude(content)
        else:
            return self._parse_generic(content)

    def _is_mast_format(self, content: str) -> bool:
        """Check if content is MAST trajectory format."""
        try:
            data = json.loads(content)
            return (
                "trajectory" in data.get("trace", {}) or
                "mast_annotation" in data or
                "mas_name" in data
            )
        except (json.JSONDecodeError, AttributeError):
            return False

    def _is_openai_format(self, content: str) -> bool:
        """Check if content is OpenAI messages format."""
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return all(
                    "role" in m and "content" in m
                    for m in data[:3] if isinstance(m, dict)
                )
            return "messages" in data
        except (json.JSONDecodeError, AttributeError):
            return False

    def _is_claude_format(self, content: str) -> bool:
        """Check if content is Claude conversation format."""
        try:
            data = json.loads(content)
            return (
                "conversation" in data or
                data.get("type") == "conversation"
            )
        except (json.JSONDecodeError, AttributeError):
            return False

    def _parse_mast(self, content: str) -> ConversationTrace:
        """Parse MAST trajectory format.

        MAST-Data contains trajectory logs from various frameworks
        with framework-specific conversation patterns.
        """
        data = json.loads(content)
        trajectory = data.get("trace", {}).get("trajectory", "")
        framework = data.get("mas_name", "unknown")

        # Use framework-specific parser
        turns = list(self._extract_turns_from_trajectory(trajectory, framework))

        trace = ConversationTrace(
            trace_id=data.get("trace_id", self._generate_id()),
            conversation_id=data.get("trace_id", self._generate_id()),
            framework=framework,
            source_format="mast",
        )

        for turn in turns:
            trace.add_turn(turn)

        # Store MAST annotations
        annotations = data.get("mast_annotation", {})
        if annotations:
            trace.extra["mast_annotations"] = annotations
            trace.extra["llm"] = data.get("llm_name")
            trace.extra["benchmark"] = data.get("benchmark_name")

        return trace

    def _extract_turns_from_trajectory(
        self,
        trajectory: str,
        framework: str
    ) -> Iterator[ConversationTurnData]:
        """Extract conversation turns from trajectory log.

        Dispatches to framework-specific extractors.
        """
        if framework == "ChatDev":
            yield from self._parse_chatdev_turns(trajectory)
        elif framework == "MetaGPT":
            yield from self._parse_metagpt_turns(trajectory)
        elif framework in ("AG2", "AutoGen"):
            yield from self._parse_autogen_turns(trajectory)
        elif framework == "Magentic":
            yield from self._parse_autogen_turns(trajectory)  # Similar format
        else:
            yield from self._parse_generic_turns(trajectory)

    def _parse_chatdev_turns(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """Parse ChatDev conversation format.

        Pattern: **Agent Name** says:\n content
        """
        # Pattern for ChatDev agent messages
        pattern = r'\*\*(\w+)\*\*[^:]*:\s*\n(.*?)(?=\*\*\w+\*\*|\[Software Info\]|\Z)'

        for i, match in enumerate(re.finditer(pattern, trajectory, re.DOTALL)):
            agent_name = match.group(1)
            content = match.group(2).strip()[:4096]  # Truncate to 4KB

            if content and len(content) > 10:
                yield ConversationTurnData(
                    turn_id=f"chatdev_{i}",
                    turn_number=i + 1,
                    role="agent",
                    participant_id=f"chatdev:{agent_name}",
                    content=content,
                )

    def _parse_metagpt_turns(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """Parse MetaGPT conversation format.

        Pattern: [Action] CONTENT:\n content
        """
        pattern = r'\[(\w+)\]\s*\nCONTENT:\s*\n(.*?)(?=\n\[\w+\]|\Z)'

        for i, match in enumerate(re.finditer(pattern, trajectory, re.DOTALL)):
            action = match.group(1)
            content = match.group(2).strip()[:4096]

            if content and len(content) > 10:
                yield ConversationTurnData(
                    turn_id=f"metagpt_{i}",
                    turn_number=i + 1,
                    role="agent",
                    participant_id=f"metagpt:{action}",
                    content=content,
                )

    def _parse_autogen_turns(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """Parse AutoGen/AG2/Magentic conversation format.

        Pattern: Agent_Name (to Recipient_Name):\n content
        """
        pattern = r'(\w+)\s*\(to\s*(\w+)\):\s*\n(.*?)(?=\n\w+\s*\(to|\n-{5,}|\Z)'

        for i, match in enumerate(re.finditer(pattern, trajectory, re.DOTALL)):
            sender = match.group(1)
            recipient = match.group(2)
            content = match.group(3).strip()[:4096]

            if content and len(content) > 10:
                # Determine role based on sender name
                role = "user" if sender.lower() in ("user", "human", "admin") else "agent"

                yield ConversationTurnData(
                    turn_id=f"autogen_{i}",
                    turn_number=i + 1,
                    role=role,
                    participant_id=f"autogen:{sender}",
                    content=content,
                    extra={"recipient": recipient},
                )

    def _parse_generic_turns(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """Generic turn parser for unknown formats.

        Tries common patterns in order of specificity.
        """
        patterns = [
            # [Agent]: content
            (r'\[(\w+)\]:\s*(.*?)(?=\[\w+\]|\Z)', "bracket"),
            # Agent: content
            (r'^(\w+):\s*(.*?)(?=\n\w+:|\Z)', "colon"),
            # --- Agent ---\n content
            (r'-{3,}\s*(\w+)\s*-{3,}\s*\n(.*?)(?=-{3,}|\Z)', "dashes"),
        ]

        for pattern, style in patterns:
            matches = list(re.finditer(pattern, trajectory, re.DOTALL | re.MULTILINE))
            if len(matches) >= 2:  # Found meaningful turns
                for i, match in enumerate(matches):
                    agent = match.group(1)
                    content = match.group(2).strip()[:4096]

                    if content and len(content) > 10:
                        role = "user" if agent.lower() in ("user", "human") else "agent"
                        yield ConversationTurnData(
                            turn_id=f"generic_{style}_{i}",
                            turn_number=i + 1,
                            role=role,
                            participant_id=agent,
                            content=content,
                        )
                return

        # Fallback: split by double newlines and treat as turns
        segments = re.split(r'\n\n+', trajectory)
        for i, segment in enumerate(segments[:100]):  # Max 100 turns
            segment = segment.strip()[:4096]
            if len(segment) > 50:
                yield ConversationTurnData(
                    turn_id=f"segment_{i}",
                    turn_number=i + 1,
                    role="agent",
                    participant_id="unknown",
                    content=segment,
                )

    def _parse_openai(self, content: str) -> ConversationTrace:
        """Parse OpenAI messages format."""
        data = json.loads(content)
        messages = data if isinstance(data, list) else data.get("messages", [])

        trace = ConversationTrace(
            trace_id=self._generate_id(),
            conversation_id=self._generate_id(),
            framework="openai",
            source_format="openai",
        )

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "user")
            content_val = msg.get("content", "")

            # Handle content blocks (vision, etc.)
            if isinstance(content_val, list):
                text_parts = [
                    c.get("text", "") for c in content_val
                    if isinstance(c, dict) and c.get("type") == "text"
                ]
                content_val = "\n".join(text_parts)

            turn = ConversationTurnData(
                turn_id=f"openai_{i}",
                turn_number=i + 1,
                role="agent" if role == "assistant" else role,
                participant_id=msg.get("name", role),
                content=str(content_val)[:4096],
                tool_calls=msg.get("tool_calls"),
            )
            trace.add_turn(turn)

        return trace

    def _parse_claude(self, content: str) -> ConversationTrace:
        """Parse Claude conversation format."""
        data = json.loads(content)
        messages = data.get("conversation", data.get("messages", []))

        trace = ConversationTrace(
            trace_id=data.get("id", self._generate_id()),
            conversation_id=data.get("id", self._generate_id()),
            framework="claude",
            source_format="claude",
        )

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "user")
            content_val = msg.get("content", "")

            # Handle content blocks
            if isinstance(content_val, list):
                text_parts = [
                    c.get("text", "") for c in content_val
                    if isinstance(c, dict) and c.get("type") == "text"
                ]
                content_val = "\n".join(text_parts)

            turn = ConversationTurnData(
                turn_id=f"claude_{i}",
                turn_number=i + 1,
                role="agent" if role == "assistant" else role,
                participant_id=role,
                content=str(content_val)[:4096],
            )
            trace.add_turn(turn)

        return trace

    def _parse_generic(self, content: str) -> ConversationTrace:
        """Parse generic/unknown format."""
        trace = ConversationTrace(
            trace_id=self._generate_id(),
            conversation_id=self._generate_id(),
            framework="generic",
            source_format="generic",
        )

        # Try JSON first
        try:
            data = json.loads(content)
            if isinstance(data, list):
                for i, item in enumerate(data[:100]):
                    if isinstance(item, dict):
                        turn = ConversationTurnData(
                            turn_id=f"generic_{i}",
                            turn_number=i + 1,
                            role=item.get("role", "agent"),
                            participant_id=item.get("agent", item.get("name", "unknown")),
                            content=str(item.get("content", item.get("text", str(item))))[:4096],
                        )
                        trace.add_turn(turn)
                return trace
        except json.JSONDecodeError:
            pass

        # Fall back to text parsing
        for turn in self._parse_generic_turns(content):
            trace.add_turn(turn)

        return trace

    def _generate_id(self) -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())
