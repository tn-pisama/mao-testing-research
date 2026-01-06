"""Review loop workflow: research → write → review → [revise loop] → end."""

from typing import TypedDict, Literal
from langgraph.graph import END, StateGraph

from src.agents import (
    create_research_agent,
    create_writer_agent,
    create_reviewer_agent,
    run_research,
    run_writer,
    run_reviewer,
    parse_review_result,
    ReviewDecision,
)


class ReviewWorkflowState(TypedDict):
    """State passed between workflow nodes."""
    topic: str
    requirements: str
    research: str
    content: str
    review_feedback: str
    review_decision: str
    revision_count: int
    max_revisions: int
    output_format: str
    _callbacks: list


async def research_node(state: ReviewWorkflowState) -> dict:
    """Node that executes the research agent."""
    callbacks = state.get("_callbacks", [])
    agent = create_research_agent(callbacks=callbacks)

    research = await run_research(
        topic=state["topic"],
        agent=agent,
    )

    return {"research": research}


async def writer_node(state: ReviewWorkflowState) -> dict:
    """Node that executes the writer agent."""
    callbacks = state.get("_callbacks", [])
    agent = create_writer_agent(callbacks=callbacks)

    # Include review feedback if this is a revision
    context = state.get("research", "")
    if state.get("review_feedback") and state.get("revision_count", 0) > 0:
        context += f"\n\nPrevious feedback to address:\n{state['review_feedback']}"

    content = await run_writer(
        research=context,
        output_format=state.get("output_format", "article"),
        agent=agent,
    )

    return {"content": content}


async def reviewer_node(state: ReviewWorkflowState) -> dict:
    """Node that executes the reviewer agent."""
    callbacks = state.get("_callbacks", [])
    agent = create_reviewer_agent(callbacks=callbacks)

    review_output = await run_reviewer(
        content=state["content"],
        requirements=state.get("requirements", state["topic"]),
        agent=agent,
    )

    result = parse_review_result(review_output)

    return {
        "review_feedback": review_output,
        "review_decision": result.decision.value,
        "revision_count": state.get("revision_count", 0) + 1,
    }


def should_revise(state: ReviewWorkflowState) -> Literal["revise", "end"]:
    """Determine if content should be revised based on review."""
    decision = state.get("review_decision", "")
    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 3)

    # Stop if approved or max revisions reached
    if decision == ReviewDecision.APPROVED.value:
        return "end"
    if revision_count >= max_revisions:
        return "end"
    if decision == ReviewDecision.REJECTED.value and revision_count >= 2:
        return "end"

    return "revise"


def create_review_workflow() -> StateGraph:
    """Create the review loop workflow graph.

    Flow: research → write → review → [pass: end, fail: revise → review]

    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(ReviewWorkflowState)

    # Add nodes
    workflow.add_node("research", research_node)
    workflow.add_node("write", writer_node)
    workflow.add_node("review", reviewer_node)
    workflow.add_node("revise", writer_node)  # Reuse writer for revision

    # Define edges
    workflow.set_entry_point("research")
    workflow.add_edge("research", "write")
    workflow.add_edge("write", "review")

    # Conditional edge: review decision
    workflow.add_conditional_edges(
        "review",
        should_revise,
        {
            "revise": "revise",
            "end": END,
        }
    )

    # Revision loops back to review
    workflow.add_edge("revise", "review")

    return workflow.compile()


async def run_review_workflow(
    topic: str,
    requirements: str = "",
    output_format: str = "article",
    max_revisions: int = 3,
    callbacks: list | None = None,
) -> dict:
    """Execute the review loop workflow.

    Args:
        topic: Topic to research and write about
        requirements: Specific requirements for the content
        output_format: Desired output format (article, summary, report)
        max_revisions: Maximum number of revision iterations
        callbacks: Optional callback handlers for tracing

    Returns:
        Final state with content and review history
    """
    workflow = create_review_workflow()

    initial_state: ReviewWorkflowState = {
        "topic": topic,
        "requirements": requirements,
        "research": "",
        "content": "",
        "review_feedback": "",
        "review_decision": "",
        "revision_count": 0,
        "max_revisions": max_revisions,
        "output_format": output_format,
        "_callbacks": callbacks or [],
    }

    result = await workflow.ainvoke(initial_state)
    return result
