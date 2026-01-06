"""Executor agent that performs tool calls and task execution."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    PARTIAL = "partial"


@dataclass
class ToolCall:
    """Represents a tool call and its result."""
    name: str
    input: dict[str, Any]
    output: Any
    status: ToolStatus
    duration_ms: int = 0
    error_message: str = ""


@dataclass
class ExecutionResult:
    """Result of task execution."""
    success: bool
    output: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    retries: int = 0


# Simulated tool definitions
AVAILABLE_TOOLS = {
    "web_search": {
        "description": "Search the web for information",
        "parameters": ["query", "num_results"],
    },
    "code_execute": {
        "description": "Execute code and return results",
        "parameters": ["code", "language"],
    },
    "database_query": {
        "description": "Query a database",
        "parameters": ["query", "database"],
    },
    "file_read": {
        "description": "Read contents of a file",
        "parameters": ["path"],
    },
    "file_write": {
        "description": "Write contents to a file",
        "parameters": ["path", "content"],
    },
    "api_call": {
        "description": "Make an API request",
        "parameters": ["url", "method", "body"],
    },
}


def create_executor_agent(
    callbacks: list[BaseCallbackHandler] | None = None,
) -> ChatAnthropic:
    """Create an executor agent using Claude.

    Args:
        callbacks: Optional list of callback handlers for tracing

    Returns:
        Configured ChatAnthropic instance for execution tasks
    """
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        callbacks=callbacks,
    )


EXECUTOR_SYSTEM_PROMPT = """You are a task execution agent. Your role is to execute tasks using available tools and report results.

Available tools:
- web_search: Search the web for information
- code_execute: Execute code and return results
- database_query: Query a database
- file_read: Read contents of a file
- file_write: Write contents to a file
- api_call: Make an API request

When executing tasks:
1. Analyze what tools are needed
2. Plan the execution sequence
3. Execute each step and capture results
4. Handle errors gracefully
5. Report comprehensive results

Output format:
## Execution Plan
[Brief description of steps]

## Tool Calls
1. [tool_name]: [input] -> [result/status]
2. [tool_name]: [input] -> [result/status]
...

## Execution Result
[SUCCESS / PARTIAL / FAILED]

## Output
[Final output or results]

## Errors (if any)
- [Error 1]
- [Error 2]

Be thorough in execution and error handling."""


async def run_executor(
    task: str,
    available_tools: list[str] | None = None,
    agent: ChatAnthropic | None = None,
    context: str = "",
) -> str:
    """Execute a task using available tools.

    Args:
        task: The task to execute
        available_tools: List of tool names available for this execution
        agent: The executor agent instance
        context: Optional context from previous steps

    Returns:
        Execution report with tool calls and results
    """
    if agent is None:
        agent = create_executor_agent()

    tools_available = available_tools or list(AVAILABLE_TOOLS.keys())
    tools_desc = "\n".join([f"- {t}: {AVAILABLE_TOOLS[t]['description']}" for t in tools_available if t in AVAILABLE_TOOLS])

    context_section = f"\n\nContext from previous steps:\n{context}" if context else ""

    messages = [
        SystemMessage(content=EXECUTOR_SYSTEM_PROMPT),
        HumanMessage(content=f"Execute the following task using available tools.\n\nAvailable tools:\n{tools_desc}\n\nTask:\n{task}{context_section}"),
    ]

    response = await agent.ainvoke(messages)
    return response.content


def parse_execution_result(execution_text: str) -> ExecutionResult:
    """Parse execution text into structured ExecutionResult.

    Args:
        execution_text: Raw execution output from executor agent

    Returns:
        Structured ExecutionResult
    """
    import re

    # Default values
    success = False
    tool_calls = []
    errors = []

    # Parse execution result
    result_match = re.search(r"Execution Result[:\s]*\n?\s*(SUCCESS|PARTIAL|FAILED)", execution_text, re.IGNORECASE)
    if result_match:
        result_str = result_match.group(1).upper()
        success = result_str == "SUCCESS"

    # Parse tool calls
    tool_section = re.search(r"Tool Calls[:\s]*\n((?:\d+\.\s+.+\n?)+)", execution_text, re.IGNORECASE)
    if tool_section:
        tool_lines = tool_section.group(1).strip().split("\n")
        for line in tool_lines:
            # Parse format: "1. tool_name: input -> result"
            match = re.match(r"\d+\.\s+(\w+)[:\s]+(.+?)\s*->\s*(.+)", line.strip())
            if match:
                tool_calls.append(ToolCall(
                    name=match.group(1),
                    input={"raw": match.group(2)},
                    output=match.group(3),
                    status=ToolStatus.SUCCESS if "success" in match.group(3).lower() or "ok" in match.group(3).lower() else ToolStatus.ERROR,
                ))

    # Parse errors
    errors_section = re.search(r"Errors[^:]*:[:\s]*\n((?:[-*]\s+.+\n?)+)", execution_text, re.IGNORECASE)
    if errors_section:
        errors = [line.strip().lstrip("-* ") for line in errors_section.group(1).strip().split("\n") if line.strip()]

    return ExecutionResult(
        success=success,
        output=execution_text,
        tool_calls=tool_calls,
        errors=errors,
    )
