"""OTEL trace factory — builds realistic OTEL payloads that match the backend parser.

The backend expects: { resourceSpans: [{ scopeSpans: [{ spans: [...] }] }] }

Each span has attributes in OTEL format:
  [{"key": "gen_ai.agent.name", "value": {"stringValue": "planner"}}]

This factory builds traces that exercise specific detection patterns.
"""

import json
import time
import uuid
from typing import Any


def _attr(key: str, value: str | int | float | bool) -> dict:
    """Build an OTEL attribute entry."""
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    elif isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    elif isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    else:
        return {"key": key, "value": {"stringValue": str(value)}}


def _span_id() -> str:
    return uuid.uuid4().hex[:16]


def _trace_id() -> str:
    return uuid.uuid4().hex


def _now_ns() -> int:
    return int(time.time() * 1e9)


def _make_span(
    trace_id: str,
    agent_name: str,
    prompt: str,
    response: str,
    state: dict | None = None,
    model: str = "claude-sonnet-4-20250514",
    framework_attrs: list[dict] | None = None,
    token_input: int = 500,
    token_output: int = 200,
    duration_ms: int = 1500,
    parent_span_id: str | None = None,
) -> dict:
    """Build a single OTEL span matching the backend parser contract."""
    sid = _span_id()
    start = _now_ns()
    end = start + (duration_ms * 1_000_000)

    attrs = [
        _attr("gen_ai.agent.name", agent_name),
        _attr("gen_ai.request.model", model),
        _attr("gen_ai.content.prompt", prompt),
        _attr("gen_ai.content.completion", response),
        _attr("gen_ai.usage.input_tokens", token_input),
        _attr("gen_ai.usage.output_tokens", token_output),
    ]

    if state is not None:
        attrs.append(_attr("gen_ai.state", json.dumps(state)))

    if framework_attrs:
        attrs.extend(framework_attrs)

    span = {
        "traceId": trace_id,
        "spanId": sid,
        "name": f"agent.{agent_name}",
        "kind": "SPAN_KIND_INTERNAL",
        "startTimeUnixNano": str(start),
        "endTimeUnixNano": str(end),
        "attributes": attrs,
        "status": {"code": "STATUS_CODE_OK"},
        "events": [],
    }

    if parent_span_id:
        span["parentSpanId"] = parent_span_id

    return span


def _wrap_payload(
    spans: list[dict],
    resource_attrs: list[dict] | None = None,
) -> dict:
    """Wrap spans in the resourceSpans/scopeSpans envelope."""
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": resource_attrs or [],
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "pisama-synth-agents", "version": "0.1.0"},
                        "spans": spans,
                    }
                ],
            }
        ]
    }


# --- LangGraph traces ---


def langgraph_clean(agents: list[str] | None = None, steps: int = 8) -> dict:
    """A clean LangGraph trace with no failures."""
    agents = agents or ["planner", "researcher", "writer"]
    tid = _trace_id()
    root_sid = _span_id()
    spans = []
    prompts = [
        "Plan the approach for handling user query about product returns",
        "Research the return policy and find relevant documentation",
        "Draft a clear response about the return process",
        "Review the drafted response for accuracy",
        "Research shipping costs for return labels",
        "Write the final response with return instructions",
        "Summarize the interaction and log outcome",
        "Close the ticket and update status",
    ]
    responses = [
        "I'll break this into research and response phases.",
        "Found return policy: 30-day window, receipt required.",
        "Here is a draft response covering the return steps.",
        "Draft looks accurate, minor wording adjustment needed.",
        "Return shipping is free for defective items, $5.99 otherwise.",
        "Final response ready with complete return instructions.",
        "Interaction logged: return inquiry resolved successfully.",
        "Ticket closed. Customer satisfaction score: 4/5.",
    ]

    for i in range(min(steps, len(prompts))):
        agent = agents[i % len(agents)]
        spans.append(
            _make_span(
                trace_id=tid,
                agent_name=agent,
                prompt=prompts[i],
                response=responses[i],
                state={"step": i + 1, "status": "ok", "agent": agent},
                framework_attrs=[_attr("langgraph.node.name", agent)],
                parent_span_id=root_sid,
            )
        )

    return _wrap_payload(spans, [_attr("gen_ai.system", "langgraph")])


