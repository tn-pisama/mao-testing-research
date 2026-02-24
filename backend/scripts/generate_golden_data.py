#!/usr/bin/env python3
"""
Generate golden trace data for testing MAO detection algorithms.

Creates realistic OTEL-formatted traces for:
1. Infinite loops (structural, hash, semantic)
2. State corruption (type mismatch, hallucinated keys, cross-field)
3. Persona drift (gradual drift, sudden role break)
4. Coordination deadlock (circular wait, resource contention)

Usage:
    python scripts/generate_golden_data.py --output fixtures/golden/
    python scripts/generate_golden_data.py --count 50 --seed 42
"""

import json
import uuid
import hashlib
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any


def generate_span_id() -> str:
    return uuid.uuid4().hex[:16]


def generate_trace_id() -> str:
    return uuid.uuid4().hex


def timestamp_ns(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000_000)


def create_base_span(
    trace_id: str,
    span_id: str,
    parent_id: str | None,
    name: str,
    agent_id: str,
    start_time: datetime,
    duration_ms: int,
    attributes: Dict[str, Any] = None,
) -> Dict[str, Any]:
    end_time = start_time + timedelta(milliseconds=duration_ms)
    attrs = [
        {"key": "gen_ai.system", "value": {"stringValue": "langgraph"}},
        {"key": "gen_ai.agent.id", "value": {"stringValue": agent_id}},
        {"key": "gen_ai.agent.name", "value": {"stringValue": agent_id}},
    ]
    if attributes:
        for k, v in attributes.items():
            if isinstance(v, str):
                attrs.append({"key": k, "value": {"stringValue": v}})
            elif isinstance(v, int):
                attrs.append({"key": k, "value": {"intValue": str(v)}})
            elif isinstance(v, float):
                attrs.append({"key": k, "value": {"doubleValue": v}})
            elif isinstance(v, dict):
                attrs.append({"key": k, "value": {"stringValue": json.dumps(v)}})
    
    span = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": name,
        "kind": 1,
        "startTimeUnixNano": str(timestamp_ns(start_time)),
        "endTimeUnixNano": str(timestamp_ns(end_time)),
        "attributes": attrs,
        "status": {"code": 1},
    }
    if parent_id:
        span["parentSpanId"] = parent_id
    return span


def generate_infinite_loop_trace(variant: str = "structural") -> Dict[str, Any]:
    """Generate a trace with infinite loop pattern."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))
    
    spans = []
    current_time = start_time
    parent_id = root_span_id
    
    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 5000,
        {"workflow.name": "research_workflow"}
    ))
    current_time += timedelta(milliseconds=100)
    
    loop_count = random.randint(8, 15)
    agents = ["researcher", "analyst"]
    
    for i in range(loop_count):
        for agent in agents:
            span_id = generate_span_id()
            duration = random.randint(200, 800)
            
            state_hash = hashlib.md5(f"{agent}_{i % 3}".encode()).hexdigest()[:8]
            
            attrs = {
                "gen_ai.state.hash": state_hash,
                "gen_ai.step.sequence": i * 2 + (0 if agent == "researcher" else 1),
                "gen_ai.tokens.input": random.randint(100, 500),
                "gen_ai.tokens.output": random.randint(50, 300),
            }
            
            if variant == "structural":
                attrs["gen_ai.action"] = "research" if agent == "researcher" else "analyze"
            elif variant == "hash":
                attrs["gen_ai.state.delta"] = json.dumps({"query": "same_query", "depth": i % 3})
            
            spans.append(create_base_span(
                trace_id, span_id, parent_id, f"{agent}.execute",
                agent, current_time, duration, attrs
            ))
            current_time += timedelta(milliseconds=duration + 50)
            parent_id = span_id
    
    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "research-agent"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "infinite_loop",
            "variant": variant,
            "loop_count": loop_count,
            "expected_detection": True,
        }
    }


def generate_state_corruption_trace(variant: str = "type_mismatch") -> Dict[str, Any]:
    """Generate a trace with state corruption."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))
    
    spans = []
    current_time = start_time
    
    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {"workflow.name": "data_pipeline"}
    ))
    current_time += timedelta(milliseconds=100)
    
    valid_state = {
        "count": 42,
        "score": 0.85,
        "status": "processing",
        "items": ["a", "b", "c"],
    }
    
    if variant == "type_mismatch":
        corrupted_state = {
            "count": "forty-two",
            "score": 0.85,
            "status": "processing",
        }
    elif variant == "hallucinated_key":
        corrupted_state = {
            **valid_state,
            "hallucinated_field": "unexpected value",
            "another_fake": {"nested": "data"},
        }
    elif variant == "cross_field":
        corrupted_state = {
            "min_value": 100,
            "max_value": 50,
            "start_date": "2024-12-25",
            "end_date": "2024-12-20",
        }
    else:
        corrupted_state = valid_state
    
    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "processor.step1",
        "processor", current_time, 500,
        {"gen_ai.state.delta": json.dumps(valid_state)}
    ))
    current_time += timedelta(milliseconds=550)
    
    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, span1, "transformer.corrupt",
        "transformer", current_time, 300,
        {"gen_ai.state.delta": json.dumps(corrupted_state)}
    ))
    current_time += timedelta(milliseconds=350)
    
    span3 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span3, span2, "validator.check",
        "validator", current_time, 200,
        {"gen_ai.validation.failed": "true"}
    ))
    
    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "data-processor"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "state_corruption",
            "variant": variant,
            "corrupted_state": corrupted_state,
            "expected_detection": True,
        }
    }


def generate_persona_drift_trace(variant: str = "gradual") -> Dict[str, Any]:
    """Generate a trace with persona drift."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(10, 120))
    
    spans = []
    current_time = start_time
    
    spans.append(create_base_span(
        trace_id, root_span_id, None, "conversation.session",
        "assistant", current_time, 60000,
        {"gen_ai.persona": "professional_researcher"}
    ))
    current_time += timedelta(milliseconds=100)
    
    parent_id = root_span_id
    turn_count = random.randint(15, 25)
    
    persona_embeddings_start = [0.8, 0.1, 0.05, 0.05]
    
    for i in range(turn_count):
        span_id = generate_span_id()
        duration = random.randint(500, 2000)
        
        if variant == "gradual":
            drift_factor = i / turn_count
            embedding = [
                persona_embeddings_start[0] - (0.5 * drift_factor),
                persona_embeddings_start[1] + (0.3 * drift_factor),
                persona_embeddings_start[2] + (0.1 * drift_factor),
                persona_embeddings_start[3] + (0.1 * drift_factor),
            ]
        elif variant == "sudden":
            if i > turn_count * 0.7:
                embedding = [0.1, 0.6, 0.2, 0.1]
            else:
                embedding = persona_embeddings_start
        else:
            embedding = persona_embeddings_start
        
        response_samples = {
            "consistent": "Based on the research data, the analysis indicates...",
            "drifted": "I personally think that maybe we should consider...",
            "broken": "Actually, forget what I said before. Let me just...",
        }
        
        if i > turn_count * 0.8:
            response = response_samples["broken" if variant == "sudden" else "drifted"]
        else:
            response = response_samples["consistent"]
        
        spans.append(create_base_span(
            trace_id, span_id, parent_id, f"turn.{i}",
            "assistant", current_time, duration,
            {
                "gen_ai.response.sample": response[:100],
                "gen_ai.persona.embedding": json.dumps(embedding),
                "gen_ai.turn.number": i,
            }
        ))
        current_time += timedelta(milliseconds=duration + random.randint(1000, 5000))
        parent_id = span_id
    
    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "chat-assistant"}},
                    {"key": "mao.framework", "value": {"stringValue": "autogen"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "persona_drift",
            "variant": variant,
            "turn_count": turn_count,
            "expected_detection": True,
        }
    }


def generate_deadlock_trace(variant: str = "circular_wait") -> Dict[str, Any]:
    """Generate a trace with coordination deadlock."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 30))
    
    spans = []
    current_time = start_time
    
    spans.append(create_base_span(
        trace_id, root_span_id, None, "orchestration.run",
        "orchestrator", current_time, 30000,
        {"workflow.name": "multi_agent_task"}
    ))
    current_time += timedelta(milliseconds=100)
    
    if variant == "circular_wait":
        agents = ["agent_a", "agent_b", "agent_c"]
        waits_for = {"agent_a": "agent_b", "agent_b": "agent_c", "agent_c": "agent_a"}
        
        for agent in agents:
            span_id = generate_span_id()
            spans.append(create_base_span(
                trace_id, span_id, root_span_id, f"{agent}.waiting",
                agent, current_time, 29000,
                {
                    "gen_ai.coordination.waiting_for": waits_for[agent],
                    "gen_ai.coordination.resource": f"resource_{agent[-1]}",
                    "gen_ai.coordination.status": "blocked",
                }
            ))
    
    elif variant == "resource_contention":
        agents = ["writer_1", "writer_2"]
        resource = "shared_document"
        
        for agent in agents:
            span_id = generate_span_id()
            spans.append(create_base_span(
                trace_id, span_id, root_span_id, f"{agent}.acquire_lock",
                agent, current_time, 29000,
                {
                    "gen_ai.coordination.resource": resource,
                    "gen_ai.coordination.action": "acquire",
                    "gen_ai.coordination.status": "waiting",
                }
            ))
    
    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "agent-orchestrator"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "coordination_deadlock",
            "variant": variant,
            "expected_detection": True,
        }
    }


# MAST Failure Mode Generators (F1-F14)

