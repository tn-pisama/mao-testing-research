"""
OTEL Golden Trace Adapters
===========================

Adapters to convert OTEL execution traces from golden_traces.jsonl into
detector-specific input formats.

Unlike n8n adapters (which work with static workflow definitions), these adapters
work with ACTUAL execution data including LLM outputs, state transitions, and
agent interactions.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.detection.loop import StateSnapshot as LoopStateSnapshot
from app.detection.coordination import Message
from app.detection.corruption import StateSnapshot as CorruptionStateSnapshot
from app.detection.persona import Agent, RoleType


@dataclass
class OTELAdapterResult:
    """Result of adapting OTEL trace to detector input."""
    success: bool
    detector_input: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseOTELAdapter(ABC):
    """Base adapter for converting OTEL traces to detector inputs."""

    @abstractmethod
    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        """Convert OTEL trace to detector-specific format."""
        pass

    @abstractmethod
    def get_detection_type(self) -> str:
        """Return the detection type this adapter handles."""
        pass

    def _extract_spans(self, trace: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all spans from OTEL trace."""
        spans = []
        for rs in trace.get('resourceSpans', []):
            for ss in rs.get('scopeSpans', []):
                spans.extend(ss.get('spans', []))
        return spans

    def _parse_attributes(self, span: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OTEL attributes into dict."""
        attrs = {}
        for attr in span.get('attributes', []):
            key = attr.get('key')
            value = attr.get('value', {})

            # Extract typed value
            if 'stringValue' in value:
                attrs[key] = value['stringValue']
            elif 'intValue' in value:
                attrs[key] = int(value['intValue'])
            elif 'doubleValue' in value:
                attrs[key] = value['doubleValue']
            elif 'boolValue' in value:
                attrs[key] = value['boolValue']

        return attrs


class InfiniteLoopOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces to List[StateSnapshot] for loop detection."""

    def get_detection_type(self) -> str:
        return "infinite_loop"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)
        states = []

        # Extract spans with state hashes
        for seq, span in enumerate(spans):
            attrs = self._parse_attributes(span)

            # Only process spans with state information
            if 'gen_ai.state.hash' not in attrs:
                continue

            # Parse state delta if available
            state_delta = {}
            if 'gen_ai.state.delta' in attrs:
                try:
                    state_delta = json.loads(attrs['gen_ai.state.delta'])
                except (json.JSONDecodeError, TypeError):
                    state_delta = {'raw': str(attrs['gen_ai.state.delta'])}

            # Create state snapshot
            state = LoopStateSnapshot(
                agent_id=attrs.get('gen_ai.agent.id', f"agent_{seq}"),
                state_delta=state_delta,
                content=attrs.get('gen_ai.action', ''),
                sequence_num=attrs.get('gen_ai.step.sequence', seq),
            )
            states.append(state)

        if len(states) < 3:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error=f"Insufficient states for loop detection (found {len(states)}, need >= 3)"
            )

        return OTELAdapterResult(
            success=True,
            detector_input=states,
            metadata={"state_count": len(states), "total_spans": len(spans)}
        )


class StateCorruptionOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces to text-based corruption detection format."""

    def get_detection_type(self) -> str:
        return "state_corruption"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        # Find spans with state deltas
        state_spans = []
        for span in spans:
            attrs = self._parse_attributes(span)
            if 'gen_ai.state.delta' in attrs:
                state_spans.append((span, attrs))

        if len(state_spans) < 2:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error=f"Need at least 2 state transitions (found {len(state_spans)})"
            )

        # Use first span as task context
        first_span, first_attrs = state_spans[0]
        task = first_span.get('name', 'Unknown task')

        # Extract state deltas
        try:
            prev_state = json.loads(first_attrs['gen_ai.state.delta'])
            curr_state = json.loads(state_spans[1][1]['gen_ai.state.delta'])
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error=f"Failed to parse state deltas: {e}"
            )

        # Format as text for semantic detection
        prev_text = ", ".join(f"{k}={v}" for k, v in prev_state.items())
        curr_text = ", ".join(f"{k}={v}" for k, v in curr_state.items())

        return OTELAdapterResult(
            success=True,
            detector_input={
                "task": task,
                "output": curr_text,
                "context": prev_text
            },
            metadata={
                "state_transitions": len(state_spans),
                "prev_state": prev_state,
                "curr_state": curr_state
            }
        )


class PersonaDriftOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces to Agent + output for persona drift detection."""

    def get_detection_type(self) -> str:
        return "persona_drift"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        # Find spans with response samples (actual LLM outputs)
        response_spans = []
        for span in spans:
            attrs = self._parse_attributes(span)
            if 'gen_ai.response.sample' in attrs:
                response_spans.append((span, attrs))

        if not response_spans:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="No response samples found in trace"
            )

        # First response defines the persona
        first_span, first_attrs = response_spans[0]
        first_response = first_attrs['gen_ai.response.sample']

        # Last response is what we check for drift
        last_span, last_attrs = response_spans[-1]
        last_response = last_attrs['gen_ai.response.sample']

        # Extract agent info
        agent_id = first_attrs.get('gen_ai.agent.id', 'agent')

        # Create agent with persona from first response
        agent = Agent(
            id=agent_id,
            persona_description=first_response[:200],  # Use first response as persona baseline
            allowed_actions=[],
            role_type=RoleType.ASSISTANT,
        )

        return OTELAdapterResult(
            success=True,
            detector_input={"agent": agent, "output": last_response},
            metadata={
                "response_count": len(response_spans),
                "first_turn": first_attrs.get('gen_ai.turn.number', 0),
                "last_turn": last_attrs.get('gen_ai.turn.number', 0)
            }
        )


class CoordinationDeadlockOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces to messages + agent_ids for coordination detection."""

    def get_detection_type(self) -> str:
        return "coordination_deadlock"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        # Find coordination-related spans
        coord_spans = []
        for span in spans:
            attrs = self._parse_attributes(span)
            if 'gen_ai.coordination.resource' in attrs or 'gen_ai.coordination.action' in attrs:
                coord_spans.append((span, attrs))

        if len(coord_spans) < 2:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error=f"Need at least 2 coordination events (found {len(coord_spans)})"
            )

        # Extract messages and agents
        messages = []
        agent_ids = set()

        for i, (span, attrs) in enumerate(coord_spans):
            agent_id = attrs.get('gen_ai.agent.id', f"agent_{i}")
            agent_ids.add(agent_id)

            # Create message representing coordination attempt
            resource = attrs.get('gen_ai.coordination.resource', 'resource')
            action = attrs.get('gen_ai.coordination.action', 'access')
            status = attrs.get('gen_ai.coordination.status', 'pending')

            content = f"{action} {resource} ({status})"

            # Determine target agent (next in sequence or coordinator)
            if i < len(coord_spans) - 1:
                next_agent = coord_spans[i + 1][1].get('gen_ai.agent.id', f"agent_{i+1}")
            else:
                next_agent = "coordinator"

            agent_ids.add(next_agent)

            messages.append(Message(
                from_agent=agent_id,
                to_agent=next_agent,
                content=content,
                timestamp=float(i),
                acknowledged=(status == 'completed'),
            ))

        return OTELAdapterResult(
            success=True,
            detector_input={"messages": messages, "agent_ids": list(agent_ids)},
            metadata={
                "coordination_events": len(coord_spans),
                "agent_count": len(agent_ids)
            }
        )


# Registry of OTEL adapters by detection type
OTEL_ADAPTER_REGISTRY: Dict[str, BaseOTELAdapter] = {
    "infinite_loop": InfiniteLoopOTELAdapter(),
    "state_corruption": StateCorruptionOTELAdapter(),
    "persona_drift": PersonaDriftOTELAdapter(),
    "coordination_deadlock": CoordinationDeadlockOTELAdapter(),
}


def get_otel_adapter(detection_type: str) -> Optional[BaseOTELAdapter]:
    """Get OTEL adapter for a specific detection type."""
    return OTEL_ADAPTER_REGISTRY.get(detection_type)