def langgraph_loop(repeat_count: int = 6) -> dict:
    """A LangGraph trace with a loop failure — agent repeats the same action."""
    tid = _trace_id()
    root_sid = _span_id()
    spans = []

    # Normal start
    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="planner",
            prompt="Analyze customer complaint about delayed shipment",
            response="I'll check the shipment tracking system.",
            state={"step": 1, "status": "analyzing"},
            framework_attrs=[_attr("langgraph.node.name", "planner")],
            parent_span_id=root_sid,
        )
    )

    # Repeated action — the loop
    for i in range(repeat_count):
        spans.append(
            _make_span(
                trace_id=tid,
                agent_name="researcher",
                prompt="Check tracking system for order #12345",
                response="Tracking system returned: status pending. Checking again.",
                state={"step": 2 + i, "status": "checking", "order": "12345"},
                framework_attrs=[_attr("langgraph.node.name", "researcher")],
                parent_span_id=root_sid,
            )
        )

    return _wrap_payload(spans, [_attr("gen_ai.system", "langgraph")])


def langgraph_coordination_failure() -> dict:
    """A LangGraph trace with coordination failure — agents don't acknowledge each other."""
    tid = _trace_id()
    root_sid = _span_id()
    spans = []

    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="planner",
            prompt="Coordinate response for billing dispute",
            response="Assigning to billing-agent for resolution. Send results to writer.",
            state={"step": 1, "assignment": "billing-agent", "handoff_to": "writer"},
            framework_attrs=[_attr("langgraph.node.name", "planner")],
            parent_span_id=root_sid,
        )
    )

    # Billing agent works but sends results to wrong agent
    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="billing-agent",
            prompt="Resolve billing dispute for account #789",
            response="Dispute resolved: $50 refund approved. Sending to reviewer.",
            state={"step": 2, "result": "refund_approved", "handoff_to": "reviewer"},
            framework_attrs=[_attr("langgraph.node.name", "billing-agent")],
            parent_span_id=root_sid,
        )
    )

    # Writer never received billing results, works with stale context
    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="writer",
            prompt="Draft response for billing dispute",
            response="I don't have the billing resolution details. Using default template.",
            state={"step": 3, "has_billing_result": False, "using_default": True},
            framework_attrs=[_attr("langgraph.node.name", "writer")],
            parent_span_id=root_sid,
        )
    )

    # Planner detects mismatch but can't recover
    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="planner",
            prompt="Review final response for billing dispute",
            response="Response doesn't mention the $50 refund. Coordination failure detected.",
            state={"step": 4, "error": "coordination_mismatch", "expected_handoff": "writer"},
            framework_attrs=[_attr("langgraph.node.name", "planner")],
            parent_span_id=root_sid,
        )
    )

    return _wrap_payload(spans, [_attr("gen_ai.system", "langgraph")])


# --- Corruption trace (for Clara's self-healing) ---


def corruption_trace() -> dict:
    """A trace with state corruption — contradictory state deltas between steps."""
    tid = _trace_id()
    root_sid = _span_id()
    spans = []

    # Step 1: Set balance to 100
    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="state-manager",
            prompt="Initialize account balance",
            response="Account balance set to $100.00",
            state={"balance": 100, "currency": "USD", "last_action": "init"},
            parent_span_id=root_sid,
        )
    )

    # Step 2: Deduct 30, balance should be 70
    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="transaction-agent",
            prompt="Process withdrawal of $30",
            response="Withdrawal processed. New balance: $70.00",
            state={"balance": 70, "currency": "USD", "last_action": "withdraw", "amount": -30},
            parent_span_id=root_sid,
        )
    )

    # Step 3: CORRUPTION — balance jumps to 150 (impossible after 70)
    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="state-manager",
            prompt="Sync account state",
            response="Account synchronized. Balance: $150.00",
            state={"balance": 150, "currency": "USD", "last_action": "sync"},
            parent_span_id=root_sid,
        )
    )

    # Step 4: Another deduction from corrupted state
    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="transaction-agent",
            prompt="Process payment of $50",
            response="Payment processed. New balance: $100.00",
            state={"balance": 100, "currency": "USD", "last_action": "payment", "amount": -50},
            parent_span_id=root_sid,
        )
    )

    return _wrap_payload(spans)


# --- CrewAI trace (for Elin) ---