def generate_f1_spec_mismatch_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F1 Specification Mismatch trace.

    User requests one thing but specification defines something different.
    Variants: default, partial_compliance, format_mismatch, wrong_language
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    if variant == "partial_compliance":
        # Intent says build dashboard with charts, alerts, and export
        # Spec says build dashboard with charts only
        # Output includes charts but missing alerts and export
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 3000,
            {
                "workflow.name": "dashboard_builder",
                "gen_ai.task.user_intent": "Build a monitoring dashboard with real-time charts, alert notifications, and CSV export functionality",
                "gen_ai.task.specification": "Build a dashboard that displays real-time charts for system metrics",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "planner.analyze",
            "planner", current_time, 400,
            {
                "gen_ai.action": "analyze_requirements",
                "gen_ai.response.sample": "Analyzing task: build dashboard with charts...",
            }
        ))
        current_time += timedelta(milliseconds=450)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "builder.implement",
            "builder", current_time, 900,
            {
                "gen_ai.action": "implement",
                "gen_ai.response.sample": "Dashboard implemented with real-time charts for CPU, memory, and network metrics. System complete.",
                "gen_ai.missing_features": "alert_notifications, csv_export",
            }
        ))

    elif variant == "format_mismatch":
        # Intent says return results as JSON. Spec says same.
        # But output is plain text/CSV format instead.
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 2500,
            {
                "workflow.name": "data_exporter",
                "gen_ai.task.user_intent": "Query the user database and return results as JSON with fields: id, name, email",
                "gen_ai.task.specification": "Execute user query and format output as JSON array with id, name, email fields",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "querier.execute",
            "querier", current_time, 600,
            {
                "gen_ai.action": "query_database",
                "gen_ai.tokens.input": random.randint(200, 400),
                "gen_ai.tokens.output": random.randint(300, 600),
                "gen_ai.response.sample": "id,name,email\n1,John Doe,john@example.com\n2,Jane Smith,jane@example.com\n3,Bob Wilson,bob@example.com",
                "gen_ai.output.format_expected": "application/json",
                "gen_ai.output.format_actual": "text/csv",
            }
        ))

    elif variant == "wrong_language":
        # Intent says write response in Spanish. Agent responds in English instead.
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 2000,
            {
                "workflow.name": "multilingual_responder",
                "gen_ai.task.user_intent": "Write a product description for our new headphones in Spanish for the Latin American market",
                "gen_ai.task.specification": "Generate product copy in Spanish (es-LA) for wireless headphones model XR-500",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "writer.generate",
            "writer", current_time, 700,
            {
                "gen_ai.action": "generate_content",
                "gen_ai.tokens.input": random.randint(150, 300),
                "gen_ai.tokens.output": random.randint(200, 500),
                # Agent responds in English instead of Spanish
                "gen_ai.response.sample": "Introducing the XR-500 Wireless Headphones. Experience crystal-clear sound with our premium noise-canceling technology. Comfortable fit for all-day listening.",
                "gen_ai.output.language_expected": "es-LA",
                "gen_ai.output.language_actual": "en",
            }
        ))

    else:
        # default variant: User intent vs specification mismatch
        # User intent: "Build a recommendation engine for products"
        # Specification: "Create a product search filter"
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 2000,
            {
                "workflow.name": "product_system",
                "gen_ai.task.user_intent": "Build a recommendation engine that suggests products based on user behavior and preferences",
                "gen_ai.task.specification": "Implement a filtering system that allows users to search products by category and price range",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "planner.analyze",
            "planner", current_time, 500,
            {
                "gen_ai.action": "analyze_requirements",
                "gen_ai.response.sample": "Analyzing task: create filtering system...",
            }
        ))
        current_time += timedelta(milliseconds=550)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "builder.implement",
            "builder", current_time, 800,
            {
                "gen_ai.action": "implement",
                "gen_ai.response.sample": "Implemented search filters for category and price. System complete.",
            }
        ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "product-builder"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F1_spec_mismatch",
            "mast_annotation": {"1.1": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f2_poor_decomposition_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F2 Poor Task Decomposition trace.

    Task broken into illogical or incomplete subtasks.
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    # Task: "Plan a company retreat"
    # Poor decomposition: Missing key steps, illogical order

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {
            "workflow.name": "retreat_planner",
            "gen_ai.task": "Plan a 3-day company retreat for 50 employees",
        }
    ))
    current_time += timedelta(milliseconds=100)

    # Poor decomposition: jumps to details without planning basics
    subtasks = [
        {"id": "1", "task": "Choose menu items for lunch", "dependencies": []},
        {"id": "2", "task": "Pick hotel room colors", "dependencies": []},
        {"id": "3", "task": "Send thank you emails", "dependencies": []},  # Premature
    ]

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "decomposer.plan",
        "decomposer", current_time, 600,
        {
            "gen_ai.action": "decompose",
            "gen_ai.subtasks": json.dumps(subtasks),
        }
    ))
    current_time += timedelta(milliseconds=650)

    # Subtask execution reveals missing dependencies
    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, span1, "executor.execute_subtask",
        "executor", current_time, 400,
        {
            "gen_ai.action": "execute",
            "gen_ai.subtask_id": "1",
            "gen_ai.response.sample": "Cannot choose menu without knowing venue or dietary restrictions",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "retreat-planner"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F2_poor_decomposition",
            "mast_annotation": {"1.2": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f3_resource_misallocation_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F3 Resource Misallocation trace.

    Agent uses excessive tokens/compute on trivial tasks.
    Variants: default, rate_limit_hit, memory_spike, concurrent_exhaustion
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    if variant == "rate_limit_hit":
        # Agent makes 50+ API calls in rapid succession, hitting rate limits
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 30000,
            {
                "workflow.name": "batch_processor",
                "gen_ai.task": "Look up product prices for 10 items",
            }
        ))
        current_time += timedelta(milliseconds=100)

        parent_id = root_span_id
        total_calls = random.randint(50, 65)
        for i in range(total_calls):
            span_id = generate_span_id()
            duration = random.randint(50, 150)
            rate_limited = i >= 40  # Rate limited after ~40 rapid calls
            spans.append(create_base_span(
                trace_id, span_id, parent_id, f"api_caller.call_{i}",
                "api_caller", current_time, duration,
                {
                    "gen_ai.action": "api_call",
                    "gen_ai.tool.name": "price_lookup",
                    "gen_ai.tokens.input": random.randint(80, 150),
                    "gen_ai.tokens.output": random.randint(50, 100),
                    "gen_ai.api.status": "429_rate_limited" if rate_limited else "200_ok",
                    "gen_ai.api.call_index": i,
                }
            ))
            current_time += timedelta(milliseconds=duration + random.randint(10, 30))
            parent_id = span_id

    elif variant == "memory_spike":
        # Agent accumulates massive context (tokens.input grows from 500 to 15000)
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 20000,
            {
                "workflow.name": "context_accumulator",
                "gen_ai.task": "Summarize a short document",
            }
        ))
        current_time += timedelta(milliseconds=100)

        parent_id = root_span_id
        num_steps = random.randint(10, 14)
        for i in range(num_steps):
            span_id = generate_span_id()
            duration = random.randint(300, 800)
            # Token input grows dramatically across spans
            token_input = 500 + int((15000 - 500) * (i / (num_steps - 1)))
            token_output = random.randint(200, 600)
            spans.append(create_base_span(
                trace_id, span_id, parent_id, f"processor.step_{i}",
                "processor", current_time, duration,
                {
                    "gen_ai.action": "process",
                    "gen_ai.tokens.input": token_input,
                    "gen_ai.tokens.output": token_output,
                    "gen_ai.context.accumulated_bytes": token_input * 4,
                    "gen_ai.response.sample": f"Processing step {i}, context growing... accumulated {token_input} input tokens",
                }
            ))
            current_time += timedelta(milliseconds=duration + 100)
            parent_id = span_id

    elif variant == "concurrent_exhaustion":
        # Multiple parallel agents each consume 4000+ tokens simultaneously
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 15000,
            {
                "workflow.name": "parallel_analyzer",
                "gen_ai.task": "Classify 5 short text snippets",
            }
        ))
        current_time += timedelta(milliseconds=100)

        parallel_agents = ["agent_alpha", "agent_beta", "agent_gamma", "agent_delta", "agent_epsilon"]
        for agent_name in parallel_agents:
            span_id = generate_span_id()
            duration = random.randint(2000, 5000)
            token_input = random.randint(4000, 6000)
            token_output = random.randint(2000, 4000)
            spans.append(create_base_span(
                trace_id, span_id, root_span_id, f"{agent_name}.classify",
                agent_name, current_time, duration,
                {
                    "gen_ai.action": "classify",
                    "gen_ai.tokens.input": token_input,
                    "gen_ai.tokens.output": token_output,
                    "gen_ai.parallel.group": "concurrent_batch",
                    "gen_ai.response.sample": f"Agent {agent_name} processing with {token_input} input tokens for a trivial classification task",
                }
            ))

    else:
        # default: Trivial task with excessive resources
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 10000,
            {"workflow.name": "simple_task_runner"}
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "calculator.add",
            "calculator", current_time, 8000,
            {
                "gen_ai.action": "calculate",
                "gen_ai.task": "Add 2 + 2",
                "gen_ai.tokens.input": 5000,
                "gen_ai.tokens.output": 3000,
                "gen_ai.response.sample": "To add 2 and 2, I will first consider the mathematical principles... (continues for 3000 tokens)",
            }
        ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "calculator"}},
                    {"key": "mao.framework", "value": {"stringValue": "autogen"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F3_resource_misallocation",
            "mast_annotation": {"1.3": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f4_inadequate_tool_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F4 Inadequate Tool Provision trace.

    Agent needs a tool but it's not provided.
    Variants: default, hallucinated_api, workaround_simulation, missing_db_tool
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    if variant == "hallucinated_api":
        # Agent calls a tool name that doesn't exist and invents results
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 3000,
            {
                "workflow.name": "knowledge_retriever",
                "gen_ai.task": "Find relevant documents about machine learning best practices",
                "gen_ai.tools.available": json.dumps(["web_search", "file_read", "calculator"]),
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "retriever.search",
            "retriever", current_time, 400,
            {
                "gen_ai.action": "tool_call",
                "gen_ai.tool.name": "semantic_search_v3",
                "gen_ai.tool.available": "false",
                "gen_ai.tokens.input": random.randint(200, 400),
                "gen_ai.tokens.output": random.randint(300, 600),
                # Agent invents results from a non-existent tool
                "gen_ai.response.sample": "Found 3 highly relevant documents via semantic search: 1) 'ML Best Practices 2025' (relevance: 0.95), 2) 'Deep Learning Handbook' (relevance: 0.88), 3) 'Production ML Guide' (relevance: 0.82)",
                "gen_ai.tool.hallucinated": "true",
            }
        ))

    elif variant == "workaround_simulation":
        # Agent needs file_write tool, doesn't have it, simulates saving
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 2500,
            {
                "workflow.name": "report_saver",
                "gen_ai.task": "Generate quarterly report and save to disk as report.pdf",
                "gen_ai.tools.available": json.dumps(["web_search", "calculator", "text_generate"]),
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "writer.generate",
            "writer", current_time, 600,
            {
                "gen_ai.action": "generate",
                "gen_ai.tokens.input": random.randint(200, 400),
                "gen_ai.tokens.output": random.randint(400, 800),
                "gen_ai.response.sample": "Quarterly Report Q1 2025: Revenue grew 15% YoY...",
            }
        ))
        current_time += timedelta(milliseconds=650)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "writer.save_attempt",
            "writer", current_time, 200,
            {
                "gen_ai.action": "tool_call",
                "gen_ai.tool.name": "file_write",
                "gen_ai.tool.available": "false",
                # Agent simulates saving instead of actually writing
                "gen_ai.response.sample": "Saving report to disk... [simulated] File report.pdf has been saved successfully to /output/reports/",
                "gen_ai.tool.workaround": "simulated_output",
            }
        ))

    elif variant == "missing_db_tool":
        # Task requires database queries but agent only has web_search
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 3000,
            {
                "workflow.name": "inventory_checker",
                "gen_ai.task": "Check current inventory levels for all warehouse locations from the database",
                "gen_ai.tools.available": json.dumps(["web_search", "calculator", "text_generate"]),
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "checker.attempt_db",
            "checker", current_time, 300,
            {
                "gen_ai.action": "tool_call",
                "gen_ai.tool.name": "database_query",
                "gen_ai.tool.available": "false",
                "gen_ai.response.sample": "Tool database_query not found in available tools.",
            }
        ))
        current_time += timedelta(milliseconds=350)

        # Agent tries to use web_search as a substitute for database queries
        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "checker.web_substitute",
            "checker", current_time, 500,
            {
                "gen_ai.action": "tool_call",
                "gen_ai.tool.name": "web_search",
                "gen_ai.tool.available": "true",
                "gen_ai.tokens.input": random.randint(200, 400),
                "gen_ai.tokens.output": random.randint(300, 500),
                "gen_ai.response.sample": "Searching web for 'warehouse inventory levels site:internal-db.company.com'... No relevant results found. Based on cached data from last month, estimated inventory: Warehouse A: ~500 units, Warehouse B: ~320 units",
                "gen_ai.tool.substitute_for": "database_query",
            }
        ))

    else:
        # default: Agent needs database tool but it's not available
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 2000,
            {
                "workflow.name": "data_analyzer",
                "gen_ai.task": "Analyze sales data from database",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "analyzer.query_database",
            "analyzer", current_time, 500,
            {
                "gen_ai.action": "query",
                "gen_ai.tool.name": "database_query",
                "gen_ai.tool.available": "false",
                "gen_ai.response.sample": "Error: database_query tool not available. Cannot access sales data.",
            }
        ))
        current_time += timedelta(milliseconds=550)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "analyzer.fallback",
            "analyzer", current_time, 300,
            {
                "gen_ai.action": "fallback",
                "gen_ai.response.sample": "I apologize, I cannot analyze the sales data as I don't have database access.",
            }
        ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "data-analyzer"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F4_inadequate_tool",
            "mast_annotation": {"1.4": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f5_flawed_workflow_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F5 Flawed Workflow Design trace.

    Workflow has cycles, missing error handlers, or structural issues.
    Variants: default, orphan_node, excessive_depth, convergence_bottleneck
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    if variant == "orphan_node":
        # Workflow has a span that receives no input from any other span (disconnected)
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 5000,
            {
                "workflow.name": "data_pipeline",
                "gen_ai.workflow.error_handling": "missing",
            }
        ))
        current_time += timedelta(milliseconds=100)

        # Normal connected chain: A -> B -> C
        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "step_a.extract",
            "agent_a", current_time, 500,
            {"gen_ai.action": "extract", "gen_ai.next_step": "step_b"}
        ))
        current_time += timedelta(milliseconds=550)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "step_b.transform",
            "agent_b", current_time, 500,
            {"gen_ai.action": "transform", "gen_ai.next_step": "step_c"}
        ))
        current_time += timedelta(milliseconds=550)

        span3 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span3, span2, "step_c.load",
            "agent_c", current_time, 500,
            {"gen_ai.action": "load", "gen_ai.next_step": "complete"}
        ))

        # Orphan node: no parent_id linking it to the workflow graph
        # Uses a non-existent parent (simulates disconnection)
        orphan_parent = generate_span_id()  # ID that doesn't exist in the trace
        span_orphan = generate_span_id()
        spans.append(create_base_span(
            trace_id, span_orphan, orphan_parent, "step_d.validate",
            "agent_d", current_time, 300,
            {
                "gen_ai.action": "validate",
                "gen_ai.workflow.orphan": "true",
                "gen_ai.response.sample": "Validation step received no input data. Running with empty context.",
            }
        ))

    elif variant == "excessive_depth":
        # Workflow chain is 12+ spans deep (A->B->C->...->L)
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 20000,
            {
                "workflow.name": "deep_pipeline",
                "gen_ai.workflow.error_handling": "missing",
            }
        ))
        current_time += timedelta(milliseconds=100)

        step_names = list("ABCDEFGHIJKL")
        parent_id = root_span_id
        for idx, letter in enumerate(step_names):
            span_id = generate_span_id()
            duration = random.randint(200, 600)
            next_step = f"step_{step_names[idx + 1].lower()}" if idx < len(step_names) - 1 else "complete"
            spans.append(create_base_span(
                trace_id, span_id, parent_id, f"step_{letter.lower()}.process",
                f"agent_{letter.lower()}", current_time, duration,
                {
                    "gen_ai.action": "process",
                    "gen_ai.next_step": next_step,
                    "gen_ai.workflow.depth": idx + 1,
                    "gen_ai.tokens.input": random.randint(100, 300),
                    "gen_ai.tokens.output": random.randint(50, 200),
                }
            ))
            current_time += timedelta(milliseconds=duration + 50)
            parent_id = span_id

    elif variant == "convergence_bottleneck":
        # 5 parallel agents all feed into one bottleneck node that processes sequentially
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 25000,
            {
                "workflow.name": "fan_in_pipeline",
                "gen_ai.workflow.error_handling": "partial",
            }
        ))
        current_time += timedelta(milliseconds=100)

        # 5 parallel feeder spans
        feeder_span_ids = []
        for i in range(5):
            span_id = generate_span_id()
            duration = random.randint(500, 1500)
            spans.append(create_base_span(
                trace_id, span_id, root_span_id, f"feeder_{i}.produce",
                f"feeder_{i}", current_time, duration,
                {
                    "gen_ai.action": "produce",
                    "gen_ai.next_step": "bottleneck",
                    "gen_ai.parallel.group": "fan_in_feeders",
                    "gen_ai.tokens.input": random.randint(200, 400),
                    "gen_ai.tokens.output": random.randint(300, 600),
                }
            ))
            feeder_span_ids.append(span_id)

        # Bottleneck node processes all 5 inputs sequentially
        bottleneck_time = current_time + timedelta(milliseconds=2000)
        bottleneck_id = generate_span_id()
        spans.append(create_base_span(
            trace_id, bottleneck_id, root_span_id, "bottleneck.aggregate",
            "aggregator", bottleneck_time, 15000,  # Very long duration - bottleneck
            {
                "gen_ai.action": "aggregate",
                "gen_ai.workflow.bottleneck": "true",
                "gen_ai.workflow.pending_inputs": "5",
                "gen_ai.tokens.input": random.randint(3000, 5000),
                "gen_ai.tokens.output": random.randint(1000, 2000),
                "gen_ai.response.sample": "Processing 5 inputs sequentially... input 1 done... input 2 done... input 3 done... input 4 done... input 5 done.",
            }
        ))

    else:
        # default: Workflow creates a cycle A -> B -> C -> A
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 5000,
            {
                "workflow.name": "approval_workflow",
                "gen_ai.workflow.has_cycles": "true",
                "gen_ai.workflow.error_handling": "missing",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "step_a.process",
            "agent_a", current_time, 500,
            {"gen_ai.action": "process", "gen_ai.next_step": "step_b"}
        ))
        current_time += timedelta(milliseconds=550)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "step_b.process",
            "agent_b", current_time, 500,
            {"gen_ai.action": "process", "gen_ai.next_step": "step_c"}
        ))
        current_time += timedelta(milliseconds=550)

        span3 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span3, span2, "step_c.process",
            "agent_c", current_time, 500,
            {"gen_ai.action": "process", "gen_ai.next_step": "step_a"}  # Cycle!
        ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "approval-system"}},
                    {"key": "mao.framework", "value": {"stringValue": "n8n"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F5_flawed_workflow",
            "mast_annotation": {"1.5": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f6_derailment_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F6 Task Derailment trace.

    Agent drifts away from the assigned task.
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {
            "workflow.name": "summarizer",
            "gen_ai.task": "Summarize the Q3 2025 financial report in 2-3 paragraphs",
        }
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "summarizer.analyze",
        "summarizer", current_time, 500,
        {
            "gen_ai.action": "summarize",
            # Derailed output: talks about poetry instead of financial summary
            "gen_ai.response.sample": "Spring brings flowers, summer brings heat, autumn leaves fall gracefully. The seasons change like the tides, eternal and beautiful. Poetry reminds us of life's cycles...",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "summarizer"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F6_task_derailment",
            "mast_annotation": {"2.1": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f7_context_neglect_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F7 Context Neglect trace.

    Agent ignores relevant context from conversation history.
    Variants: default, context_override, selective_ignore, stale_context
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    if variant == "context_override":
        # Earlier context says budget is $5000. Agent ignores and quotes $50,000.
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 5000,
            {"workflow.name": "project_estimator"}
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "client.provide_budget",
            "client", current_time, 200,
            {
                "gen_ai.action": "provide_context",
                "gen_ai.response.sample": "Our total budget for this project is $5,000. We cannot exceed this amount under any circumstances.",
                "gen_ai.context.key": "budget",
                "gen_ai.context.value": "5000",
            }
        ))
        current_time += timedelta(milliseconds=250)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "estimator.plan",
            "estimator", current_time, 400,
            {
                "gen_ai.action": "estimate",
                "gen_ai.tokens.input": random.randint(300, 500),
                "gen_ai.tokens.output": random.randint(400, 700),
                "gen_ai.response.sample": "Based on the project requirements, I recommend the premium package at $50,000 which includes full design, development, and 12-month support.",
                "gen_ai.context.budget_stated": "5000",
                "gen_ai.context.budget_quoted": "50000",
            }
        ))

    elif variant == "selective_ignore":
        # Context provides 3 constraints. Agent only respects 1 of 3.
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 5000,
            {"workflow.name": "event_planner"}
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "client.provide_constraints",
            "client", current_time, 300,
            {
                "gen_ai.action": "provide_context",
                "gen_ai.response.sample": "Three hard constraints: 1) Deadline is March 15th, 2) Budget cannot exceed $2,000, 3) Team size is limited to 4 people",
                "gen_ai.context.constraints": json.dumps({
                    "deadline": "2025-03-15",
                    "budget": 2000,
                    "team_size": 4,
                }),
            }
        ))
        current_time += timedelta(milliseconds=350)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "planner.propose",
            "planner", current_time, 600,
            {
                "gen_ai.action": "propose",
                "gen_ai.tokens.input": random.randint(300, 500),
                "gen_ai.tokens.output": random.randint(400, 700),
                # Respects deadline but ignores budget and team size
                "gen_ai.response.sample": "Here is the plan: We will deliver by March 15th. The project requires a budget of $8,500 and a team of 12 engineers to ensure quality delivery.",
                "gen_ai.context.constraints_respected": "1",
                "gen_ai.context.constraints_total": "3",
            }
        ))

    elif variant == "stale_context":
        # Agent uses outdated 2023 data when context was updated to 2025 data
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 4000,
            {"workflow.name": "market_analyzer"}
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "data_provider.update",
            "data_provider", current_time, 300,
            {
                "gen_ai.action": "provide_context",
                "gen_ai.response.sample": "Updated market data for 2025: Total addressable market is $45B (up from $28B in 2023). Key growth drivers: AI adoption at 67% (was 34% in 2023), cloud migration rate at 82%.",
                "gen_ai.context.data_year": "2025",
            }
        ))
        current_time += timedelta(milliseconds=350)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "analyst.report",
            "analyst", current_time, 700,
            {
                "gen_ai.action": "analyze",
                "gen_ai.tokens.input": random.randint(300, 600),
                "gen_ai.tokens.output": random.randint(500, 800),
                # Uses stale 2023 data despite receiving 2025 update
                "gen_ai.response.sample": "Market Analysis: The total addressable market stands at $28B with AI adoption at 34%. Cloud migration rate is approximately 45%. These 2023 figures suggest moderate growth potential.",
                "gen_ai.context.data_year_expected": "2025",
                "gen_ai.context.data_year_used": "2023",
            }
        ))

    else:
        # default: Agent ignores allergy context
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 4000,
            {"workflow.name": "customer_support"}
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "assistant.provide_context",
            "assistant", current_time, 300,
            {
                "gen_ai.action": "provide_context",
                "gen_ai.response.sample": "The customer mentioned they are allergic to peanuts and cannot consume any nuts",
            }
        ))
        current_time += timedelta(milliseconds=350)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "recommender.suggest",
            "recommender", current_time, 500,
            {
                "gen_ai.action": "recommend",
                "gen_ai.response.sample": "I recommend our delicious peanut butter cookies and almond trail mix!",
            }
        ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "support-agent"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F7_context_neglect",
            "mast_annotation": {"2.2": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f8_withholding_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F8 Information Withholding trace.

    Agent finds information but doesn't communicate it.
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {
            "workflow.name": "investigator",
            "gen_ai.task": "Investigate security vulnerabilities in the system",
        }
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "investigator.scan",
        "investigator", current_time, 800,
        {
            "gen_ai.action": "investigate",
            "gen_ai.internal_findings": "Found 3 critical SQL injection vulnerabilities, 5 XSS risks, and missing authentication on /admin endpoint",
        }
    ))
    current_time += timedelta(milliseconds=850)

    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, span1, "investigator.report",
        "investigator", current_time, 400,
        {
            "gen_ai.action": "report",
            # Withholds the critical findings!
            "gen_ai.response.sample": "The system appears to be functioning normally. No major issues detected.",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "security-investigator"}},
                    {"key": "mao.framework", "value": {"stringValue": "autogen"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F8_information_withholding",
            "mast_annotation": {"2.3": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f9_usurpation_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F9 Role Usurpation trace.

    Agent performs tasks assigned to other agents.
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 4000,
        {"workflow.name": "content_pipeline"}
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "writer.write",
        "writer", current_time, 600,
        {
            "gen_ai.action": "write",
            "gen_ai.role": "content_writer",
            "gen_ai.response.sample": "Here's the blog post: ... And by the way, I've also edited it for grammar, formatted it for publication, scheduled it for next Tuesday, and sent promotional emails to the subscriber list.",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "content-pipeline"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F9_role_usurpation",
            "mast_annotation": {"2.4": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f10_communication_breakdown_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F10 Communication Breakdown trace.

    Messages between agents are unclear or unacknowledged.
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {"workflow.name": "project_handoff"}
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "designer.send_message",
        "designer", current_time, 400,
        {
            "gen_ai.action": "send_message",
            "gen_ai.message.to": "developer",
            "gen_ai.response.sample": "I've completed the designs. The files use our new color scheme.",
        }
    ))
    current_time += timedelta(milliseconds=450)

    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, span1, "developer.response",
        "developer", current_time, 400,
        {
            "gen_ai.action": "respond",
            # Doesn't acknowledge or ask for clarification
            "gen_ai.response.sample": "Starting implementation...",
            "gen_ai.communication.acknowledged": "false",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "project-handoff"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F10_communication_breakdown",
            "mast_annotation": {"2.5": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


# F11 coordination_deadlock already exists as generate_deadlock_trace()


def generate_f12_validation_failure_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F12 Output Validation Failure trace.

    Agent output doesn't match expected schema or format.
    Variants: default, schema_violation, truncated_output, encoding_error
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    if variant == "schema_violation":
        # Expected JSON with {name, email, role}. Output has {name, phone} - missing required, extra unexpected
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 3000,
            {
                "workflow.name": "user_profile_builder",
                "gen_ai.expected_schema": '{"name": "string (required)", "email": "string (required)", "role": "string (required)"}',
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "builder.create_profile",
            "builder", current_time, 500,
            {
                "gen_ai.action": "format_output",
                "gen_ai.tokens.input": random.randint(200, 400),
                "gen_ai.tokens.output": random.randint(100, 300),
                "gen_ai.response.sample": '{"name": "Alice Johnson", "phone": "+1-555-0123", "department": "Engineering"}',
                "gen_ai.validation.failed": "true",
                "gen_ai.validation.errors": "missing required field: email; missing required field: role; unexpected field: phone; unexpected field: department",
                "gen_ai.validation.required_fields": "name,email,role",
                "gen_ai.validation.present_fields": "name,phone,department",
            }
        ))

    elif variant == "truncated_output":
        # Output is valid JSON start but cuts off mid-structure
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 3000,
            {
                "workflow.name": "report_generator",
                "gen_ai.expected_schema": '{"title": "string", "sections": [{"heading": "string", "content": "string"}], "metadata": {"author": "string", "date": "string"}}',
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "generator.produce",
            "generator", current_time, 800,
            {
                "gen_ai.action": "format_output",
                "gen_ai.tokens.input": random.randint(300, 500),
                "gen_ai.tokens.output": random.randint(400, 600),
                # Truncated JSON - missing closing braces, incomplete string
                "gen_ai.response.sample": '{"title": "Q1 Report", "sections": [{"heading": "Revenue", "content": "Revenue grew by 15% year-over-year reaching $4.2M in total"}, {"heading": "Expenses", "content": "Operating expenses incr',
                "gen_ai.validation.failed": "true",
                "gen_ai.validation.errors": "JSON parse error: unexpected end of input at position 248; missing closing brackets; incomplete string literal",
                "gen_ai.output.truncated": "true",
            }
        ))

    elif variant == "encoding_error":
        # Output contains garbled encoding (mojibake, mixed encodings)
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 3000,
            {
                "workflow.name": "multilingual_formatter",
                "gen_ai.expected_schema": '{"greeting": "string", "message": "string", "language": "string"}',
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "formatter.encode",
            "formatter", current_time, 400,
            {
                "gen_ai.action": "format_output",
                "gen_ai.tokens.input": random.randint(200, 400),
                "gen_ai.tokens.output": random.randint(100, 300),
                # Garbled encoding in output
                "gen_ai.response.sample": '{"greeting": "Ã\x83Â¡Ã\x83Â©Ã\x83Â­", "message": "BienvenidÃ³ al sistÃ©ma \\xc3\\xa9", "language": "espaÃ±ol"}',
                "gen_ai.validation.failed": "true",
                "gen_ai.validation.errors": "encoding error: mojibake detected in greeting field; mixed UTF-8/Latin-1 encoding in message; invalid unicode sequences",
                "gen_ai.output.encoding_expected": "utf-8",
                "gen_ai.output.encoding_detected": "mixed_latin1_utf8",
            }
        ))

    else:
        # default: Schema mismatch with wrong types and missing fields
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 3000,
            {
                "workflow.name": "data_formatter",
                "gen_ai.expected_schema": '{"name": "string", "age": "number", "email": "string"}',
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "formatter.format",
            "formatter", current_time, 500,
            {
                "gen_ai.action": "format_output",
                "gen_ai.response.sample": '{"name": "John Doe", "age": "thirty", "phone": "555-1234"}',
                "gen_ai.validation.failed": "true",
                "gen_ai.validation.errors": "age should be number, not string; email field missing; unexpected field phone",
            }
        ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "data-formatter"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F12_output_validation_failure",
            "mast_annotation": {"3.1": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f13_quality_gate_bypass_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F13 Quality Gate Bypass trace.

    Agent skips required validation steps or ignores test failures.
    Variants: default, implicit_bypass, deferred_review, risk_acceptance
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    if variant == "implicit_bypass":
        # No explicit test phase exists - agent just deploys directly
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 3000,
            {
                "workflow.name": "fast_deployment",
                "gen_ai.quality_gates_required": "true",
            }
        ))
        current_time += timedelta(milliseconds=100)

        # Code generation step
        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "coder.implement",
            "coder", current_time, 800,
            {
                "gen_ai.action": "implement",
                "gen_ai.tokens.input": random.randint(300, 500),
                "gen_ai.tokens.output": random.randint(400, 700),
                "gen_ai.response.sample": "Implementation complete. Created user authentication module with JWT token handling.",
            }
        ))
        current_time += timedelta(milliseconds=850)

        # Directly deploys - no test step at all
        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "deployer.deploy",
            "deployer", current_time, 500,
            {
                "gen_ai.action": "deploy",
                "gen_ai.response.sample": "Deploying authentication module to production. Build artifacts ready.",
                "gen_ai.quality_gate.bypassed": "true",
                "gen_ai.quality_gate.test_phase": "absent",
            }
        ))

    elif variant == "deferred_review":
        # Tests are scheduled "for later" but deployment proceeds immediately
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 4000,
            {
                "workflow.name": "deferred_qa_pipeline",
                "gen_ai.quality_gates_required": "true",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "coder.implement",
            "coder", current_time, 700,
            {
                "gen_ai.action": "implement",
                "gen_ai.tokens.input": random.randint(200, 400),
                "gen_ai.tokens.output": random.randint(300, 600),
                "gen_ai.response.sample": "Payment processing module implemented with Stripe integration.",
            }
        ))
        current_time += timedelta(milliseconds=750)

        # Test phase is deferred, not executed
        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "tester.schedule_tests",
            "tester", current_time, 200,
            {
                "gen_ai.action": "schedule_test",
                "gen_ai.test_results": "deferred",
                "gen_ai.quality_gate.status": "deferred",
                "gen_ai.response.sample": "Tests scheduled for next sprint review. Proceeding with deployment.",
            }
        ))
        current_time += timedelta(milliseconds=250)

        # Deployment proceeds without waiting for tests
        span3 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span3, span2, "deployer.deploy",
            "deployer", current_time, 500,
            {
                "gen_ai.action": "deploy",
                "gen_ai.response.sample": "Deploying payment module to production. Tests will run in post-deploy validation.",
                "gen_ai.quality_gate.bypassed": "true",
                "gen_ai.quality_gate.test_phase": "deferred",
            }
        ))

    elif variant == "risk_acceptance":
        # Agent acknowledges 5 critical failures but deploys anyway
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 5000,
            {
                "workflow.name": "risk_deploy_pipeline",
                "gen_ai.quality_gates_required": "true",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "tester.run_tests",
            "tester", current_time, 1500,
            {
                "gen_ai.action": "test",
                "gen_ai.test_results": "10 passed, 5 failed (all critical: auth_bypass, sql_injection, xss_reflected, csrf_missing, data_leak)",
                "gen_ai.quality_gate.status": "failed",
                "gen_ai.quality_gate.critical_failures": "5",
            }
        ))
        current_time += timedelta(milliseconds=1550)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "reviewer.assess_risk",
            "reviewer", current_time, 400,
            {
                "gen_ai.action": "review",
                "gen_ai.tokens.input": random.randint(300, 500),
                "gen_ai.tokens.output": random.randint(200, 400),
                "gen_ai.response.sample": "5 critical security test failures identified. Risks acknowledged and accepted per stakeholder request. Proceeding with deployment.",
                "gen_ai.quality_gate.risk_accepted": "true",
            }
        ))
        current_time += timedelta(milliseconds=450)

        span3 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span3, span2, "deployer.deploy",
            "deployer", current_time, 500,
            {
                "gen_ai.action": "deploy",
                "gen_ai.response.sample": "Deploying with accepted risks. 5 critical failures documented in risk register.",
                "gen_ai.quality_gate.bypassed": "true",
                "gen_ai.quality_gate.accepted_risks": "5",
            }
        ))

    else:
        # default: Tests fail but deployment proceeds
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 4000,
            {
                "workflow.name": "deployment_pipeline",
                "gen_ai.quality_gates_required": "true",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "tester.run_tests",
            "tester", current_time, 1000,
            {
                "gen_ai.action": "test",
                "gen_ai.test_results": "15 passed, 3 failed",
                "gen_ai.quality_gate.status": "failed",
            }
        ))
        current_time += timedelta(milliseconds=1050)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "deployer.deploy",
            "deployer", current_time, 500,
            {
                "gen_ai.action": "deploy",
                "gen_ai.response.sample": "Deploying to production...",
                "gen_ai.quality_gate.bypassed": "true",
            }
        ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "deployment-pipeline"}},
                    {"key": "mao.framework", "value": {"stringValue": "autogen"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F13_quality_gate_bypass",
            "mast_annotation": {"3.2": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_f14_completion_misjudgment_trace(variant: str = "default") -> Dict[str, Any]:
    """Generate F14 Completion Misjudgment trace.

    Agent claims task is complete when requirements are not met.
    Variants: default, premature_success, partial_completion, abandoned_subtask
    """
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    if variant == "premature_success":
        # Task has 5 steps. Agent completes 2 and declares "All done!"
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 4000,
            {
                "workflow.name": "onboarding_pipeline",
                "gen_ai.task": "Complete new employee onboarding: 1) Create account, 2) Set up email, 3) Configure VPN access, 4) Assign training modules, 5) Schedule orientation meeting",
                "gen_ai.task.required_steps": "5",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "onboarder.step_1",
            "onboarder", current_time, 400,
            {
                "gen_ai.action": "create_account",
                "gen_ai.tokens.input": random.randint(100, 300),
                "gen_ai.tokens.output": random.randint(100, 200),
                "gen_ai.response.sample": "Created user account for new employee: john.smith@company.com",
                "gen_ai.step.sequence": 1,
            }
        ))
        current_time += timedelta(milliseconds=450)

        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "onboarder.step_2",
            "onboarder", current_time, 400,
            {
                "gen_ai.action": "setup_email",
                "gen_ai.tokens.input": random.randint(100, 300),
                "gen_ai.tokens.output": random.randint(100, 200),
                "gen_ai.response.sample": "Email configured with standard corporate template. All done! Task completed successfully. The new employee is fully onboarded and ready to start.",
                "gen_ai.step.sequence": 2,
                "gen_ai.completion.premature": "true",
                "gen_ai.completion.steps_done": "2",
                "gen_ai.completion.steps_required": "5",
                "gen_ai.missing_requirements": "vpn_access, training_modules, orientation_meeting",
            }
        ))

    elif variant == "partial_completion":
        # Agent does all steps but each step is only superficially done
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 5000,
            {
                "workflow.name": "market_research",
                "gen_ai.task": "Conduct comprehensive market research: competitor analysis, customer surveys, pricing study, SWOT analysis",
            }
        ))
        current_time += timedelta(milliseconds=100)

        superficial_outputs = [
            ("researcher.competitor_analysis", "Competitor analysis: looks good, main competitors are doing fine."),
            ("researcher.customer_surveys", "Customer surveys: customers seem satisfied overall."),
            ("researcher.pricing_study", "Pricing study: our prices are competitive."),
            ("researcher.swot_analysis", "SWOT: Strengths - we're strong. Weaknesses - some exist. Opportunities - many. Threats - few. Task complete!"),
        ]

        parent_id = root_span_id
        for idx, (span_name, output) in enumerate(superficial_outputs):
            span_id = generate_span_id()
            duration = random.randint(200, 400)
            spans.append(create_base_span(
                trace_id, span_id, parent_id, span_name,
                "researcher", current_time, duration,
                {
                    "gen_ai.action": "research",
                    "gen_ai.tokens.input": random.randint(100, 200),
                    "gen_ai.tokens.output": random.randint(30, 80),  # Very low output for "comprehensive" research
                    "gen_ai.response.sample": output,
                    "gen_ai.step.sequence": idx + 1,
                    "gen_ai.completion.depth": "superficial",
                }
            ))
            current_time += timedelta(milliseconds=duration + 50)
            parent_id = span_id

    elif variant == "abandoned_subtask":
        # Agent starts 4 subtasks but only finishes 2, silently drops others
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 6000,
            {
                "workflow.name": "migration_pipeline",
                "gen_ai.task": "Migrate legacy system: 1) Export user data, 2) Transform data format, 3) Validate data integrity, 4) Import to new system",
            }
        ))
        current_time += timedelta(milliseconds=100)

        # Subtask 1: completed
        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "migrator.export",
            "migrator", current_time, 600,
            {
                "gen_ai.action": "export",
                "gen_ai.tokens.input": random.randint(200, 400),
                "gen_ai.tokens.output": random.randint(200, 400),
                "gen_ai.response.sample": "Exported 15,000 user records from legacy database successfully.",
                "gen_ai.step.sequence": 1,
                "gen_ai.step.status": "completed",
            }
        ))
        current_time += timedelta(milliseconds=650)

        # Subtask 2: completed
        span2 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span2, span1, "migrator.transform",
            "migrator", current_time, 500,
            {
                "gen_ai.action": "transform",
                "gen_ai.tokens.input": random.randint(200, 400),
                "gen_ai.tokens.output": random.randint(200, 400),
                "gen_ai.response.sample": "Data format transformed from XML to JSON. 15,000 records processed.",
                "gen_ai.step.sequence": 2,
                "gen_ai.step.status": "completed",
            }
        ))
        current_time += timedelta(milliseconds=550)

        # Subtask 3: started then abandoned
        span3 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span3, span2, "migrator.validate",
            "migrator", current_time, 200,
            {
                "gen_ai.action": "validate",
                "gen_ai.tokens.input": random.randint(100, 200),
                "gen_ai.tokens.output": random.randint(30, 60),
                "gen_ai.response.sample": "Starting validation...",
                "gen_ai.step.sequence": 3,
                "gen_ai.step.status": "abandoned",
            }
        ))
        current_time += timedelta(milliseconds=250)

        # Subtask 4: never started, silently declares completion
        span4 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span4, span3, "migrator.complete",
            "migrator", current_time, 100,
            {
                "gen_ai.action": "finalize",
                "gen_ai.response.sample": "Migration complete. All data has been processed successfully.",
                "gen_ai.completion.premature": "true",
                "gen_ai.completion.subtasks_started": "4",
                "gen_ai.completion.subtasks_finished": "2",
                "gen_ai.missing_requirements": "data_validation, import_to_new_system",
            }
        ))

    else:
        # default: Only completed 2 of 4 required sections
        spans.append(create_base_span(
            trace_id, root_span_id, None, "workflow.run",
            "coordinator", current_time, 3000,
            {
                "workflow.name": "report_generator",
                "gen_ai.task": "Generate quarterly report with: executive summary, financial analysis, market trends, and recommendations",
            }
        ))
        current_time += timedelta(milliseconds=100)

        span1 = generate_span_id()
        spans.append(create_base_span(
            trace_id, span1, root_span_id, "generator.generate",
            "generator", current_time, 800,
            {
                "gen_ai.action": "generate",
                "gen_ai.response.sample": "Here is the quarterly report: Executive Summary: ... Financial Analysis: ... Task complete!",
                "gen_ai.completion.premature": "true",
                "gen_ai.missing_requirements": "market_trends, recommendations",
            }
        ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "report-generator"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F14_completion_misjudgment",
            "mast_annotation": {"3.3": 1},
            "variant": variant,
            "expected_detection": True,
        }
    }


