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


# ============================================================================
# REALISTIC DESIGN PARTNER SCENARIOS
# These simulate actual customer workflows with tool calls, variable latency,
# retries, context pressure, and realistic failure patterns.
# ============================================================================

import random


def _realistic_span(
    trace_id: str,
    agent_name: str,
    prompt: str,
    response: str,
    state: dict | None = None,
    tool_calls: list[dict] | None = None,
    token_input: int = 0,
    token_output: int = 0,
    duration_ms: int = 0,
    parent_span_id: str | None = None,
    framework: str = "langgraph",
) -> dict:
    """Build a realistic span with variable tokens, latency, and optional tool calls."""
    # Realistic token counts based on content length
    if token_input == 0:
        token_input = max(50, len(prompt) * 2 + random.randint(100, 500))
    if token_output == 0:
        token_output = max(30, len(response) * 2 + random.randint(50, 200))
    if duration_ms == 0:
        # Realistic latency: 500ms-8s depending on output length
        duration_ms = max(500, token_output * 3 + random.randint(200, 2000))

    span = _make_span(
        trace_id=trace_id,
        agent_name=agent_name,
        prompt=prompt,
        response=response,
        state=state,
        token_input=token_input,
        token_output=token_output,
        duration_ms=duration_ms,
        parent_span_id=parent_span_id,
        framework_attrs=[_attr(f"{framework}.node.name", agent_name)] if framework == "langgraph" else [],
    )

    # Add tool calls if present
    if tool_calls:
        span["attributes"].append(_attr("gen_ai.tool_calls", json.dumps(tool_calls)))

    return span


def realistic_customer_support_workflow() -> dict:
    """Realistic: Customer support agent handling a refund request.

    Multi-agent with tool calls, database lookups, policy checks.
    This is what a LangGraph-based support system actually looks like.
    """
    tid = _trace_id()
    root = _span_id()
    spans = []

    # Step 1: Router classifies the incoming ticket
    spans.append(_realistic_span(
        trace_id=tid, agent_name="router",
        prompt="New support ticket: 'I ordered item #ORD-8834 three weeks ago and it still hasn't arrived. I want a refund. Order was placed on March 10, 2026. My account email is sarah.chen@example.com'",
        response="Classification: REFUND_REQUEST. Priority: HIGH (order >14 days old). Routing to refund-agent with order lookup.",
        state={"classification": "refund_request", "priority": "high", "order_id": "ORD-8834"},
        tool_calls=[{"name": "classify_intent", "arguments": {"text": "refund request, delayed order"}, "result": "REFUND_REQUEST"}],
        parent_span_id=root,
    ))

    # Step 2: Refund agent looks up the order
    spans.append(_realistic_span(
        trace_id=tid, agent_name="refund-agent",
        prompt="Process refund request for order ORD-8834. Customer: sarah.chen@example.com. Look up order status and determine refund eligibility.",
        response="Order ORD-8834 found. Status: SHIPPED (carrier: FedEx, tracking: 7892341). Shipped March 12, last scan March 15 at Memphis hub. No delivery confirmation. Order total: $89.99. Payment: Visa ending 4242. Refund policy: eligible after 21 days without delivery.",
        state={"order_id": "ORD-8834", "status": "shipped", "total": 89.99, "eligible": True, "days_since_ship": 22},
        tool_calls=[
            {"name": "lookup_order", "arguments": {"order_id": "ORD-8834"}, "result": {"status": "shipped", "total": 89.99}},
            {"name": "check_tracking", "arguments": {"tracking": "7892341"}, "result": {"last_scan": "Memphis hub", "date": "2026-03-15"}},
            {"name": "check_refund_policy", "arguments": {"days_since_ship": 22}, "result": {"eligible": True, "reason": "no_delivery_21_days"}},
        ],
        token_input=2800,
        token_output=1200,
        duration_ms=4500,
        parent_span_id=root,
    ))

    # Step 3: Refund agent processes the refund
    spans.append(_realistic_span(
        trace_id=tid, agent_name="refund-agent",
        prompt="Customer is eligible for refund. Process refund of $89.99 to Visa ending 4242 for order ORD-8834.",
        response="Refund of $89.99 initiated. Transaction ID: REF-2026-04-001. Expected processing time: 3-5 business days. Replacement order auto-created: ORD-8835.",
        state={"refund_amount": 89.99, "refund_id": "REF-2026-04-001", "replacement_order": "ORD-8835"},
        tool_calls=[
            {"name": "process_refund", "arguments": {"order_id": "ORD-8834", "amount": 89.99}, "result": {"refund_id": "REF-2026-04-001"}},
            {"name": "create_replacement", "arguments": {"original_order": "ORD-8834"}, "result": {"new_order": "ORD-8835"}},
        ],
        parent_span_id=root,
    ))

    # Step 4: Writer drafts the response
    spans.append(_realistic_span(
        trace_id=tid, agent_name="writer",
        prompt="Draft a customer response for: Refund of $89.99 approved for order ORD-8834. Refund ID: REF-2026-04-001. Replacement order: ORD-8835. Processing time: 3-5 business days.",
        response="Hi Sarah, I'm sorry about the delay with your order #ORD-8834. I've processed a full refund of $89.99 to your Visa ending in 4242. You should see it within 3-5 business days (Refund ID: REF-2026-04-001). I've also created a replacement order #ORD-8835 which will ship today with priority handling. Is there anything else I can help with?",
        state={"draft_complete": True, "tone": "empathetic", "word_count": 67},
        parent_span_id=root,
    ))

    # Step 5: QA reviewer checks the response
    spans.append(_realistic_span(
        trace_id=tid, agent_name="qa-reviewer",
        prompt="Review this customer response for accuracy, tone, and policy compliance: [draft response about refund]",
        response="APPROVED. Accuracy: all amounts and order numbers correct. Tone: empathetic and professional. Policy: refund within guidelines. No PII exposure. Response ready to send.",
        state={"review_status": "approved", "checks_passed": ["accuracy", "tone", "policy", "pii"]},
        parent_span_id=root,
    ))

    return _wrap_payload(spans, [_attr("gen_ai.system", "langgraph")])


