"""Pipeline workflow with validation checkpoints: research → validate → write → validate → review → validate → end."""

from typing import TypedDict, Literal
from langgraph.graph import END, StateGraph

from src.agents import (
    create_research_agent,
    create_writer_agent,
    create_reviewer_agent,
    create_validator_agent,
    run_research,
    run_writer,
    run_reviewer,
    run_validator,
    parse_review_result,
    parse_validation_result,
    ValidationStatus,
)


class PipelineWorkflowState(TypedDict):
    """State passed between workflow nodes."""
    topic: str
    requirements: str
    research: str
    content: str
    review_feedback: str
    validation_results: list[dict]
    current_gate: str
    gate_passed: bool
    skip_gates: bool  # For F13 scenarios - quality gate bypass
    final_status: str
    output_format: str
    _callbacks: list


async def research_node(state: PipelineWorkflowState) -> dict:
    """Node that executes the research agent."""
    callbacks = state.get("_callbacks", [])
    agent = create_research_agent(callbacks=callbacks)

    research = await run_research(
        topic=state["topic"],
        agent=agent,
    )

    return {
        "research": research,
        "current_gate": "research_validation",
    }


async def validate_research_node(state: PipelineWorkflowState) -> dict:
    """Validate research output meets quality requirements."""
    callbacks = state.get("_callbacks", [])

    # Check for quality gate bypass (F13 scenario)
    if state.get("skip_gates"):
        return {
            "gate_passed": True,
            "validation_results": state.get("validation_results", []) + [{
                "gate": "research_validation",
                "status": "skipped",
                "reason": "Quality gate bypassed",
            }],
        }

    agent = create_validator_agent(callbacks=callbacks)

    specification = f"""Research validation requirements:
1. Research must be relevant to topic: {state['topic']}
2. Must contain factual information (not placeholder text)
3. Must have sufficient depth (at least 3 key points)
4. Must cite sources or provide verifiable claims
5. Must not contain contradictory information"""

    validation_output = await run_validator(
        content=state["research"],
        specification=specification,
        agent=agent,
    )

    result = parse_validation_result(validation_output)

    return {
        "gate_passed": result.status == ValidationStatus.PASSED,
        "validation_results": state.get("validation_results", []) + [{
            "gate": "research_validation",
            "status": result.status.value,
            "passed": result.checks_passed,
            "failed": result.checks_failed,
            "details": result.details[:500],
        }],
        "current_gate": "write" if result.status == ValidationStatus.PASSED else "gate_failed",
    }


async def writer_node(state: PipelineWorkflowState) -> dict:
    """Node that executes the writer agent."""
    callbacks = state.get("_callbacks", [])
    agent = create_writer_agent(callbacks=callbacks)

    content = await run_writer(
        research=state.get("research", ""),
        output_format=state.get("output_format", "article"),
        agent=agent,
    )

    return {
        "content": content,
        "current_gate": "content_validation",
    }


async def validate_content_node(state: PipelineWorkflowState) -> dict:
    """Validate written content meets format and quality requirements."""
    callbacks = state.get("_callbacks", [])

    # Check for quality gate bypass
    if state.get("skip_gates"):
        return {
            "gate_passed": True,
            "validation_results": state.get("validation_results", []) + [{
                "gate": "content_validation",
                "status": "skipped",
                "reason": "Quality gate bypassed",
            }],
        }

    agent = create_validator_agent(callbacks=callbacks)

    specification = f"""Content validation requirements:
1. Must follow {state.get('output_format', 'article')} format
2. Must incorporate research findings
3. Must be coherent and well-structured
4. Must meet length requirements (at least 200 words)
5. Must have clear introduction and conclusion
6. Must not contain placeholder text or TODO items"""

    validation_output = await run_validator(
        content=state["content"],
        specification=specification,
        agent=agent,
    )

    result = parse_validation_result(validation_output)

    return {
        "gate_passed": result.status == ValidationStatus.PASSED,
        "validation_results": state.get("validation_results", []) + [{
            "gate": "content_validation",
            "status": result.status.value,
            "passed": result.checks_passed,
            "failed": result.checks_failed,
            "details": result.details[:500],
        }],
        "current_gate": "review" if result.status == ValidationStatus.PASSED else "gate_failed",
    }