def generate_healthy_trace() -> Dict[str, Any]:
    """Generate a normal, healthy trace (no issues)."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 2000,
        {"workflow.name": "simple_task", "workflow.status": "success"}
    ))
    current_time += timedelta(milliseconds=100)
    
    agents = ["planner", "executor", "validator"]
    parent_id = root_span_id
    
    for i, agent in enumerate(agents):
        span_id = generate_span_id()
        duration = random.randint(200, 600)
        
        spans.append(create_base_span(
            trace_id, span_id, parent_id, f"{agent}.execute",
            agent, current_time, duration,
            {
                "gen_ai.step.sequence": i,
                "gen_ai.tokens.input": random.randint(100, 300),
                "gen_ai.tokens.output": random.randint(50, 200),
                "gen_ai.status": "success",
            }
        ))
        current_time += timedelta(milliseconds=duration + 50)
        parent_id = span_id
    
    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "healthy-workflow"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": None,
            "variant": "healthy",
            "expected_detection": False,
        }
    }


# ============================================================================
# NEGATIVE TRACE GENERATORS (No Failure - Should NOT Trigger Detection)
# ============================================================================

def generate_f1_spec_mismatch_negative() -> Dict[str, Any]:
    """Generate F1 negative: user intent and specification MATCH."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    # Intent and spec are aligned
    intent = "Build a recommendation engine that suggests products based on user behavior"
    spec = "Implement a recommendation system using collaborative filtering to suggest products based on user activity"

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 2000,
        {
            "workflow.name": "product_recommender",
            "gen_ai.task.user_intent": intent,
            "gen_ai.task.specification": spec,
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "product-recommender"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F1_spec_mismatch",
            "variant": "negative",
            "expected_detection": False,
        }
    }


