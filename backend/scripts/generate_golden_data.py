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


def generate_golden_dataset(
    count: int = 50,
    seed: int = None,
) -> List[Dict[str, Any]]:
    """Generate a balanced dataset of golden traces."""
    if seed:
        random.seed(seed)
    
    traces = []
    
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
    parser.add_argument("--count", "-n", type=int, default=50, help="Number of traces")
    parser.add_argument("--seed", "-s", type=int, help="Random seed for reproducibility")
    parser.add_argument("--format", "-f", choices=["jsonl", "json"], default="jsonl")
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
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
