#!/usr/bin/env python3
"""
Export n8n execution data from database to OTEL trace format.

This script converts n8n execution data stored in the PostgreSQL database
into OTEL trace format compatible with the golden trace test harness.

Usage:
    # Export recent traces
    python scripts/export_n8n_to_otel.py --limit 100 --output data/n8n_otel_traces.jsonl

    # Export specific trace
    python scripts/export_n8n_to_otel.py --trace-id abc-123 --output data/trace.jsonl

    # Export with detection type labels (from detections table)
    python scripts/export_n8n_to_otel.py --with-labels --output data/n8n_labeled_traces.jsonl

    # Dry run - just show what would be exported
    python scripts/export_n8n_to_otel.py --dry-run --limit 10
"""

import sys
import json
import asyncio
import argparse
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def export_traces(
    limit: int = 100,
    trace_id: Optional[str] = None,
    with_labels: bool = False,
    output_path: Optional[Path] = None,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """Export n8n traces from database to OTEL format."""

    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    from app.storage.database import async_session_maker
    from app.storage.models import Trace, State, Detection

    otel_traces = []

    async with async_session_maker() as db:
        # Build query
        if trace_id:
            query = select(Trace).where(Trace.id == trace_id)
        else:
            # Get recent traces that have states
            query = (
                select(Trace)
                .options(selectinload(Trace.states))
                .order_by(Trace.created_at.desc())
                .limit(limit)
            )

        result = await db.execute(query)
        traces = result.scalars().all()

        print(f"Found {len(traces)} traces to export")

        if dry_run:
            for trace in traces:
                print(f"\nTrace: {trace.id}")
                print(f"  Session: {trace.session_id}")
                print(f"  Status: {trace.status}")
                print(f"  Tokens: {trace.total_tokens}")
                print(f"  Created: {trace.created_at}")

                # Get state count
                state_query = select(func.count(State.id)).where(State.trace_id == trace.id)
                state_result = await db.execute(state_query)
                state_count = state_result.scalar()
                print(f"  States: {state_count}")
            return []

        for trace in traces:
            # Get all states for this trace
            state_query = (
                select(State)
                .where(State.trace_id == trace.id)
                .order_by(State.sequence_num)
            )
            state_result = await db.execute(state_query)
            states = state_result.scalars().all()

            if not states:
                print(f"  Skipping trace {trace.id} - no states")
                continue

            # Get detections for labeling
            detection_type = None
            expected_detection = False

            if with_labels:
                det_query = select(Detection).where(Detection.trace_id == trace.id)
                det_result = await db.execute(det_query)
                detections = det_result.scalars().all()

                if detections:
                    # Use first detection as label
                    detection_type = detections[0].detection_type
                    expected_detection = True

            # Convert to OTEL format
            otel_trace = convert_to_otel(trace, states, detection_type, expected_detection)
            otel_traces.append(otel_trace)

            print(f"  Exported trace {trace.id} ({len(states)} states)")

    # Write output
    if output_path and otel_traces:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            for trace in otel_traces:
                f.write(json.dumps(trace) + '\n')
        print(f"\nExported {len(otel_traces)} traces to {output_path}")

    return otel_traces


def convert_to_otel(
    trace,
    states: List,
    detection_type: Optional[str] = None,
    expected_detection: bool = False,
) -> Dict[str, Any]:
    """Convert n8n trace and states to OTEL format.

    Args:
        trace: Trace database record
        states: List of State database records
        detection_type: Detection type label (for golden dataset)
        expected_detection: Whether detection should trigger

    Returns:
        OTEL-formatted trace dict
    """
    spans = []

    # Create root workflow span
    root_span_id = uuid.uuid4().hex[:16]
    trace_id = str(trace.id).replace('-', '')[:32]

    root_span = {
        "traceId": trace_id,
        "spanId": root_span_id,
        "name": "workflow.run",
        "kind": 1,
        "startTimeUnixNano": str(int(trace.created_at.timestamp() * 1_000_000_000)),
        "endTimeUnixNano": str(int((trace.completed_at or trace.created_at).timestamp() * 1_000_000_000)),
        "attributes": [
            {"key": "gen_ai.system", "value": {"stringValue": "n8n"}},
            {"key": "workflow.name", "value": {"stringValue": trace.session_id or "n8n-workflow"}},
            {"key": "workflow.status", "value": {"stringValue": trace.status or "unknown"}},
        ],
        "status": {"code": 1 if trace.status == "completed" else 2},
    }
    spans.append(root_span)

    # Convert each state to a span
    for state in states:
        span = convert_state_to_span(state, trace_id, root_span_id)
        spans.append(span)

    # Build OTEL trace structure
    otel_trace = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "n8n-workflow"}},
                        {"key": "mao.framework", "value": {"stringValue": "n8n"}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {
                            "name": "mao-n8n-exporter",
                            "version": "1.0.0"
                        },
                        "spans": spans
                    }
                ]
            }
        ],
        # Golden metadata for testing
        "_golden_metadata": {
            "detection_type": detection_type,
            "expected_detection": expected_detection,
            "source": "n8n_database",
            "trace_id": str(trace.id),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
    }

    return otel_trace