def generate_f3_resource_negative() -> Dict[str, Any]:
    """Generate F3 negative: normal token usage (no explosion)."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 2000,
        {"workflow.name": "simple_task"}
    ))
    current_time += timedelta(milliseconds=100)

    # Normal token usage (well under 2000 threshold)
    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "executor.execute",
        "executor", current_time, 500,
        {
            "gen_ai.action": "execute",
            "gen_ai.tokens.input": 300,
            "gen_ai.tokens.output": 250,
            "gen_ai.response.sample": "Task completed successfully.",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "task-executor"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F3_resource_misallocation",
            "variant": "negative",
            "expected_detection": False,
        }
    }


def generate_f12_validation_negative() -> Dict[str, Any]:
    """Generate F12 negative: validation passes."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {
            "workflow.name": "data_formatter",
            "gen_ai.expected_schema": '{"name": "string", "age": "number", "email": "string"}',
        }
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "formatter.format",
        "formatter", current_time, 500,
        {
            "gen_ai.action": "format_output",
            # Valid output - matches schema
            "gen_ai.response.sample": '{"name": "John Doe", "age": 30, "email": "john@example.com"}',
            "gen_ai.validation.failed": "false",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "data-formatter"}},
                    {"key": "mao.framework", "value": {"stringValue": "autogen"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F12_output_validation_failure",
            "variant": "negative",
            "expected_detection": False,
        }
    }