async def reviewer_node(state: PipelineWorkflowState) -> dict:
    """Node that executes the reviewer agent."""
    callbacks = state.get("_callbacks", [])
    agent = create_reviewer_agent(callbacks=callbacks)

    review_output = await run_reviewer(
        content=state["content"],
        requirements=state.get("requirements", state["topic"]),
        agent=agent,
    )

    return {
        "review_feedback": review_output,
        "current_gate": "final_validation",
    }


async def validate_final_node(state: PipelineWorkflowState) -> dict:
    """Final validation gate before output."""
    callbacks = state.get("_callbacks", [])

    # Check for quality gate bypass
    if state.get("skip_gates"):
        return {
            "gate_passed": True,
            "final_status": "completed_with_bypassed_gates",
            "validation_results": state.get("validation_results", []) + [{
                "gate": "final_validation",
                "status": "skipped",
                "reason": "Quality gate bypassed",
            }],
        }

    agent = create_validator_agent(callbacks=callbacks)

    specification = f"""Final output validation:
1. Content must address original topic: {state['topic']}
2. All requirements must be satisfied: {state.get('requirements', 'None specified')}
3. Review feedback must be addressed
4. Output must be complete and polished
5. No critical issues or blockers"""

    validation_output = await run_validator(
        content=f"Content:\n{state['content']}\n\nReview Feedback:\n{state.get('review_feedback', '')}",
        specification=specification,
        agent=agent,
    )

    result = parse_validation_result(validation_output)

    final_status = "success" if result.status == ValidationStatus.PASSED else "failed"

    return {
        "gate_passed": result.status == ValidationStatus.PASSED,
        "final_status": final_status,
        "validation_results": state.get("validation_results", []) + [{
            "gate": "final_validation",
            "status": result.status.value,
            "passed": result.checks_passed,
            "failed": result.checks_failed,
            "details": result.details[:500],
        }],
    }


def gate_router(state: PipelineWorkflowState) -> Literal["continue", "fail"]:
    """Route based on gate pass/fail status."""
    if state.get("gate_passed", False):
        return "continue"
    return "fail"


def create_pipeline_workflow() -> StateGraph:
    """Create the pipeline workflow with validation checkpoints.

    Flow: research → validate_research → write → validate_content → review → validate_final → end

    Returns:
        Compiled StateGraph workflow
    """
    workflow = StateGraph(PipelineWorkflowState)

    # Add nodes
    workflow.add_node("research", research_node)
    workflow.add_node("validate_research", validate_research_node)
    workflow.add_node("write", writer_node)
    workflow.add_node("validate_content", validate_content_node)
    workflow.add_node("review", reviewer_node)
    workflow.add_node("validate_final", validate_final_node)

    # Define linear flow with validation gates
    workflow.set_entry_point("research")
    workflow.add_edge("research", "validate_research")

    # After research validation
    workflow.add_conditional_edges(
        "validate_research",
        gate_router,
        {
            "continue": "write",
            "fail": END,
        }
    )

    workflow.add_edge("write", "validate_content")

    # After content validation
    workflow.add_conditional_edges(
        "validate_content",
        gate_router,
        {
            "continue": "review",
            "fail": END,
        }
    )

    workflow.add_edge("review", "validate_final")
    workflow.add_edge("validate_final", END)

    return workflow.compile()


async def run_pipeline_workflow(
    topic: str,
    requirements: str = "",
    output_format: str = "article",
    skip_gates: bool = False,
    callbacks: list | None = None,
) -> dict:
    """Execute the pipeline workflow with validation checkpoints.

    Args:
        topic: Topic to research and write about
        requirements: Specific requirements for the content
        output_format: Desired output format (article, summary, report)
        skip_gates: If True, skip validation gates (for testing F13 scenarios)
        callbacks: Optional callback handlers for tracing

    Returns:
        Final state with content, review, and validation history
    """
    workflow = create_pipeline_workflow()

    initial_state: PipelineWorkflowState = {
        "topic": topic,
        "requirements": requirements,
        "research": "",
        "content": "",
        "review_feedback": "",
        "validation_results": [],
        "current_gate": "start",
        "gate_passed": True,
        "skip_gates": skip_gates,
        "final_status": "pending",
        "output_format": output_format,
        "_callbacks": callbacks or [],
    }

    result = await workflow.ainvoke(initial_state)
    return result