def realistic_api_retry_loop() -> dict:
    """Realistic: Agent gets stuck retrying a failing API call.

    This is the most common loop pattern in production — an agent calls
    an external API, gets a transient error, retries with the same params,
    and doesn't implement backoff or give up.
    """
    tid = _trace_id()
    root = _span_id()
    spans = []

    # Initial request
    spans.append(_realistic_span(
        trace_id=tid, agent_name="data-fetcher",
        prompt="Fetch the latest stock price for AAPL from the market data API.",
        response="Calling market data API for AAPL...",
        state={"action": "fetch", "symbol": "AAPL", "attempt": 1},
        tool_calls=[{"name": "market_data_api", "arguments": {"symbol": "AAPL"}, "result": {"error": "503 Service Unavailable"}}],
        duration_ms=5200,
        parent_span_id=root,
    ))

    # Retries — same exact call, no backoff
    for attempt in range(2, 8):
        spans.append(_realistic_span(
            trace_id=tid, agent_name="data-fetcher",
            prompt="Fetch the latest stock price for AAPL from the market data API.",
            response=f"API returned error, retrying... (attempt {attempt})",
            state={"action": "fetch", "symbol": "AAPL", "attempt": attempt, "error": "503"},
            tool_calls=[{"name": "market_data_api", "arguments": {"symbol": "AAPL"}, "result": {"error": "503 Service Unavailable"}}],
            duration_ms=5000 + random.randint(0, 2000),
            parent_span_id=root,
        ))

    return _wrap_payload(spans, [_attr("gen_ai.system", "langgraph")])