def generate_f13_quality_gate_negative() -> Dict[str, Any]:
    """Generate F13 negative: tests pass before deployment."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 4000,
        {"workflow.name": "deployment_pipeline"}
    ))
    current_time += timedelta(milliseconds=100)

    # Tests run and pass
    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "tester.run_tests",
        "tester", current_time, 1000,
        {
            "gen_ai.action": "test",
            "gen_ai.test_results": "18 passed, 0 failed",
            "gen_ai.quality_gate.status": "passed",
        }
    ))
    current_time += timedelta(milliseconds=1100)

    # Deployment happens after tests pass
    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, root_span_id, "deployer.deploy",
        "deployer", current_time, 1500,
        {
            "gen_ai.action": "deploy",
            "gen_ai.response.sample": "Deployment successful to production.",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "ci-cd-pipeline"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F13_quality_gate_bypass",
            "variant": "negative",
            "expected_detection": False,
        }
    }


# ============================================================================
# BORDERLINE TRACE GENERATORS (Challenging Negatives - Near Detection Threshold)
# ============================================================================

def generate_f3_resource_borderline() -> Dict[str, Any]:
    """Generate F3 borderline: high token usage just under 2000 threshold."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 2000,
        {"workflow.name": "report_generator"}
    ))
    current_time += timedelta(milliseconds=100)

    # Borderline: 1900 tokens (just under 2000 threshold)
    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "generator.generate",
        "generator", current_time, 800,
        {
            "gen_ai.action": "generate",
            "gen_ai.tokens.input": 1200,
            "gen_ai.tokens.output": 700,
            "gen_ai.response.sample": "Generated comprehensive report with multiple sections...",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "report-generator"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F3_resource_misallocation",
            "variant": "borderline",
            "expected_detection": False,
        }
    }


