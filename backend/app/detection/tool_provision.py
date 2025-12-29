"""
F4: Inadequate Tool Provision Detection (MAST Taxonomy)
========================================================

Detects when an agent lacks the tools needed to complete a task.
This occurs at the system design level when:
- Agent attempts to use tools it doesn't have
- Agent hallucinates tool names or capabilities
- Task requires tools not provisioned to the agent
- Agent works around missing tools in suboptimal ways
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Set, Dict, Any

logger = logging.getLogger(__name__)


class ProvisionSeverity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class ProvisionIssueType(str, Enum):
    MISSING_TOOL = "missing_tool"
    HALLUCINATED_TOOL = "hallucinated_tool"
    TOOL_CAPABILITY_GAP = "tool_capability_gap"
    WORKAROUND_DETECTED = "workaround_detected"
    TOOL_CALL_FAILURE = "tool_call_failure"


@dataclass
class ToolProvisionIssue:
    issue_type: ProvisionIssueType
    tool_name: str
    description: str
    severity: ProvisionSeverity


@dataclass
class ToolProvisionResult:
    detected: bool
    severity: ProvisionSeverity
    confidence: float
    issues: List[ToolProvisionIssue] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    attempted_tools: List[str] = field(default_factory=list)
    missing_tools: List[str] = field(default_factory=list)
    hallucinated_tools: List[str] = field(default_factory=list)
    explanation: str = ""
    suggested_fix: Optional[str] = None


class ToolProvisionDetector:
    """
    Detects F4: Inadequate Tool Provision - agent lacks needed tools.

    Analyzes agent behavior and tool calls to identify gaps between
    required capabilities and available tools.
    """

    # Common tool categories and their typical names
    TOOL_CATEGORIES = {
        "web_search": ["search", "web_search", "google", "bing", "duckduckgo", "browse"],
        "file_ops": ["read_file", "write_file", "list_files", "delete_file", "file_reader"],
        "code_exec": ["python", "execute_code", "run_code", "shell", "bash", "terminal"],
        "api_calls": ["http_request", "api_call", "fetch", "curl", "request"],
        "database": ["sql", "query_db", "database", "db_query", "execute_sql"],
        "calculator": ["calculator", "calculate", "math", "compute"],
        "email": ["send_email", "email", "mail", "smtp"],
        "calendar": ["calendar", "schedule", "create_event", "book_meeting"],
    }

    # Patterns indicating tool need without having it
    WORKAROUND_PATTERNS = [
        (r"I don't have access to", "explicit_admission"),
        (r"I cannot (?:browse|search|access) the (?:web|internet)", "web_limitation"),
        (r"I'm unable to (?:execute|run) code", "code_limitation"),
        (r"I cannot (?:send|read) (?:emails?|mail)", "email_limitation"),
        (r"I don't have (?:a |the )?(?:tool|ability|capability) to", "general_limitation"),
        (r"(?:As an AI|Unfortunately),? I (?:can't|cannot|am unable to)", "ai_limitation"),
        (r"I'll (?:simulate|pretend|imagine|approximate)", "simulation_workaround"),
        (r"(?:Let me|I'll) (?:assume|estimate|guess)", "estimation_workaround"),
        (r"Based on my (?:training|knowledge) (?:cutoff|data)", "knowledge_limitation"),
    ]

    # Patterns suggesting hallucinated tool usage
    HALLUCINATION_PATTERNS = [
        r"(?:using|calling|invoking) (?:the )?(\w+_tool)",
        r"(?:let me |I'll )(?:use|call|invoke) (\w+)",
        r"(?:executing|running) (\w+)\(\)",
        r"tool: (\w+)",
    ]

    def __init__(
        self,
        known_tools: Optional[List[str]] = None,
        strict_mode: bool = False,
    ):
        self.known_tools = set(known_tools or [])
        self.strict_mode = strict_mode

    def _normalize_tool_name(self, name: str) -> str:
        """Normalize tool name for comparison."""
        return name.lower().strip().replace("-", "_").replace(" ", "_")

    def _extract_tool_mentions(self, text: str) -> Set[str]:
        """Extract tool names mentioned in text."""
        tools = set()

        for pattern in self.HALLUCINATION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                normalized = self._normalize_tool_name(match)
                if len(normalized) > 2:
                    tools.add(normalized)

        # Also check for common tool names directly
        for category, names in self.TOOL_CATEGORIES.items():
            for name in names:
                if re.search(rf'\b{name}\b', text, re.IGNORECASE):
                    tools.add(self._normalize_tool_name(name))

        return tools

    def _detect_workarounds(self, text: str) -> List[tuple]:
        """Detect workaround patterns indicating missing tools."""
        workarounds = []

        for pattern, workaround_type in self.WORKAROUND_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                workarounds.append((pattern, workaround_type))

        return workarounds

    def _infer_needed_tools(self, task: str) -> Set[str]:
        """Infer what tools might be needed based on task description."""
        needed = set()
        task_lower = task.lower()

        # Web search indicators
        if any(w in task_lower for w in ["search", "find online", "look up", "google", "current", "latest", "today's"]):
            needed.add("web_search")

        # File operation indicators
        if any(w in task_lower for w in ["read file", "write file", "save to", "load from", "file"]):
            needed.add("file_ops")

        # Code execution indicators
        if any(w in task_lower for w in ["run code", "execute", "python", "script", "calculate"]):
            needed.add("code_exec")

        # API indicators
        if any(w in task_lower for w in ["api", "fetch data", "http", "endpoint", "request"]):
            needed.add("api_calls")

        # Database indicators
        if any(w in task_lower for w in ["database", "sql", "query", "table"]):
            needed.add("database")

        # Email indicators
        if any(w in task_lower for w in ["send email", "email", "mail to"]):
            needed.add("email")

        # Calendar indicators
        if any(w in task_lower for w in ["schedule", "calendar", "meeting", "appointment"]):
            needed.add("calendar")

        return needed

    def _analyze_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
    ) -> tuple[List[str], List[str]]:
        """Analyze tool calls for failures and issues."""
        successful = []
        failed = []

        for call in tool_calls:
            tool_name = call.get("name", call.get("tool", "unknown"))
            status = call.get("status", call.get("result", {}).get("status", ""))
            error = call.get("error", call.get("result", {}).get("error", ""))

            if error or status in ["failed", "error", "not_found"]:
                failed.append(tool_name)
            else:
                successful.append(tool_name)

        return successful, failed

    def detect(
        self,
        task: str,
        agent_output: str,
        available_tools: Optional[List[str]] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        context: Optional[str] = None,
    ) -> ToolProvisionResult:
        """
        Detect inadequate tool provision.

        Args:
            task: The task the agent was asked to perform
            agent_output: The agent's response/output
            available_tools: List of tools available to the agent
            tool_calls: List of tool call attempts with results
            context: Additional context

        Returns:
            ToolProvisionResult with detection outcome
        """
        issues = []
        available = set(self._normalize_tool_name(t) for t in (available_tools or []))
        available.update(self.known_tools)

        # Analyze tool calls if provided
        attempted = set()
        failed_tools = []
        if tool_calls:
            successful, failed_tools = self._analyze_tool_calls(tool_calls)
            attempted.update(self._normalize_tool_name(t) for t in successful + failed_tools)

            # Check for tool call failures
            for tool in failed_tools:
                normalized = self._normalize_tool_name(tool)
                if normalized not in available:
                    issues.append(ToolProvisionIssue(
                        issue_type=ProvisionIssueType.TOOL_CALL_FAILURE,
                        tool_name=tool,
                        description=f"Tool '{tool}' call failed - tool may not exist",
                        severity=ProvisionSeverity.MODERATE,
                    ))

        # Extract tools mentioned in output
        mentioned_tools = self._extract_tool_mentions(agent_output)
        attempted.update(mentioned_tools)

        # Detect hallucinated tools
        hallucinated = []
        if available:  # Only check if we know what's available
            for tool in mentioned_tools:
                if tool not in available and not any(tool in cat for cat in self.TOOL_CATEGORIES.values()):
                    hallucinated.append(tool)
                    issues.append(ToolProvisionIssue(
                        issue_type=ProvisionIssueType.HALLUCINATED_TOOL,
                        tool_name=tool,
                        description=f"Agent referenced non-existent tool '{tool}'",
                        severity=ProvisionSeverity.MODERATE,
                    ))

        # Detect workarounds indicating missing tools
        workarounds = self._detect_workarounds(agent_output)
        for pattern, workaround_type in workarounds:
            issues.append(ToolProvisionIssue(
                issue_type=ProvisionIssueType.WORKAROUND_DETECTED,
                tool_name=workaround_type,
                description=f"Agent acknowledged limitation: {workaround_type}",
                severity=ProvisionSeverity.MINOR,
            ))

        # Infer needed tools from task
        needed_tools = self._infer_needed_tools(task)
        missing = []

        for needed_category in needed_tools:
            category_tools = set(self.TOOL_CATEGORIES.get(needed_category, []))
            has_category_tool = bool(available & category_tools) if available else True

            if not has_category_tool and available:
                missing.append(needed_category)
                issues.append(ToolProvisionIssue(
                    issue_type=ProvisionIssueType.MISSING_TOOL,
                    tool_name=needed_category,
                    description=f"Task likely requires {needed_category} capability",
                    severity=ProvisionSeverity.SEVERE if self.strict_mode else ProvisionSeverity.MODERATE,
                ))

        # Determine overall result
        detected = len(issues) > 0

        if not detected:
            return ToolProvisionResult(
                detected=False,
                severity=ProvisionSeverity.NONE,
                confidence=0.9,
                available_tools=list(available),
                attempted_tools=list(attempted),
                missing_tools=[],
                hallucinated_tools=[],
                explanation="No tool provision issues detected",
            )

        # Calculate severity based on issues
        if any(i.severity == ProvisionSeverity.CRITICAL for i in issues):
            severity = ProvisionSeverity.CRITICAL
        elif any(i.severity == ProvisionSeverity.SEVERE for i in issues):
            severity = ProvisionSeverity.SEVERE
        elif any(i.severity == ProvisionSeverity.MODERATE for i in issues):
            severity = ProvisionSeverity.MODERATE
        else:
            severity = ProvisionSeverity.MINOR

        # Calculate confidence
        confidence = min(0.9, 0.5 + (len(issues) * 0.1))

        # Build explanation
        issue_types = set(i.issue_type.value for i in issues)
        explanation = f"Detected {len(issues)} tool provision issue(s): {', '.join(issue_types)}"

        # Suggest fix
        if missing:
            suggested_fix = f"Add tools for: {', '.join(missing)}"
        elif hallucinated:
            suggested_fix = f"Agent referenced non-existent tools: {', '.join(hallucinated)}"
        elif workarounds:
            suggested_fix = "Agent is working around missing capabilities - consider adding needed tools"
        else:
            suggested_fix = "Review agent tool configuration"

        return ToolProvisionResult(
            detected=True,
            severity=severity,
            confidence=confidence,
            issues=issues,
            available_tools=list(available),
            attempted_tools=list(attempted),
            missing_tools=missing,
            hallucinated_tools=hallucinated,
            explanation=explanation,
            suggested_fix=suggested_fix,
        )


# Singleton instance
tool_provision_detector = ToolProvisionDetector()
