"""Hierarchical delegation workflow: supervisor → [planner → executors] → aggregator → validator."""

from typing import TypedDict, Literal
from langgraph.graph import END, StateGraph

from src.agents import (
    create_planner_agent,
    create_executor_agent,
    create_validator_agent,
    create_writer_agent,
    run_planner,
    run_executor,
    run_validator,
    run_writer,
    parse_validation_result,
    ValidationStatus,
)


class HierarchicalWorkflowState(TypedDict):
    """State passed between workflow nodes."""
    task: str
    specification: str
    plan: str
    executor_results: list[str]
    aggregated_output: str
    validation_result: str
    validation_status: str
    _callbacks: list


async def supervisor_node(state: HierarchicalWorkflowState) -> dict:
    """Supervisor node that initiates the workflow."""
    # Supervisor just passes through to planning
    return {"task": state["task"]}


async def planner_node(state: HierarchicalWorkflowState) -> dict:
    """Planner node that decomposes the task."""
    callbacks = state.get("_callbacks", [])
    agent = create_planner_agent(callbacks=callbacks)

    plan = await run_planner(
        task=state["task"],
        agent=agent,
        context=state.get("specification", ""),
    )

    return {"plan": plan}


async def executor_1_node(state: HierarchicalWorkflowState) -> dict:
    """First executor node - handles research/data gathering."""
    callbacks = state.get("_callbacks", [])
    agent = create_executor_agent(callbacks=callbacks)

    result = await run_executor(
        task=f"Execute phase 1 of plan: Research and data gathering\n\nPlan:\n{state['plan']}",
        available_tools=["web_search", "database_query", "file_read"],
        agent=agent,
        context=state["task"],
    )

    current_results = state.get("executor_results", [])
    return {"executor_results": current_results + [f"Executor 1 (Research):\n{result}"]}


async def executor_2_node(state: HierarchicalWorkflowState) -> dict:
    """Second executor node - handles processing/transformation."""
    callbacks = state.get("_callbacks", [])
    agent = create_executor_agent(callbacks=callbacks)

    result = await run_executor(
        task=f"Execute phase 2 of plan: Processing and transformation\n\nPlan:\n{state['plan']}",
        available_tools=["code_execute", "api_call"],
        agent=agent,
        context=state["task"],
    )

    current_results = state.get("executor_results", [])
    return {"executor_results": current_results + [f"Executor 2 (Processing):\n{result}"]}


async def executor_3_node(state: HierarchicalWorkflowState) -> dict:
    """Third executor node - handles output generation."""
    callbacks = state.get("_callbacks", [])
    agent = create_executor_agent(callbacks=callbacks)

    result = await run_executor(
        task=f"Execute phase 3 of plan: Output generation\n\nPlan:\n{state['plan']}",
        available_tools=["file_write", "api_call"],
        agent=agent,
        context=state["task"],
    )

    current_results = state.get("executor_results", [])
    return {"executor_results": current_results + [f"Executor 3 (Output):\n{result}"]}


async def aggregator_node(state: HierarchicalWorkflowState) -> dict:
    """Aggregator node that combines executor results."""
    callbacks = state.get("_callbacks", [])
    agent = create_writer_agent(callbacks=callbacks)

    executor_results = state.get("executor_results", [])
    combined_results = "\n\n---\n\n".join(executor_results)

    aggregated = await run_writer(
        research=f"Combine and synthesize these executor results into a coherent output:\n\n{combined_results}",
        output_format="report",
        agent=agent,
    )

    return {"aggregated_output": aggregated}


async def validator_node(state: HierarchicalWorkflowState) -> dict:
    """Validator node that validates the final output."""
    callbacks = state.get("_callbacks", [])
    agent = create_validator_agent(callbacks=callbacks)

    validation = await run_validator(
        content=state["aggregated_output"],
        specification=state.get("specification", state["task"]),
        agent=agent,
    )

    result = parse_validation_result(validation)

    return {
        "validation_result": validation,
        "validation_status": result.status.value,
    }


def check_validation(state: HierarchicalWorkflowState) -> Literal["end", "retry"]:
    """Check validation result and decide next action."""
    status = state.get("validation_status", "")

    if status == ValidationStatus.PASSED.value:
        return "end"
    if status == ValidationStatus.PARTIAL.value:
        return "end"  # Accept partial success

    # For failed validation, we could retry but for simplicity just end
    return "end"


def create_hierarchical_workflow() -> StateGraph:
    """Create the hierarchical delegation workflow graph.

    Flow: supervisor → planner → [executor1, executor2, executor3] → aggregator → validator

    Note: Executors run sequentially (LangGraph limitation for state management)

    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(HierarchicalWorkflowState)

    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor_1", executor_1_node)
    workflow.add_node("executor_2", executor_2_node)
    workflow.add_node("executor_3", executor_3_node)
    workflow.add_node("aggregator", aggregator_node)
    workflow.add_node("validator", validator_node)

    # Define edges (sequential for state management)
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", "planner")
    workflow.add_edge("planner", "executor_1")
    workflow.add_edge("executor_1", "executor_2")
    workflow.add_edge("executor_2", "executor_3")
    workflow.add_edge("executor_3", "aggregator")
    workflow.add_edge("aggregator", "validator")
    workflow.add_edge("validator", END)

    return workflow.compile()


async def run_hierarchical_workflow(
    task: str,
    specification: str = "",
    callbacks: list | None = None,
) -> dict:
    """Execute the hierarchical delegation workflow.

    Args:
        task: The task to execute
        specification: Specification/requirements for validation
        callbacks: Optional callback handlers for tracing

    Returns:
        Final state with all execution results
    """
    workflow = create_hierarchical_workflow()

    initial_state: HierarchicalWorkflowState = {
        "task": task,
        "specification": specification,
        "plan": "",
        "executor_results": [],
        "aggregated_output": "",
        "validation_result": "",
        "validation_status": "",
        "_callbacks": callbacks or [],
    }

    result = await workflow.ainvoke(initial_state)
    return result