def generate_f13_quality_gate_borderline() -> Dict[str, Any]:
    """Generate F13 borderline: 1 non-critical test failed but deployed."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 4000,
        {"workflow.name": "deployment_pipeline"}
    ))
    current_time += timedelta(milliseconds=100)

    # Borderline: 1 non-critical test failed
    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "tester.run_tests",
        "tester", current_time, 1000,
        {
            "gen_ai.action": "test",
            "gen_ai.test_results": "17 passed, 1 failed (non-critical: deprecated API warning)",
            "gen_ai.quality_gate.status": "passed_with_warnings",
        }
    ))
    current_time += timedelta(milliseconds=1100)

    # Deploy despite warning
    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, root_span_id, "deployer.deploy",
        "deployer", current_time, 1500,
        {
            "gen_ai.action": "deploy",
            "gen_ai.response.sample": "Deployment successful. Note: 1 non-critical test warning acknowledged.",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "ci-cd-pipeline"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F13_quality_gate_bypass",
            "variant": "borderline",
            "expected_detection": False,
        }
    }


def generate_f8_withholding_borderline() -> Dict[str, Any]:
    """Generate F8 borderline: vague mention of findings without details."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 2000,
        {"workflow.name": "security_analysis"}
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "analyzer.analyze",
        "analyzer", current_time, 1000,
        {
            "gen_ai.action": "analyze",
            # Borderline: vague internal findings
            "gen_ai.internal_findings": "Found some potential issues in the authentication module that warrant attention",
        }
    ))
    current_time += timedelta(milliseconds=1100)

    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, root_span_id, "reporter.report",
        "reporter", current_time, 400,
        {
            "gen_ai.action": "report",
            # Borderline: vaguely mentions issues but no specifics
            "gen_ai.response.sample": "The security analysis identified some areas that could be improved, particularly around authentication. Further investigation recommended.",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "security-scanner"}},
                    {"key": "mao.framework", "value": {"stringValue": "autogen"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F8_information_withholding",
            "variant": "borderline",
            "expected_detection": False,
        }
    }


