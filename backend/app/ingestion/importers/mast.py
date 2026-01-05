"""MAST-Data specific importer with framework extractors.

UC Berkeley MAST-Data contains trajectory logs from multiple
multi-agent frameworks with standardized failure annotations.

Supported frameworks:
- ChatDev: Software development agents
- MetaGPT: Multi-role software company
- AG2/AutoGen: Conversational agents
- Magentic: Magnetic-one framework
- OpenManus: Open-source agent framework
- AppWorld: Application interaction agents
- HyperAgent: Hierarchical agents

Reference: https://github.com/KevinHuuu/MAST
"""

import json
import re
from typing import Dict, List, Optional, Iterator, Any

from app.ingestion.importers.conversation import ConversationImporter
from app.ingestion.conversation_trace import ConversationTrace, ConversationTurnData


class MASTImporter(ConversationImporter):
    """Import UC Berkeley MAST-Data traces with framework-specific parsing."""

    # MAST annotation code to failure mode mapping
    ANNOTATION_MAP = {
        # Planning failures (Category 1)
        "1.1": "F1",   # Specification Mismatch
        "1.2": "F2",   # Poor Task Decomposition
        "1.3": "F3",   # Resource Misallocation
        "1.4": "F4",   # Inadequate Tool Provision
        "1.5": "F5",   # Flawed Workflow Design
        # Execution failures (Category 2)
        "2.1": "F6",   # Task Derailment
        "2.2": "F7",   # Context Neglect
        "2.3": "F8",   # Information Withholding
        "2.4": "F9",   # Role Usurpation
        "2.5": "F10",  # Communication Breakdown
        "2.6": "F11",  # Coordination Failure
        # Verification failures (Category 3)
        "3.1": "F12",  # Output Validation Failure
        "3.2": "F13",  # Quality Gate Bypass
        "3.3": "F14",  # Completion Misjudgment
    }

    # Reverse mapping for lookup
    FAILURE_MODE_TO_ANNOTATION = {v: k for k, v in ANNOTATION_MAP.items()}

    @property
    def format_name(self) -> str:
        return "mast"

    def import_conversation(self, content: str) -> ConversationTrace:
        """Parse MAST record to ConversationTrace."""
        data = json.loads(content)

        framework = data.get("mas_name", "unknown")
        trajectory = data.get("trace", {}).get("trajectory", "")
        annotations = data.get("mast_annotation", {})

        # Parse trajectory with framework-specific extractor
        trace = self._parse_trajectory(
            trajectory=trajectory,
            framework=framework,
            trace_id=data.get("trace_id"),
        )

        # Store source info
        trace.source_format = "mast"
        trace.extra = {
            "mast_annotations": self._parse_annotations(annotations),
            "raw_annotations": annotations,
            "llm": data.get("llm_name"),
            "benchmark": data.get("benchmark_name"),
            "task_id": data.get("task_id"),
        }

        # Extract and prepend task as system turn
        task = self._extract_task(trajectory, framework, data)
        if task and (not trace.turns or trace.turns[0].role != "system"):
            task_turn = ConversationTurnData(
                turn_id="turn_task",
                turn_number=0,
                role="system",
                participant_id="system",
                content=task,
            )
            # Insert at beginning and renumber
            trace.turns.insert(0, task_turn)
            for i, t in enumerate(trace.turns):
                t.turn_number = i + 1
            trace.total_turns = len(trace.turns)

        return trace

    def _parse_trajectory(
        self,
        trajectory: str,
        framework: str,
        trace_id: Optional[str] = None,
    ) -> ConversationTrace:
        """Parse trajectory using framework-specific extractor."""
        trace = ConversationTrace(
            trace_id=trace_id or self._generate_id(),
            conversation_id=trace_id or self._generate_id(),
            framework=framework,
        )

        # Get framework-specific extractor
        extractor = self._get_extractor(framework)
        turns = list(extractor(trajectory))

        for turn in turns:
            trace.add_turn(turn)

        return trace

    def _get_extractor(self, framework: str):
        """Get framework-specific turn extractor."""
        extractors = {
            "ChatDev": self._extract_chatdev,
            "MetaGPT": self._extract_metagpt,
            "AG2": self._extract_ag2,
            "AutoGen": self._extract_ag2,
            "Magentic": self._extract_magentic,
            "OpenManus": self._extract_openmanus,
            "AppWorld": self._extract_appworld,
            "HyperAgent": self._extract_hyperagent,
            "CAMEL": self._extract_camel,
            "CrewAI": self._extract_crewai,
        }
        return extractors.get(framework, self._extract_generic)

    def _extract_chatdev(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """ChatDev: **Agent** says: ... format

        ChatDev uses role-based software development agents:
        CEO, CTO, CPO, Programmer, Reviewer, Tester, etc.
        """
        # Primary pattern
        pattern = r'\*\*(\w+)\*\*[^:]*:\s*\n(.*?)(?=\*\*\w+\*\*|\[Software Info\]|\[ChatDev|\Z)'

        matches = list(re.finditer(pattern, trajectory, re.DOTALL))

        if not matches:
            # Fallback pattern for variant formats
            pattern = r'(\w+):\s*\n(.*?)(?=\n\w+:|\Z)'
            matches = list(re.finditer(pattern, trajectory, re.DOTALL))

        for i, match in enumerate(matches):
            agent = match.group(1)
            content = match.group(2).strip()

            # Skip empty or very short content
            if not content or len(content) < 20:
                continue

            # Truncate to 4KB
            content = content[:4096]

            yield ConversationTurnData(
                turn_id=f"chatdev_{i}",
                turn_number=i + 1,
                role="agent",
                participant_id=f"chatdev:{agent}",
                content=content,
                extra={"agent_role": agent},
            )

    def _extract_metagpt(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """MetaGPT: [Action] CONTENT:\n ... format

        MetaGPT uses action-based logging with roles like:
        ProductManager, Architect, ProjectManager, Engineer
        """
        # Pattern for action blocks
        pattern = r'\[(\w+)\]\s*(?:CONTENT:)?\s*\n(.*?)(?=\n\[\w+\]|\Z)'

        matches = list(re.finditer(pattern, trajectory, re.DOTALL))

        if not matches:
            # Try alternative format: Role: content
            pattern = r'(ProductManager|Architect|ProjectManager|Engineer|QA):\s*\n?(.*?)(?=\n(?:ProductManager|Architect|ProjectManager|Engineer|QA):|\Z)'
            matches = list(re.finditer(pattern, trajectory, re.DOTALL | re.IGNORECASE))

        for i, match in enumerate(matches):
            action = match.group(1)
            content = match.group(2).strip()[:4096]

            if content and len(content) > 20:
                yield ConversationTurnData(
                    turn_id=f"metagpt_{i}",
                    turn_number=i + 1,
                    role="agent",
                    participant_id=f"metagpt:{action}",
                    content=content,
                    extra={"action": action},
                )

    def _extract_ag2(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """AG2/AutoGen: Agent (to Recipient):\n content

        AutoGen uses conversational agents with explicit routing.
        """
        pattern = r'(\w+)\s*\(to\s*(\w+)\):\s*\n(.*?)(?=\n\w+\s*\(to|\n-{5,}|TERMINATE|\Z)'

        for i, match in enumerate(re.finditer(pattern, trajectory, re.DOTALL)):
            sender = match.group(1)
            recipient = match.group(2)
            content = match.group(3).strip()[:4096]

            if content and len(content) > 10:
                # Determine role
                role = "user" if sender.lower() in ("user", "human", "admin", "user_proxy") else "agent"

                yield ConversationTurnData(
                    turn_id=f"ag2_{i}",
                    turn_number=i + 1,
                    role=role,
                    participant_id=f"ag2:{sender}",
                    content=content,
                    extra={"recipient": recipient, "sender": sender},
                )

    def _extract_magentic(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """Magentic-One: Similar to AG2 but with specialized agents.

        Uses agents like Orchestrator, WebSurfer, FileSurfer, Coder, ComputerTerminal
        """
        # Try AG2 pattern first
        ag2_turns = list(self._extract_ag2(trajectory))
        if ag2_turns:
            for turn in ag2_turns:
                turn.turn_id = turn.turn_id.replace("ag2_", "magentic_")
                turn.participant_id = turn.participant_id.replace("ag2:", "magentic:")
                yield turn
            return

        # Magentic-specific patterns
        pattern = r'(Orchestrator|WebSurfer|FileSurfer|Coder|ComputerTerminal|UserProxy):\s*\n?(.*?)(?=\n(?:Orchestrator|WebSurfer|FileSurfer|Coder|ComputerTerminal|UserProxy):|\Z)'

        for i, match in enumerate(re.finditer(pattern, trajectory, re.DOTALL)):
            agent = match.group(1)
            content = match.group(2).strip()[:4096]

            if content and len(content) > 10:
                yield ConversationTurnData(
                    turn_id=f"magentic_{i}",
                    turn_number=i + 1,
                    role="agent",
                    participant_id=f"magentic:{agent}",
                    content=content,
                )

    def _extract_openmanus(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """OpenManus: Tool-use focused format."""
        # Try to find structured tool calls
        tool_pattern = r'Tool:\s*(\w+)\s*\nInput:\s*(.*?)\nOutput:\s*(.*?)(?=\nTool:|\Z)'

        tool_matches = list(re.finditer(tool_pattern, trajectory, re.DOTALL))

        if tool_matches:
            for i, match in enumerate(tool_matches):
                tool_name = match.group(1)
                tool_input = match.group(2).strip()
                tool_output = match.group(3).strip()

                content = f"Tool: {tool_name}\nInput: {tool_input}\nOutput: {tool_output}"

                yield ConversationTurnData(
                    turn_id=f"openmanus_{i}",
                    turn_number=i + 1,
                    role="tool",
                    participant_id=f"openmanus:{tool_name}",
                    content=content[:4096],
                    extra={"tool_name": tool_name},
                )
        else:
            # Fall back to generic
            yield from self._extract_generic(trajectory)

    def _extract_appworld(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """AppWorld: Application interaction format."""
        # AppWorld often has API call patterns
        api_pattern = r'(GET|POST|PUT|DELETE|PATCH)\s+(/\S+).*?\n(.*?)(?=\n(?:GET|POST|PUT|DELETE|PATCH)|\Z)'

        api_matches = list(re.finditer(api_pattern, trajectory, re.DOTALL))

        if api_matches:
            for i, match in enumerate(api_matches):
                method = match.group(1)
                endpoint = match.group(2)
                response = match.group(3).strip()

                content = f"{method} {endpoint}\n{response}"

                yield ConversationTurnData(
                    turn_id=f"appworld_{i}",
                    turn_number=i + 1,
                    role="tool",
                    participant_id=f"appworld:api",
                    content=content[:4096],
                    extra={"method": method, "endpoint": endpoint},
                )
        else:
            yield from self._extract_generic(trajectory)

    def _extract_hyperagent(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """HyperAgent: Hierarchical agent format."""
        # HyperAgent uses hierarchical task decomposition
        task_pattern = r'(?:Task|Subtask)\s*(\d+)?:\s*(.*?)(?=\n(?:Task|Subtask)|\Z)'

        for i, match in enumerate(re.finditer(task_pattern, trajectory, re.DOTALL)):
            task_num = match.group(1) or str(i)
            content = match.group(2).strip()[:4096]

            if content and len(content) > 20:
                yield ConversationTurnData(
                    turn_id=f"hyperagent_{i}",
                    turn_number=i + 1,
                    role="agent",
                    participant_id=f"hyperagent:task_{task_num}",
                    content=content,
                )

        # If no tasks found, fall back to generic
        if i == 0:
            yield from self._extract_generic(trajectory)

    def _extract_camel(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """CAMEL: Role-playing conversation format."""
        # CAMEL uses AI User and AI Assistant roles
        pattern = r'(AI User|AI Assistant|User|Assistant):\s*\n?(.*?)(?=\n(?:AI User|AI Assistant|User|Assistant):|\Z)'

        for i, match in enumerate(re.finditer(pattern, trajectory, re.DOTALL)):
            role_name = match.group(1)
            content = match.group(2).strip()[:4096]

            if content and len(content) > 10:
                role = "user" if "user" in role_name.lower() else "agent"
                yield ConversationTurnData(
                    turn_id=f"camel_{i}",
                    turn_number=i + 1,
                    role=role,
                    participant_id=f"camel:{role_name.replace(' ', '_')}",
                    content=content,
                )

    def _extract_crewai(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """CrewAI: Task-based agent collaboration."""
        # CrewAI logs agent tasks and outputs
        pattern = r'\[Agent:\s*(\w+)\]\s*(.*?)(?=\[Agent:|\[Task|\Z)'

        matches = list(re.finditer(pattern, trajectory, re.DOTALL))

        if matches:
            for i, match in enumerate(matches):
                agent = match.group(1)
                content = match.group(2).strip()[:4096]

                if content and len(content) > 10:
                    yield ConversationTurnData(
                        turn_id=f"crewai_{i}",
                        turn_number=i + 1,
                        role="agent",
                        participant_id=f"crewai:{agent}",
                        content=content,
                    )
        else:
            yield from self._extract_generic(trajectory)

    def _extract_generic(self, trajectory: str) -> Iterator[ConversationTurnData]:
        """Generic fallback extractor."""
        # Try multiple patterns
        patterns = [
            (r'\[(\w+)\]:\s*(.*?)(?=\[\w+\]:|\Z)', "bracket"),
            (r'^(\w+):\s*(.*?)(?=\n\w+:|\Z)', "colon"),
            (r'-{3,}\s*(\w+)\s*-{3,}\s*\n(.*?)(?=-{3,}|\Z)', "dashes"),
        ]

        for pattern, style in patterns:
            matches = list(re.finditer(pattern, trajectory, re.DOTALL | re.MULTILINE))
            if len(matches) >= 2:
                for i, match in enumerate(matches):
                    agent = match.group(1)
                    content = match.group(2).strip()[:4096]

                    if content and len(content) > 20:
                        yield ConversationTurnData(
                            turn_id=f"generic_{style}_{i}",
                            turn_number=i + 1,
                            role="agent",
                            participant_id=agent,
                            content=content,
                        )
                return

        # Last resort: split by paragraphs
        segments = re.split(r'\n\n+', trajectory)
        for i, segment in enumerate(segments[:100]):
            segment = segment.strip()[:4096]
            if len(segment) > 50:
                yield ConversationTurnData(
                    turn_id=f"segment_{i}",
                    turn_number=i + 1,
                    role="agent",
                    participant_id="unknown",
                    content=segment,
                )

    def _extract_task(
        self,
        trajectory: str,
        framework: str,
        data: Dict[str, Any]
    ) -> Optional[str]:
        """Extract initial task/prompt from trajectory or metadata."""
        # First check metadata
        task = data.get("task") or data.get("query") or data.get("prompt")
        if task:
            return str(task)[:2000]

        # Framework-specific task patterns
        patterns = {
            "ChatDev": r'\*\*task_prompt\*\*:\s*([^\n|]+)',
            "MetaGPT": r'UserRequirement\s*\nCONTENT:\s*\n(.+?)(?:\n\n|\n\[)',
            "AG2": r'(?:problem_statement|task):\s*(.+?)(?:\n[a-z_]+:|$)',
            "AutoGen": r'(?:problem_statement|task):\s*(.+?)(?:\n[a-z_]+:|$)',
        }

        pattern = patterns.get(framework) or r'(?:Task|Query|Prompt|Problem):\s*(.+?)(?:\n\n|\n\[|$)'
        match = re.search(pattern, trajectory, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()[:2000]

        return None

    def _parse_annotations(self, annotations: Dict[str, Any]) -> Dict[str, bool]:
        """Convert MAST annotations to failure mode flags.

        Args:
            annotations: Raw MAST annotation dict

        Returns:
            Dict mapping failure mode codes (F1-F14) to boolean flags
        """
        result = {}
        for code, value in annotations.items():
            mode = self.ANNOTATION_MAP.get(str(code))
            if mode:
                # Handle various value formats
                if isinstance(value, bool):
                    result[mode] = value
                elif isinstance(value, (int, float)):
                    result[mode] = value > 0
                elif isinstance(value, str):
                    result[mode] = value.lower() in ("true", "yes", "1")
                else:
                    result[mode] = bool(value)
        return result

    def get_failure_modes(self, trace: ConversationTrace) -> List[str]:
        """Get list of failure modes present in trace.

        Args:
            trace: Parsed ConversationTrace

        Returns:
            List of failure mode codes (e.g., ["F1", "F7", "F12"])
        """
        annotations = trace.extra.get("mast_annotations", {})
        return [mode for mode, present in annotations.items() if present]

    def get_annotation_code(self, failure_mode: str) -> Optional[str]:
        """Get MAST annotation code for a failure mode.

        Args:
            failure_mode: Failure mode code (e.g., "F7")

        Returns:
            MAST annotation code (e.g., "2.2") or None
        """
        return self.FAILURE_MODE_TO_ANNOTATION.get(failure_mode)
