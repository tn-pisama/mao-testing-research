"""Planner agent that decomposes tasks into subtasks and creates execution plans."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler


def create_planner_agent(
    callbacks: list[BaseCallbackHandler] | None = None,
) -> ChatAnthropic:
    """Create a planner agent using Claude.

    Args:
        callbacks: Optional list of callback handlers for tracing

    Returns:
        Configured ChatAnthropic instance for planning tasks
    """
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        callbacks=callbacks,
    )


PLANNER_SYSTEM_PROMPT = """You are a task planning agent. Your role is to analyze complex tasks and break them down into clear, actionable subtasks.

When given a task:
1. Analyze the overall objective and requirements
2. Identify the key components and dependencies
3. Break down into ordered subtasks with clear deliverables
4. Assign appropriate agent roles for each subtask
5. Identify potential risks and mitigation strategies

Output format:
## Task Analysis
[Brief analysis of the task]

## Subtasks
1. [Subtask 1] - Assigned to: [agent_role] - Dependencies: [none/subtask_id]
2. [Subtask 2] - Assigned to: [agent_role] - Dependencies: [subtask_id]
...

## Resource Requirements
- [List of required tools, agents, data]

## Risk Assessment
- [Potential issues and mitigations]

Be thorough but practical. Avoid over-decomposition of simple tasks."""


async def run_planner(
    task: str,
    agent: ChatAnthropic | None = None,
    context: str = "",
) -> str:
    """Create an execution plan for a given task.

    Args:
        task: The task to plan
        agent: The planner agent instance
        context: Optional context from previous steps

    Returns:
        Execution plan with subtasks and assignments
    """
    if agent is None:
        agent = create_planner_agent()

    context_section = f"\n\nAdditional context:\n{context}" if context else ""

    messages = [
        SystemMessage(content=PLANNER_SYSTEM_PROMPT),
        HumanMessage(content=f"Create an execution plan for the following task:\n\n{task}{context_section}"),
    ]

    response = await agent.ainvoke(messages)
    return response.content
