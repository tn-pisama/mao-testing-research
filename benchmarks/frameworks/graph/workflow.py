"""LangGraph workflow for multi-agent orchestration."""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.agents.research_agent import create_research_agent, run_research
from src.agents.writer_agent import create_writer_agent, run_writer
from src.tracing import OpenTelemetryCallbackHandler


class WorkflowState(TypedDict):
    """State passed between workflow nodes."""

    topic: str
    research: str
    content: str
    output_format: str


async def research_node(state: WorkflowState) -> dict:
    """Node that executes the research agent."""
    callbacks = state.get("_callbacks", [])
    agent = create_research_agent(callbacks=callbacks)

    research = await run_research(
        topic=state["topic"],
        agent=agent,
    )

    return {"research": research}


async def writer_node(state: WorkflowState) -> dict:
    """Node that executes the writer agent."""
    callbacks = state.get("_callbacks", [])
    agent = create_writer_agent(callbacks=callbacks)

    content = await run_writer(
        research=state["research"],
        output_format=state.get("output_format", "article"),
        agent=agent,
    )

    return {"content": content}


def create_workflow(
    otel_handler: OpenTelemetryCallbackHandler | None = None,
) -> StateGraph:
    """Create the multi-agent workflow graph.

    Args:
        otel_handler: Optional OpenTelemetry callback handler for tracing

    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(WorkflowState)

    # Add nodes
    workflow.add_node("research", research_node)
    workflow.add_node("write", writer_node)

    # Define edges: research -> write -> end
    workflow.set_entry_point("research")
    workflow.add_edge("research", "write")
    workflow.add_edge("write", END)

    return workflow.compile()


async def run_workflow(
    topic: str,
    output_format: str = "article",
    otel_handler: OpenTelemetryCallbackHandler | None = None,
) -> str:
    """Execute the full research and writing workflow.

    Args:
        topic: Topic to research and write about
        output_format: Desired output format (article, summary, report)
        otel_handler: Optional OpenTelemetry handler for tracing

    Returns:
        Final written content
    """
    workflow = create_workflow(otel_handler)

    initial_state: WorkflowState = {
        "topic": topic,
        "research": "",
        "content": "",
        "output_format": output_format,
    }

    # Add callbacks to state for nodes to use
    if otel_handler:
        initial_state["_callbacks"] = [otel_handler]

    result = await workflow.ainvoke(initial_state)
    return result["content"]