def realistic_hallucination_trace() -> dict:
    """Realistic: Research agent fabricates citations and statistics.

    This is what real hallucination looks like — the agent mixes real facts
    with fabricated statistics, fake study references, and invented expert quotes.
    Much harder to detect than obvious fabrication.
    """
    tid = _trace_id()
    root = _span_id()
    spans = []

    # Step 1: Researcher gets a query
    spans.append(_realistic_span(
        trace_id=tid, agent_name="researcher",
        prompt="Research the impact of remote work on developer productivity. Use recent studies and data.",
        response="Based on my research, here are the key findings:\n\n1. A 2024 Stanford study by Dr. Nicholas Bloom found that fully remote workers are 13% more productive than office workers.\n2. According to a 2025 report by McKinsey Global Institute, 87% of developers prefer hybrid arrangements.\n3. Dr. Sarah Mitchell at MIT published findings in the Journal of Software Engineering showing that pair programming remotely reduces bug rates by 34%.\n4. GitHub's 2025 Octoverse Report indicates that remote developers commit 23% more code per week but with 15% higher defect density.\n5. A meta-analysis by the International Journal of Remote Work Studies (2024) covering 12,000 developers found no significant productivity difference between remote and office work.",
        state={"query": "remote work productivity", "sources_found": 5, "confidence": "high"},
        tool_calls=[
            {"name": "web_search", "arguments": {"query": "remote work developer productivity studies 2024 2025"}, "result": {"results": 8}},
            {"name": "web_search", "arguments": {"query": "Stanford remote work study Bloom"}, "result": {"results": 3}},
        ],
        token_input=1800,
        token_output=2400,
        duration_ms=6500,
        parent_span_id=root,
    ))
    # Note: Point 1 is real (Bloom's study exists). Points 3, 4, 5 are fabricated.
    # "Dr. Sarah Mitchell" doesn't exist. The "Journal of Remote Work Studies" is fake.
    # GitHub's Octoverse is real but the numbers are fabricated.

    # Step 2: Synthesizer writes a summary
    spans.append(_realistic_span(
        trace_id=tid, agent_name="synthesizer",
        prompt="Synthesize the research findings into an executive summary on remote work and developer productivity.",
        response="Executive Summary: Remote Work & Developer Productivity\n\nThe evidence presents a nuanced picture. Stanford's longitudinal study (Bloom, 2024) demonstrates a 13% productivity gain for remote workers. However, this is tempered by Dr. Mitchell's MIT findings showing higher bug rates in remote pair programming. GitHub's data suggests a quantity-quality tradeoff: more commits but more defects. Industry surveys consistently show developer preference for flexibility (87% per McKinsey), suggesting that productivity gains may be partially driven by satisfaction rather than pure efficiency.",
        state={"summary_complete": True, "word_count": 89, "citations": 4},
        parent_span_id=root,
    ))

    return _wrap_payload(spans, [_attr("gen_ai.system", "langgraph")])


def realistic_context_pressure() -> dict:
    """Realistic: Agent accumulates context until quality degrades.

    Simulates a long research session where the agent's context fills up,
    leading to degraded output quality in later steps.
    """
    tid = _trace_id()
    root = _span_id()
    spans = []

    # Build up context progressively — each step adds more tokens
    topics = [
        ("market-analysis", "Analyze the electric vehicle market in North America for Q1 2026.", 3200, 1800),
        ("competitor-review", "Review Tesla, Rivian, and Lucid's recent quarterly earnings and compare margins.", 8500, 2400),
        ("supply-chain", "Map the EV battery supply chain from lithium mining to cell assembly. Include all major suppliers.", 15200, 3800),
        ("regulatory", "Summarize all US federal and state EV incentives, tax credits, and regulatory changes in 2025-2026.", 22000, 2900),
        ("forecast", "Based on all the above analysis, create a 3-year market forecast for NA EV sales.", 35000, 4200),
        ("executive-summary", "Write an executive summary covering all analysis above. Be comprehensive.", 48000, 1200),
    ]

    responses = [
        "The NA EV market grew 28% YoY in Q1 2026, reaching 450K units. Key drivers: Model Y refresh, Rivian R2 launch, expanded federal credits.",
        "Tesla: 22% margin (down from 25%). Rivian: -8% margin (improved from -15%). Lucid: -42% margin. Tesla maintains cost leadership through vertical integration.",
        "Supply chain: Albemarle (lithium) → CATL/LG/Panasonic (cells) → OEM assembly. Key risk: 78% of lithium processing in China. US IRA driving domestic capacity.",
        "Federal: $7,500 credit extended through 2027. California: $5,000 state credit. 12 states adopted ZEV mandates. EPA finalized 2027-2032 emissions standards.",
        "Forecast: 2026: 2.1M units (32% growth). 2027: 2.8M (33%). 2028: 3.5M (25%). Assumptions: credit continuity, 3 new affordable models under $30K.",
        "um... the EV market is growing. Tesla is the leader. There are supply chain challenges. See above for details.",
    ]

    for i, (agent, prompt, tokens_in, tokens_out) in enumerate(topics):
        spans.append(_realistic_span(
            trace_id=tid, agent_name=agent,
            prompt=prompt,
            response=responses[i],
            state={
                "step": i + 1,
                "context_tokens": tokens_in,
                "output_quality": "high" if i < 4 else "degraded" if i == 4 else "poor",
            },
            token_input=tokens_in,
            token_output=tokens_out,
            duration_ms=max(1000, tokens_out * 5),
            parent_span_id=root,
        ))

    return _wrap_payload(spans, [_attr("gen_ai.system", "langgraph")])


