"""Plain-English detection explanations for non-technical users.

This module generates human-readable explanations for detected failures,
including business impact and suggested actions. The goal is to make
detection results understandable to anyone, not just ML engineers.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class DetectionExplanation:
    """Human-readable explanation for a detection."""
    explanation: str  # What happened in plain English
    business_impact: str  # Why it matters to the user
    suggested_action: str  # What to do next


# Explanation templates for each detection type
EXPLANATION_TEMPLATES: Dict[str, Dict[str, str]] = {
    # Loop detections
    "loop": {
        "explanation": "Your agent got stuck in a loop, repeating the same action {count} times without making progress.",
        "business_impact": "This wastes compute resources and can cause timeouts. Users may experience delays or incomplete results.",
        "suggested_action": "Add a retry limit or break condition. Consider implementing exponential backoff.",
    },
    "exact_loop": {
        "explanation": "Your agent repeated the exact same message '{action}' {count} times in a row.",
        "business_impact": "This indicates the agent is stuck and not processing new information. It will likely time out.",
        "suggested_action": "Check if the agent is receiving proper feedback from tools. Add a maximum retry limit.",
    },
    "semantic_loop": {
        "explanation": "Your agent is expressing the same intent repeatedly but with different wording. It's running in circles.",
        "business_impact": "The agent isn't making progress despite appearing active. This burns tokens without value.",
        "suggested_action": "Track completed actions in agent state to prevent re-attempts. Consider adding progress checkpoints.",
    },
    "tool_loop": {
        "explanation": "Your agent called the same tool '{tool_name}' {count} times with similar parameters.",
        "business_impact": "Repeated tool calls waste API credits and time. The underlying issue isn't being addressed.",
        "suggested_action": "Cache tool results or track which queries have been tried. Implement tool call deduplication.",
    },

    # State corruption
    "corruption": {
        "explanation": "The agent's internal state became inconsistent or invalid during execution.",
        "business_impact": "State corruption can lead to unpredictable behavior and incorrect outputs.",
        "suggested_action": "Validate state transitions. Add state invariant checks after each operation.",
    },
    "state_regression": {
        "explanation": "The agent's state reverted to an earlier value, losing progress.",
        "business_impact": "Work may be lost and the agent could repeat unnecessary steps.",
        "suggested_action": "Ensure state updates are atomic. Check for race conditions in multi-step operations.",
    },

    # Persona drift
    "persona": {
        "explanation": "The agent deviated from its defined role or personality during the conversation.",
        "business_impact": "Users may receive inconsistent or inappropriate responses that don't match expectations.",
        "suggested_action": "Reinforce the system prompt periodically. Add persona consistency checks.",
    },
    "persona_drift": {
        "explanation": "The agent gradually shifted away from its assigned persona over {span_count} turns.",
        "business_impact": "Long conversations may feel inconsistent. Brand voice can be lost.",
        "suggested_action": "Add persona anchoring in the system prompt. Consider periodic persona resets.",
    },

    # Coordination failures (multi-agent)
    "coordination": {
        "explanation": "Multiple agents failed to coordinate properly, causing a handoff failure or miscommunication.",
        "business_impact": "Tasks may be incomplete or executed incorrectly. Information can be lost between agents.",
        "suggested_action": "Implement explicit handoff acknowledgments. Add coordination state tracking.",
    },
    "handoff_failure": {
        "explanation": "Agent '{from_agent}' tried to hand off to '{to_agent}' but the handoff was not completed.",
        "business_impact": "The task is stuck between agents. Neither agent is progressing the work.",
        "suggested_action": "Add handoff confirmation protocol. Implement timeout and retry for failed handoffs.",
    },
    "deadlock": {
        "explanation": "Two or more agents are waiting on each other, creating a deadlock.",
        "business_impact": "The entire workflow is blocked. No agent can make progress.",
        "suggested_action": "Implement deadlock detection and automatic resolution. Add timeout-based circuit breakers.",
    },

    # Context and memory issues
    "context_overflow": {
        "explanation": "The agent's context window is {percent_full}% full and approaching the limit.",
        "business_impact": "Important information may be truncated or lost. Response quality will degrade.",
        "suggested_action": "Implement context summarization. Consider moving long-term info to external memory.",
    },
    "overflow": {
        "explanation": "The context window overflowed, losing earlier conversation context.",
        "business_impact": "The agent forgot earlier parts of the conversation. It may repeat questions or lose context.",
        "suggested_action": "Add context compression. Prioritize recent messages. Use retrieval for old context.",
    },

    # Hallucination
    "hallucination": {
        "explanation": "The agent made up information that wasn't in its context or tools.",
        "business_impact": "Users may receive false or misleading information. Trust in the system is damaged.",
        "suggested_action": "Ground responses in retrieved documents. Add fact-checking steps.",
    },

    # Task and goal issues
    "derailment": {
        "explanation": "The agent went off-topic and stopped working on the original task.",
        "business_impact": "The user's actual request isn't being addressed. Time is wasted on unrelated work.",
        "suggested_action": "Add task tracking and goal reminders. Implement relevance checks.",
    },
    "task_derailment": {
        "explanation": "The agent started working on '{actual_task}' instead of the requested '{expected_task}'.",
        "business_impact": "User's needs aren't being met. The conversation has gone off track.",
        "suggested_action": "Anchor to the original user request. Add explicit task confirmation steps.",
    },

    # Tool issues
    "tool_provision": {
        "explanation": "A tool call failed with error: {error}",
        "business_impact": "The agent can't complete the task without this tool. It may retry indefinitely.",
        "suggested_action": "Add tool error handling. Implement fallback strategies for common failures.",
    },

    # Injection attacks
    "injection": {
        "explanation": "A potential prompt injection attack was detected in the input.",
        "business_impact": "An attacker may be trying to manipulate the agent's behavior or extract sensitive data.",
        "suggested_action": "Review the flagged input. Consider implementing input sanitization.",
    },

    # Communication
    "communication": {
        "explanation": "Inter-agent communication failed or was corrupted.",
        "business_impact": "Agents can't coordinate effectively. Task completion is at risk.",
        "suggested_action": "Add message validation and acknowledgments. Implement retry logic.",
    },

    # Workflow
    "workflow": {
        "explanation": "The workflow execution deviated from the expected path.",
        "business_impact": "The task may not complete correctly. Some steps may be skipped or repeated.",
        "suggested_action": "Add workflow state tracking. Implement step validation.",
    },

    # Default fallback
    "unknown": {
        "explanation": "An issue was detected but the specific type couldn't be determined.",
        "business_impact": "The agent may not be functioning optimally.",
        "suggested_action": "Review the trace details for more information.",
    },
}


def get_explanation(
    detection_type: str,
    method: str,
    details: Dict[str, Any],
    confidence: int,
) -> DetectionExplanation:
    """Generate a human-readable explanation for a detection.

    Args:
        detection_type: The type of detection (loop, corruption, etc.)
        method: The detection method used
        details: Detection details with context
        confidence: Detection confidence percentage

    Returns:
        DetectionExplanation with human-readable text
    """
    # Try to find a specific template for the method, fall back to type
    templates = EXPLANATION_TEMPLATES.get(
        method,
        EXPLANATION_TEMPLATES.get(
            detection_type,
            EXPLANATION_TEMPLATES["unknown"]
        )
    )

    # Extract common values from details for template substitution
    context = {
        "count": details.get("repetition_count", details.get("count", "multiple")),
        "action": details.get("repeated_content", details.get("action", "an action"))[:50],
        "tool_name": details.get("tool_name", "a tool"),
        "span_count": details.get("span_count", "several"),
        "from_agent": details.get("from_agent", "source agent"),
        "to_agent": details.get("to_agent", "target agent"),
        "percent_full": details.get("context_percent", details.get("usage_percent", "high")),
        "error": details.get("error", details.get("error_message", "unknown error"))[:100],
        "actual_task": details.get("actual_task", "another task")[:50],
        "expected_task": details.get("expected_task", "the original task")[:50],
        "confidence": confidence,
    }

    # Format explanation templates with context
    try:
        explanation = templates["explanation"].format(**context)
        business_impact = templates["business_impact"].format(**context)
        suggested_action = templates["suggested_action"].format(**context)
    except KeyError:
        # If template substitution fails, use raw templates
        explanation = templates["explanation"]
        business_impact = templates["business_impact"]
        suggested_action = templates["suggested_action"]

    # Add confidence context to explanation
    if confidence >= 90:
        explanation = f"(High confidence) {explanation}"
    elif confidence >= 70:
        explanation = f"(Medium confidence) {explanation}"
    elif confidence >= 50:
        explanation = f"(Low confidence - may be a false positive) {explanation}"

    return DetectionExplanation(
        explanation=explanation,
        business_impact=business_impact,
        suggested_action=suggested_action,
    )


def explain_detection(detection_dict: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """Generate explanations from a detection dictionary.

    Args:
        detection_dict: Detection data with type, method, details, confidence

    Returns:
        Dictionary with explanation, business_impact, suggested_action keys
    """
    explanation = get_explanation(
        detection_type=detection_dict.get("detection_type", "unknown"),
        method=detection_dict.get("method", "unknown"),
        details=detection_dict.get("details", {}),
        confidence=detection_dict.get("confidence", 50),
    )

    return {
        "explanation": explanation.explanation,
        "business_impact": explanation.business_impact,
        "suggested_action": explanation.suggested_action,
    }