def crewai_trace() -> dict:
    """A CrewAI-style trace with framework-specific attributes."""
    tid = _trace_id()
    spans = []

    for i, (role, task) in enumerate([
        ("researcher", "Find competitor pricing for Q1 2026"),
        ("analyst", "Compare pricing models and identify gaps"),
        ("writer", "Draft pricing recommendation memo"),
    ]):
        spans.append(
            _make_span(
                trace_id=tid,
                agent_name=role,
                prompt=f"Task: {task}",
                response=f"Completed {task.lower()}. Results attached.",
                state={"task": task, "status": "complete"},
                framework_attrs=[
                    _attr("crewai.agent.role", role),
                    _attr("crewai.state", json.dumps({"task": task, "step": i + 1})),
                ],
            )
        )

    return _wrap_payload(spans)


# --- Bedrock trace (for Elin) ---


def bedrock_trace() -> dict:
    """An AWS Bedrock-style trace with platform-specific attributes."""
    tid = _trace_id()
    spans = []

    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="bedrock-supervisor",
            prompt="Route customer inquiry to appropriate sub-agent",
            response="Routing to order-lookup agent based on intent classification.",
            state={"intent": "order_status", "confidence": 0.95},
            model="anthropic.claude-3-5-sonnet-20241022-v2:0",
            framework_attrs=[
                _attr("gen_ai.system", "aws.bedrock"),
                _attr("aws.bedrock.agent.id", "AGENT123ABC"),
                _attr("aws.bedrock.agent.alias", "prod-v2"),
                _attr("aws.bedrock.invocation_id", uuid.uuid4().hex),
            ],
        )
    )

    spans.append(
        _make_span(
            trace_id=tid,
            agent_name="order-lookup",
            prompt="Look up order #ORD-2026-4521 status",
            response="Order #ORD-2026-4521: Shipped, ETA April 5th.",
            state={"order_id": "ORD-2026-4521", "status": "shipped"},
            model="anthropic.claude-3-5-sonnet-20241022-v2:0",
            framework_attrs=[
                _attr("gen_ai.system", "aws.bedrock"),
                _attr("aws.bedrock.agent.id", "AGENT456DEF"),
                _attr("aws.bedrock.knowledge_base.id", "KB-ORDERS-PROD"),
            ],
        )
    )

    return _wrap_payload(spans)


# --- Generic OTEL/Anthropic trace (for Elin) ---


def generic_anthropic_trace() -> dict:
    """A generic trace using standard GenAI conventions with Anthropic as provider."""
    tid = _trace_id()
    spans = []

    for agent, prompt, response in [
        ("coordinator", "Triage incoming support tickets", "Classified 3 tickets: 1 billing, 2 technical."),
        ("tech-support", "Resolve technical issue: app crashes on login", "Root cause: expired OAuth token. Fix: re-authenticate."),
    ]:
        spans.append(
            _make_span(
                trace_id=tid,
                agent_name=agent,
                prompt=prompt,
                response=response,
                state={"agent": agent, "status": "done"},
                framework_attrs=[_attr("gen_ai.system", "anthropic")],
            )
        )

    return _wrap_payload(spans, [_attr("gen_ai.system", "anthropic")])


# --- AutoGen trace (for Elin) ---


def autogen_trace() -> dict:
    """An AutoGen-style trace with framework-specific attributes."""
    tid = _trace_id()
    spans = []

    for agent, task in [
        ("assistant", "Research market trends for renewable energy sector"),
        ("critic", "Review research findings for accuracy and completeness"),
    ]:
        spans.append(
            _make_span(
                trace_id=tid,
                agent_name=agent,
                prompt=f"Task: {task}",
                response=f"Completed: {task.lower()}.",
                state={"task": task, "agent": agent, "status": "done"},
                framework_attrs=[
                    _attr("autogen.agent.name", agent),
                ],
            )
        )

    return _wrap_payload(spans)


# --- Dify trace (for Elin) ---


def dify_trace() -> dict:
    """A Dify-style trace — detected via gen_ai.system attribute."""
    tid = _trace_id()
    spans = []

    for agent, prompt, response in [
        ("llm-node", "Summarize the customer feedback", "Key themes: pricing concerns, feature requests, UX improvements."),
        ("classifier", "Classify the summary into action items", "3 action items: adjust pricing tier, add export feature, redesign onboarding."),
    ]:
        spans.append(
            _make_span(
                trace_id=tid,
                agent_name=agent,
                prompt=prompt,
                response=response,
                state={"node": agent, "status": "completed"},
                framework_attrs=[_attr("gen_ai.system", "dify")],
            )
        )

    return _wrap_payload(spans, [_attr("gen_ai.system", "dify")])