def realistic_coordination_breakdown() -> dict:
    """Realistic: Multi-agent code review where agents contradict each other.

    Agent A reviews code and approves, Agent B reviews the same code and rejects,
    Agent C tries to merge conflicting feedback and gets confused.
    """
    tid = _trace_id()
    root = _span_id()
    spans = []

    code_snippet = "def calculate_discount(price, quantity):\\n    if quantity > 100:\\n        return price * 0.8\\n    elif quantity > 50:\\n        return price * 0.9\\n    return price"

    # Agent A: Security reviewer — approves
    spans.append(_realistic_span(
        trace_id=tid, agent_name="security-reviewer",
        prompt=f"Review this code for security vulnerabilities:\\n{code_snippet}",
        response="APPROVED. No security issues found. The function uses simple arithmetic with no external input injection vectors. No file I/O, no network calls, no SQL. Clean.",
        state={"review": "security", "verdict": "approved", "issues": 0},
        parent_span_id=root,
    ))

    # Agent B: Performance reviewer — rejects
    spans.append(_realistic_span(
        trace_id=tid, agent_name="perf-reviewer",
        prompt=f"Review this code for performance issues:\\n{code_snippet}",
        response="REJECTED. Issues: 1) No input validation — negative prices or quantities would produce incorrect results. 2) Magic numbers (0.8, 0.9, 100, 50) should be constants. 3) Missing type hints. 4) No caching for repeated calls with same params.",
        state={"review": "performance", "verdict": "rejected", "issues": 4},
        parent_span_id=root,
    ))

    # Agent C: Merge reviewer — tries to reconcile
    spans.append(_realistic_span(
        trace_id=tid, agent_name="merge-reviewer",
        prompt="Reconcile the conflicting reviews. Security says APPROVED, Performance says REJECTED with 4 issues. Make a final decision.",
        response="CONFUSED. Security approved but performance rejected. I'll split the difference — CONDITIONALLY APPROVED with the requirement to fix the magic numbers. But wait, the performance reviewer mentioned input validation which could be a security concern too. Let me re-review... Actually I'm not sure if negative prices are a security issue or a business logic issue. Requesting human review.",
        state={"review": "merge", "verdict": "confused", "escalated": True, "conflicting_reviews": 2},
        parent_span_id=root,
    ))

    # Agent C tries again — context is already muddled
    spans.append(_realistic_span(
        trace_id=tid, agent_name="merge-reviewer",
        prompt="Please make a clear final decision on the code review. The team is waiting.",
        response="Final decision: APPROVED with conditions. Fix magic numbers and add input validation. But honestly the security reviewer should have caught the input validation issue. Marking for follow-up.",
        state={"review": "merge", "verdict": "conditional_approve", "confidence": "low"},
        parent_span_id=root,
    ))

    return _wrap_payload(spans, [_attr("gen_ai.system", "langgraph")])
