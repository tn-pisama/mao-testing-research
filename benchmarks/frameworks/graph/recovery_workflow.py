"""Error recovery workflow: task → execute → [error: retry(3) → fallback] → complete."""

from typing import TypedDict, Literal
from langgraph.graph import END, StateGraph

from src.agents import (
    create_planner_agent,
    create_executor_agent,
    run_planner,
    run_executor,
    parse_execution_result,
    ToolStatus,
)


class RecoveryWorkflowState(TypedDict):
    """State passed between workflow nodes."""
    task: str
    context: str
    plan: str
    execution_result: str
    execution_status: str
    retry_count: int
    max_retries: int
    errors: list[str]
    fallback_attempted: bool
    fallback_result: str
    final_status: str
    partial_results: list[dict]
    _callbacks: list


async def plan_node(state: RecoveryWorkflowState) -> dict:
    """Create execution plan for the task."""
    callbacks = state.get("_callbacks", [])
    agent = create_planner_agent(callbacks=callbacks)

    plan = await run_planner(
        task=state["task"],
        agent=agent,
    )

    return {
        "plan": plan,
        "execution_status": "planned",
    }


async def execute_node(state: RecoveryWorkflowState) -> dict:
    """Execute the planned task."""
    callbacks = state.get("_callbacks", [])
    agent = create_executor_agent(callbacks=callbacks)

    # Include context from previous attempts if retrying
    context = state.get("context", "")
    if state.get("retry_count", 0) > 0:
        context += f"\n\nPrevious attempt failed with errors:\n" + "\n".join(state.get("errors", []))
        context += f"\n\nAttempt #{state.get('retry_count', 0) + 1}"

    execution_output = await run_executor(
        task=state["task"],
        context=context + f"\n\nExecution Plan:\n{state.get('plan', '')}",
        agent=agent,
    )

    result = parse_execution_result(execution_output)

    # Track partial results
    partial_results = state.get("partial_results", [])
    partial_results.append({
        "attempt": state.get("retry_count", 0) + 1,
        "success": result.success,
        "tool_calls": len(result.tool_calls),
        "errors": result.errors,
    })

    new_errors = state.get("errors", []) + result.errors

    return {
        "execution_result": execution_output,
        "execution_status": "success" if result.success else "failed",
        "errors": new_errors,
        "retry_count": state.get("retry_count", 0) + 1,
        "partial_results": partial_results,
    }


async def fallback_node(state: RecoveryWorkflowState) -> dict:
    """Execute fallback strategy when retries exhausted."""
    callbacks = state.get("_callbacks", [])
    agent = create_executor_agent(callbacks=callbacks)

    # Fallback uses simplified approach
    fallback_task = f"""FALLBACK MODE: Execute a simplified version of the task.

Original task: {state['task']}

Previous errors encountered:
{chr(10).join(state.get('errors', [])[:5])}

Instructions:
1. Attempt the task with minimal tool usage
2. If tools fail, provide best-effort output without tools
3. Document what could not be completed
4. Provide partial results if full completion is not possible"""

    fallback_output = await run_executor(
        task=fallback_task,
        available_tools=["web_search", "file_read"],  # Limited tools for fallback
        agent=agent,
    )

    result = parse_execution_result(fallback_output)

    return {
        "fallback_attempted": True,
        "fallback_result": fallback_output,
        "execution_status": "fallback_success" if result.success else "fallback_failed",
        "final_status": "partial" if result.success else "failed",
    }


async def complete_node(state: RecoveryWorkflowState) -> dict:
    """Mark task as complete and compile final results."""
    if state.get("execution_status") == "success":
        final_status = "success"
    elif state.get("fallback_attempted") and "success" in state.get("execution_status", ""):
        final_status = "partial_success"
    elif state.get("fallback_attempted"):
        final_status = "partial_failure"
    else:
        final_status = "failed"

    return {
        "final_status": final_status,
    }


def should_retry(state: RecoveryWorkflowState) -> Literal["retry", "fallback", "complete"]:
    """Determine if execution should retry, fallback, or complete."""
    status = state.get("execution_status", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    # Success - go to complete
    if status == "success":
        return "complete"

    # Max retries reached - try fallback
    if retry_count >= max_retries:
        return "fallback"

    # Still have retries - retry
    return "retry"


def fallback_result(state: RecoveryWorkflowState) -> Literal["complete"]:
    """Always go to complete after fallback."""
    return "complete"


def create_recovery_workflow() -> StateGraph:
    """Create the error recovery workflow.

    Flow: plan → execute → [success: complete, error: retry(3) → fallback → complete]

    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(RecoveryWorkflowState)

    # Add nodes
    workflow.add_node("plan", plan_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("fallback", fallback_node)
    workflow.add_node("complete", complete_node)

    # Define flow
    workflow.set_entry_point("plan")
    workflow.add_edge("plan", "execute")

    # After execution - decide retry/fallback/complete
    workflow.add_conditional_edges(
        "execute",
        should_retry,
        {
            "retry": "execute",  # Loop back for retry
            "fallback": "fallback",
            "complete": "complete",
        }
    )

    # After fallback - always complete
    workflow.add_edge("fallback", "complete")
    workflow.add_edge("complete", END)

    return workflow.compile()


async def run_recovery_workflow(
    task: str,
    context: str = "",
    max_retries: int = 3,
    callbacks: list | None = None,
) -> dict:
    """Execute the recovery workflow with retry and fallback logic.

    Args:
        task: The task to execute
        context: Optional context for the task
        max_retries: Maximum number of retry attempts (default 3)
        callbacks: Optional callback handlers for tracing

    Returns:
        Final state with execution results and recovery history
    """
    workflow = create_recovery_workflow()

    initial_state: RecoveryWorkflowState = {
        "task": task,
        "context": context,
        "plan": "",
        "execution_result": "",
        "execution_status": "pending",
        "retry_count": 0,
        "max_retries": max_retries,
        "errors": [],
        "fallback_attempted": False,
        "fallback_result": "",
        "final_status": "pending",
        "partial_results": [],
        "_callbacks": callbacks or [],
    }

    result = await workflow.ainvoke(initial_state)
    return result