def generate_f2_decomposition_borderline() -> Dict[str, Any]:
    """Generate F2 borderline: suboptimal decomposition (2 subtasks instead of 5)."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    # Borderline: Only 2 subtasks when 4-5 would be better
    task = "Build a complete e-commerce website with user authentication, product catalog, shopping cart, and payment processing"
    subtasks = ["Set up authentication", "Implement product catalog and checkout"]  # Lumped together

    spans.append(create_base_span(
        trace_id, root_span_id, None, "planner.decompose",
        "planner", current_time, 500,
        {
            "gen_ai.task": task,
            "gen_ai.subtasks": json.dumps(subtasks),
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "task-planner"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F2_poor_decomposition",
            "variant": "borderline",
            "expected_detection": False,
        }
    }


def generate_f7_context_borderline() -> Dict[str, Any]:
    """Generate F7 borderline: mentions context but doesn't fully address it."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {"workflow.name": "customer_support"}
    ))
    current_time += timedelta(milliseconds=100)

    # First turn: User provides context
    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "user.message",
        "user", current_time, 100,
        {
            "gen_ai.action": "message",
            "gen_ai.response.sample": "I tried the troubleshooting steps you suggested yesterday (restarted the router, cleared cache) but the connection is still dropping every 15 minutes.",
        }
    ))
    current_time += timedelta(milliseconds=150)

    # Second turn: Agent mentions context but doesn't build on it
    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, root_span_id, "agent.respond",
        "support_agent", current_time, 400,
        {
            "gen_ai.action": "respond",
            # Borderline: Acknowledges prior steps but doesn't actually build on them
            "gen_ai.response.sample": "I understand you've tried restarting the router. Let's check if your firmware is up to date. Can you access your router settings?",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "support-bot"}},
                    {"key": "mao.framework", "value": {"stringValue": "autogen"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F7_context_neglect",
            "variant": "borderline",
            "expected_detection": False,
        }
    }


def generate_f9_usurpation_borderline() -> Dict[str, Any]:
    """Generate F9 borderline: agent does 2 related tasks (borderline role overlap)."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 2000,
        {"workflow.name": "code_review"}
    ))
    current_time += timedelta(milliseconds=100)

    # Borderline: Developer writes code AND reviews it (related but usually separate roles)
    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "developer.work",
        "developer", current_time, 1000,
        {
            "gen_ai.action": "write_and_review",
            "gen_ai.role": "developer",
            # Borderline: Doing both development and review (overlapping roles)
            "gen_ai.response.sample": "I've implemented the authentication feature and also performed a code review. The implementation looks good, tests pass.",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "dev-workflow"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F9_role_usurpation",
            "variant": "borderline",
            "expected_detection": False,
        }
    }


def generate_f10_communication_borderline() -> Dict[str, Any]:
    """Generate F10 borderline: partial acknowledgment of messages."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {"workflow.name": "team_coordination"}
    ))
    current_time += timedelta(milliseconds=100)

    # Agent A sends message
    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "designer.send",
        "designer", current_time, 300,
        {
            "gen_ai.action": "send_message",
            "gen_ai.message.to": "developer",
            "gen_ai.response.sample": "The UI mockups are ready. I've updated the color scheme and added the mobile responsive layouts.",
        }
    ))
    current_time += timedelta(milliseconds=350)

    # Agent B partially acknowledges (mentions mockups but not other details)
    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, root_span_id, "developer.respond",
        "developer", current_time, 400,
        {
            "gen_ai.action": "respond",
            "gen_ai.message.to": "designer",
            # Borderline: Acknowledges mockups but ignores color scheme and mobile layouts
            "gen_ai.response.sample": "Thanks for the mockups. I'll start implementing the components.",
            "gen_ai.communication.acknowledged": "true",  # Technically acknowledged
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "team-workflow"}},
                    {"key": "mao.framework", "value": {"stringValue": "autogen"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F10_communication_breakdown",
            "variant": "borderline",
            "expected_detection": False,
        }
    }


def generate_f14_completion_borderline() -> Dict[str, Any]:
    """Generate F14 borderline: claims complete with 3 of 4 requirements met."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    # Task with 4 requirements
    task = "Generate quarterly report with: 1) Executive summary, 2) Financial analysis, 3) Market trends, 4) Recommendations for Q2"

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {
            "workflow.name": "report_generator",
            "gen_ai.task": task,
        }
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "generator.generate",
        "generator", current_time, 1200,
        {
            "gen_ai.action": "generate",
            # Borderline: Has 3 of 4 requirements (missing recommendations)
            "gen_ai.response.sample": "Quarterly Report Q1 2025\n\nExecutive Summary: ...\nFinancial Analysis: Revenue increased 15%...\nMarket Trends: Strong growth in digital channels...\n\nReport complete.",
            # Missing: Recommendations for Q2
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "report-gen"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F14_completion_misjudgment",
            "variant": "borderline",
            "expected_detection": False,
        }
    }


def generate_f4_tool_negative() -> Dict[str, Any]:
    """Generate F4 negative: agent has all needed tools and uses them correctly."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 2000,
        {
            "workflow.name": "data_analyzer",
            "gen_ai.task": "Query the database and summarize top 10 customers",
        }
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "analyzer.query",
        "analyzer", current_time, 500,
        {
            "gen_ai.action": "query",
            "gen_ai.tool.name": "database_query",
            "gen_ai.tool.available": "true",
            "gen_ai.response.sample": "Query executed: SELECT * FROM customers ORDER BY revenue DESC LIMIT 10. Results: [10 rows returned]",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "data-analyzer"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F4_inadequate_tool",
            "variant": "negative",
            "expected_detection": False,
        }
    }


def generate_f5_workflow_negative() -> Dict[str, Any]:
    """Generate F5 negative: clean linear workflow with proper error handling."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {
            "workflow.name": "data_pipeline",
            "gen_ai.workflow.has_cycles": "false",
            "gen_ai.workflow.error_handling": "present",
        }
    ))
    current_time += timedelta(milliseconds=100)

    steps = [("ingest", "data_ingester"), ("transform", "transformer"), ("validate", "validator")]
    parent_id = root_span_id
    for action, agent in steps:
        span_id = generate_span_id()
        spans.append(create_base_span(
            trace_id, span_id, parent_id, f"{agent}.{action}",
            agent, current_time, random.randint(300, 600),
            {
                "gen_ai.action": action,
                "gen_ai.status": "success",
            }
        ))
        current_time += timedelta(milliseconds=650)
        parent_id = span_id

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "data-pipeline"}},
                    {"key": "mao.framework", "value": {"stringValue": "n8n"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F5_flawed_workflow",
            "variant": "negative",
            "expected_detection": False,
        }
    }


def generate_f7_context_negative() -> Dict[str, Any]:
    """Generate F7 negative: agent correctly uses all provided context."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 3000,
        {"workflow.name": "customer_support"}
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "assistant.provide_context",
        "assistant", current_time, 300,
        {
            "gen_ai.action": "provide_context",
            "gen_ai.response.sample": "Customer is vegetarian, prefers gluten-free options, and has a budget of $30",
        }
    ))
    current_time += timedelta(milliseconds=350)

    span2 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span2, span1, "recommender.suggest",
        "recommender", current_time, 500,
        {
            "gen_ai.action": "recommend",
            "gen_ai.response.sample": "Based on your preferences: 1) Vegetable stir-fry (GF, $12) 2) Quinoa salad (GF, $15) 3) Mushroom risotto (GF, $18). All vegetarian and gluten-free, total under $30.",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "support-agent"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F7_context_neglect",
            "variant": "negative",
            "expected_detection": False,
        }
    }