def convert_state_to_span(state, trace_id: str, parent_span_id: str) -> Dict[str, Any]:
    """Convert a State record to an OTEL span.

    Args:
        state: State database record
        trace_id: Trace ID string
        parent_span_id: Parent span ID

    Returns:
        OTEL span dict
    """
    span_id = uuid.uuid4().hex[:16]
    state_delta = state.state_delta or {}

    # Build attributes
    attributes = [
        {"key": "gen_ai.system", "value": {"stringValue": "n8n"}},
        {"key": "gen_ai.agent.id", "value": {"stringValue": state.agent_id}},
        {"key": "gen_ai.agent.name", "value": {"stringValue": state.agent_id}},
        {"key": "gen_ai.step.sequence", "value": {"intValue": str(state.sequence_num)}},
    ]

    # Add state hash
    if state.state_hash:
        attributes.append({
            "key": "gen_ai.state.hash",
            "value": {"stringValue": state.state_hash}
        })

    # Add token counts
    if state.token_count:
        # Split roughly 60/40 input/output (n8n doesn't separate)
        input_tokens = int(state.token_count * 0.6)
        output_tokens = state.token_count - input_tokens
        attributes.extend([
            {"key": "gen_ai.tokens.input", "value": {"intValue": str(input_tokens)}},
            {"key": "gen_ai.tokens.output", "value": {"intValue": str(output_tokens)}},
        ])

    # Add LLM output if present
    output = state_delta.get("output")
    if output:
        # Extract text from n8n output structure
        output_text = extract_output_text(output)
        if output_text:
            attributes.append({
                "key": "gen_ai.response.sample",
                "value": {"stringValue": output_text[:500]}  # Truncate for safety
            })

    # Add state delta
    if state_delta:
        # Create simplified delta for state comparison
        simplified_delta = {
            k: v for k, v in state_delta.items()
            if k not in ['output', 'parameters'] and v is not None
        }
        if simplified_delta:
            attributes.append({
                "key": "gen_ai.state.delta",
                "value": {"stringValue": json.dumps(simplified_delta)}
            })

    # Add model config if present
    model_config = state_delta.get("model_config", {})
    if model_config:
        if "temperature" in model_config:
            attributes.append({
                "key": "gen_ai.temperature",
                "value": {"doubleValue": model_config["temperature"]}
            })

    # Add reasoning if present (Claude extended thinking)
    reasoning = state_delta.get("reasoning")
    if reasoning:
        attributes.append({
            "key": "gen_ai.reasoning",
            "value": {"stringValue": reasoning[:1000]}  # Truncate
        })

    # Add action based on node type
    node_type = state_delta.get("node_type", "")
    action = infer_action(node_type, state.agent_id)
    attributes.append({
        "key": "gen_ai.action",
        "value": {"stringValue": action}
    })

    # Calculate timing
    start_ns = int(state.created_at.timestamp() * 1_000_000_000)
    end_ns = start_ns + (state.latency_ms * 1_000_000) if state.latency_ms else start_ns + 1_000_000

    return {
        "traceId": trace_id,
        "spanId": span_id,
        "parentSpanId": parent_span_id,
        "name": f"{state.agent_id}.execute",
        "kind": 1,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": attributes,
        "status": {"code": 1},
    }


def extract_output_text(output: Any) -> Optional[str]:
    """Extract text from n8n output structure.

    n8n outputs can be nested in various ways:
    - Direct string
    - List of dicts with 'json' key
    - Nested under 'text', 'content', 'message', etc.
    """
    if isinstance(output, str):
        return output

    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, dict):
            # Check common keys
            for key in ['text', 'content', 'message', 'response', 'output']:
                if key in first:
                    return str(first[key])

            # Check nested json
            if 'json' in first:
                json_data = first['json']
                if isinstance(json_data, str):
                    return json_data
                if isinstance(json_data, dict):
                    for key in ['text', 'content', 'message', 'response', 'output']:
                        if key in json_data:
                            return str(json_data[key])

    if isinstance(output, dict):
        for key in ['text', 'content', 'message', 'response', 'output']:
            if key in output:
                return str(output[key])

    return None


def infer_action(node_type: str, agent_id: str) -> str:
    """Infer action from node type and agent name."""
    node_type_lower = node_type.lower()
    agent_lower = agent_id.lower()

    if 'openai' in node_type_lower or 'anthropic' in node_type_lower:
        return "generate"
    if 'langchain' in node_type_lower:
        if 'agent' in node_type_lower:
            return "agent_execute"
        return "chain"
    if 'http' in node_type_lower:
        return "http_request"
    if 'set' in node_type_lower:
        return "set_data"
    if 'code' in node_type_lower:
        return "execute_code"
    if 'trigger' in node_type_lower:
        return "trigger"

    # Infer from agent name
    if 'research' in agent_lower:
        return "research"
    if 'analyst' in agent_lower or 'analysis' in agent_lower:
        return "analyze"
    if 'write' in agent_lower:
        return "write"

    return "execute"


def main():
    parser = argparse.ArgumentParser(
        description="Export n8n execution data to OTEL format"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of traces to export",
    )
    parser.add_argument(
        "--trace-id",
        type=str,
        help="Export specific trace by ID",
    )
    parser.add_argument(
        "--with-labels",
        action="store_true",
        help="Include detection labels from detections table",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/n8n_otel_traces.jsonl",
        help="Output file path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Just show what would be exported",
    )

    args = parser.parse_args()

    # Run async export
    output_path = Path(args.output) if not args.dry_run else None

    traces = asyncio.run(export_traces(
        limit=args.limit,
        trace_id=args.trace_id,
        with_labels=args.with_labels,
        output_path=output_path,
        dry_run=args.dry_run,
    ))

    if args.dry_run:
        print(f"\nDry run complete. Would export up to {args.limit} traces.")
    else:
        print(f"\nExport complete. {len(traces)} traces exported.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
