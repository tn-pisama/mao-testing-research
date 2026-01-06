"""Reviewer agent that reviews outputs and provides feedback."""

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler
from dataclasses import dataclass
from enum import Enum


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


@dataclass
class ReviewResult:
    """Result of a review."""
    decision: ReviewDecision
    feedback: str
    score: float  # 0.0 to 1.0
    issues: list[str]
    suggestions: list[str]


def create_reviewer_agent(
    callbacks: list[BaseCallbackHandler] | None = None,
) -> ChatAnthropic:
    """Create a reviewer agent using Claude.

    Args:
        callbacks: Optional list of callback handlers for tracing

    Returns:
        Configured ChatAnthropic instance for review tasks
    """
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        callbacks=callbacks,
    )


REVIEWER_SYSTEM_PROMPT = """You are a quality review agent. Your role is to critically evaluate content and provide constructive feedback.

When reviewing content:
1. Check for accuracy and completeness
2. Evaluate clarity and organization
3. Identify errors, inconsistencies, or gaps
4. Assess alignment with requirements
5. Provide specific, actionable feedback

Output format (use exactly this structure):
## Review Decision
[APPROVED / NEEDS_REVISION / REJECTED]

## Score
[0.0 to 1.0]

## Issues Found
- [Issue 1]
- [Issue 2]
...

## Suggestions for Improvement
- [Suggestion 1]
- [Suggestion 2]
...

## Detailed Feedback
[Comprehensive feedback explaining the decision]

Be constructive but honest. Focus on specific improvements rather than vague criticism."""


async def run_reviewer(
    content: str,
    requirements: str = "",
    agent: ChatAnthropic | None = None,
) -> str:
    """Review content and provide feedback.

    Args:
        content: The content to review
        requirements: Original requirements to check against
        agent: The reviewer agent instance

    Returns:
        Review feedback with decision and suggestions
    """
    if agent is None:
        agent = create_reviewer_agent()

    requirements_section = f"\n\nOriginal requirements:\n{requirements}" if requirements else ""

    messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=f"Review the following content:{requirements_section}\n\nContent to review:\n\n{content}"),
    ]

    response = await agent.ainvoke(messages)
    return response.content


def parse_review_result(review_text: str) -> ReviewResult:
    """Parse review text into structured ReviewResult.

    Args:
        review_text: Raw review output from reviewer agent

    Returns:
        Structured ReviewResult
    """
    import re

    # Default values
    decision = ReviewDecision.NEEDS_REVISION
    score = 0.5
    issues = []
    suggestions = []

    # Parse decision
    decision_match = re.search(r"Review Decision[:\s]*\n?\s*(APPROVED|NEEDS_REVISION|REJECTED)", review_text, re.IGNORECASE)
    if decision_match:
        decision_str = decision_match.group(1).upper()
        decision = ReviewDecision(decision_str.lower())

    # Parse score
    score_match = re.search(r"Score[:\s]*\n?\s*([0-9.]+)", review_text, re.IGNORECASE)
    if score_match:
        try:
            score = float(score_match.group(1))
            score = max(0.0, min(1.0, score))
        except ValueError:
            pass

    # Parse issues
    issues_section = re.search(r"Issues Found[:\s]*\n((?:[-*]\s+.+\n?)+)", review_text, re.IGNORECASE)
    if issues_section:
        issues = [line.strip().lstrip("-* ") for line in issues_section.group(1).strip().split("\n") if line.strip()]

    # Parse suggestions
    suggestions_section = re.search(r"Suggestions[^:]*:[:\s]*\n((?:[-*]\s+.+\n?)+)", review_text, re.IGNORECASE)
    if suggestions_section:
        suggestions = [line.strip().lstrip("-* ") for line in suggestions_section.group(1).strip().split("\n") if line.strip()]

    return ReviewResult(
        decision=decision,
        feedback=review_text,
        score=score,
        issues=issues,
        suggestions=suggestions,
    )