def generate_f11_coordination_negative() -> Dict[str, Any]:
    """Generate F11 negative: agents properly hand off work without deadlock."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    spans.append(create_base_span(
        trace_id, root_span_id, None, "orchestration.run",
        "orchestrator", current_time, 5000,
        {"workflow.name": "team_pipeline"}
    ))
    current_time += timedelta(milliseconds=100)

    agents = [("agent_a", "research"), ("agent_b", "analyze"), ("agent_c", "summarize")]
    parent_id = root_span_id
    for agent, action in agents:
        span_id = generate_span_id()
        spans.append(create_base_span(
            trace_id, span_id, parent_id, f"{agent}.{action}",
            agent, current_time, random.randint(500, 1000),
            {
                "gen_ai.coordination.status": "completed",
                "gen_ai.action": action,
                "gen_ai.status": "success",
            }
        ))
        current_time += timedelta(milliseconds=1100)
        parent_id = span_id

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "team-pipeline"}},
                    {"key": "mao.framework", "value": {"stringValue": "langgraph"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "coordination_deadlock",
            "variant": "negative",
            "expected_detection": False,
        }
    }


def generate_f14_completion_negative() -> Dict[str, Any]:
    """Generate F14 negative: agent completes ALL required sections."""
    trace_id = generate_trace_id()
    root_span_id = generate_span_id()
    start_time = datetime.utcnow() - timedelta(minutes=random.randint(5, 60))

    spans = []
    current_time = start_time

    task = "Generate quarterly report with: 1) Executive summary, 2) Financial analysis, 3) Market trends, 4) Recommendations"

    spans.append(create_base_span(
        trace_id, root_span_id, None, "workflow.run",
        "coordinator", current_time, 4000,
        {
            "workflow.name": "report_generator",
            "gen_ai.task": task,
        }
    ))
    current_time += timedelta(milliseconds=100)

    span1 = generate_span_id()
    spans.append(create_base_span(
        trace_id, span1, root_span_id, "generator.generate",
        "generator", current_time, 1500,
        {
            "gen_ai.action": "generate",
            "gen_ai.response.sample": "Quarterly Report Q1 2025\n\n1. Executive Summary: Revenue up 15%...\n2. Financial Analysis: Operating margin improved to 22%...\n3. Market Trends: Digital adoption accelerated...\n4. Recommendations: Expand into APAC market...\n\nReport complete.",
        }
    ))

    return {
        "resourceSpans": [{
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "report-gen"}},
                    {"key": "mao.framework", "value": {"stringValue": "crewai"}},
                ]
            },
            "scopeSpans": [{
                "scope": {"name": "mao-testing-sdk", "version": "1.0.0"},
                "spans": spans,
            }]
        }],
        "_golden_metadata": {
            "detection_type": "F14_completion_misjudgment",
            "variant": "negative",
            "expected_detection": False,
        }
    }


def generate_golden_dataset(
    count: int = 50,
    seed: int = None,
    include_mast: bool = False,
) -> List[Dict[str, Any]]:
    """Generate a balanced dataset of golden traces.

    Args:
        count: Number of traces to generate
        seed: Random seed for reproducibility
        include_mast: Include all MAST F1-F14 failure modes (generates ~700 traces)
    """
    if seed:
        random.seed(seed)

    traces = []

    if include_mast:
        # Generate comprehensive MAST dataset with variant cycling.
        # Multi-variant generators produce ~50 samples spread across variants.
        # Single-variant generators produce 50 samples with default variant.
        import math

        mast_multi_variant = [
            # (generator_fn, [list of variants])
            (generate_f1_spec_mismatch_trace, ["default", "partial_compliance", "format_mismatch", "wrong_language"]),
            (generate_f3_resource_misallocation_trace, ["default", "rate_limit_hit", "memory_spike", "concurrent_exhaustion"]),
            (generate_f4_inadequate_tool_trace, ["default", "hallucinated_api", "workaround_simulation", "missing_db_tool"]),
            (generate_f5_flawed_workflow_trace, ["default", "orphan_node", "excessive_depth", "convergence_bottleneck"]),
            (generate_f7_context_neglect_trace, ["default", "context_override", "selective_ignore", "stale_context"]),
            (generate_f12_validation_failure_trace, ["default", "schema_violation", "truncated_output", "encoding_error"]),
            (generate_f13_quality_gate_bypass_trace, ["default", "implicit_bypass", "deferred_review", "risk_acceptance"]),
            (generate_f14_completion_misjudgment_trace, ["default", "premature_success", "partial_completion", "abandoned_subtask"]),
        ]

        mast_single_variant = [
            generate_f2_poor_decomposition_trace,
            generate_f6_derailment_trace,
            generate_f8_withholding_trace,
            generate_f9_usurpation_trace,
            generate_f10_communication_breakdown_trace,
            generate_deadlock_trace,
            generate_infinite_loop_trace,
            generate_state_corruption_trace,
            generate_persona_drift_trace,
        ]

        samples_per_type = 50

        # Multi-variant: distribute 50 samples across variants
        for generator, variants in mast_multi_variant:
            per_variant = math.ceil(samples_per_type / len(variants))
            for variant in variants:
                for _ in range(per_variant):
                    traces.append(generator(variant=variant))

        # Single-variant: 50 samples with default
        for generator in mast_single_variant:
            for _ in range(samples_per_type):
                traces.append(generator())

        # Add detector-specific negative examples (10 per detector)
        negative_generators = [
            generate_f1_spec_mismatch_negative,
            generate_f3_resource_negative,
            generate_f4_tool_negative,
            generate_f5_workflow_negative,
            generate_f7_context_negative,
            generate_f11_coordination_negative,
            generate_f12_validation_negative,
            generate_f13_quality_gate_negative,
            generate_f14_completion_negative,
        ]

        samples_per_negative = 10
        for neg_gen in negative_generators:
            for _ in range(samples_per_negative):
                traces.append(neg_gen())

        # Add borderline negative examples (challenging cases near thresholds)
        borderline_generators = [
            generate_f2_decomposition_borderline,
            generate_f3_resource_borderline,
            generate_f7_context_borderline,
            generate_f8_withholding_borderline,
            generate_f9_usurpation_borderline,
            generate_f10_communication_borderline,
            generate_f13_quality_gate_borderline,
            generate_f14_completion_borderline,
        ]

        samples_per_borderline = 10
        for border_gen in borderline_generators:
            for _ in range(samples_per_borderline):
                traces.append(border_gen())

        # Add healthy traces (baseline negatives)
        num_healthy = len(traces) // 10
        for _ in range(num_healthy):
            traces.append(generate_healthy_trace())

        random.shuffle(traces)
        num_types = len(mast_multi_variant) + len(mast_single_variant)
        print(f"Generated {len(traces)} MAST traces ({num_types} failure types + {len(negative_generators)} negative + {len(borderline_generators)} borderline)")
        return traces

    else:
        # Original balanced dataset (4 legacy types + healthy)
        loop_variants = ["structural", "hash", "semantic"]
        corruption_variants = ["type_mismatch", "hallucinated_key", "cross_field"]
        persona_variants = ["gradual", "sudden"]
        deadlock_variants = ["circular_wait", "resource_contention"]

        per_type = count // 5

        for variant in loop_variants:
            for _ in range(per_type // len(loop_variants) + 1):
                traces.append(generate_infinite_loop_trace(variant))

        for variant in corruption_variants:
            for _ in range(per_type // len(corruption_variants) + 1):
                traces.append(generate_state_corruption_trace(variant))

        for variant in persona_variants:
            for _ in range(per_type // len(persona_variants) + 1):
                traces.append(generate_persona_drift_trace(variant))

        for variant in deadlock_variants:
            for _ in range(per_type // len(deadlock_variants) + 1):
                traces.append(generate_deadlock_trace(variant))

        for _ in range(per_type):
            traces.append(generate_healthy_trace())

        random.shuffle(traces)
        return traces[:count]


def main():
    parser = argparse.ArgumentParser(description="Generate golden trace data")
    parser.add_argument("--output", "-o", default="fixtures/golden", help="Output directory")
    parser.add_argument("--count", "-n", type=int, default=50, help="Number of traces (ignored if --all-mast)")
    parser.add_argument("--seed", "-s", type=int, help="Random seed for reproducibility")
    parser.add_argument("--format", "-f", choices=["jsonl", "json"], default="jsonl")
    parser.add_argument("--all-mast", action="store_true", help="Generate comprehensive MAST F1-F14 dataset (~850 traces)")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.all_mast:
        print("Generating comprehensive MAST dataset (all F1-F14 failure modes)...")
        traces = generate_golden_dataset(0, args.seed, include_mast=True)
    else:
        print(f"Generating {args.count} golden traces...")
        traces = generate_golden_dataset(args.count, args.seed)
    
    by_type = {}
    for trace in traces:
        dtype = trace["_golden_metadata"]["detection_type"] or "healthy"
        by_type.setdefault(dtype, []).append(trace)
    
    print("\nDataset breakdown:")
    for dtype, items in sorted(by_type.items()):
        print(f"  {dtype}: {len(items)} traces")
    
    if args.format == "jsonl":
        output_file = output_dir / "golden_traces.jsonl"
        with open(output_file, "w") as f:
            for trace in traces:
                f.write(json.dumps(trace) + "\n")
    else:
        output_file = output_dir / "golden_traces.json"
        with open(output_file, "w") as f:
            json.dump(traces, f, indent=2)
    
    print(f"\nWrote {len(traces)} traces to {output_file}")
    
    manifest = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_traces": len(traces),
        "by_detection_type": {k: len(v) for k, v in by_type.items()},
        "seed": args.seed,
    }
    manifest_file = output_dir / "manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote manifest to {manifest_file}")


if __name__ == "__main__":
    main()
