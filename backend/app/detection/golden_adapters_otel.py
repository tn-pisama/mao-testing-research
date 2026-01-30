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


# MAST F1-F14 Adapters

class F1SpecMismatchOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F1 Specification Mismatch detection."""

    def get_detection_type(self) -> str:
        return "F1_spec_mismatch"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        user_intent = None
        specification = None

        for span in spans:
            attrs = self._parse_attributes(span)
            if 'gen_ai.task.user_intent' in attrs:
                user_intent = attrs['gen_ai.task.user_intent']
            if 'gen_ai.task.specification' in attrs:
                specification = attrs['gen_ai.task.specification']

        if not user_intent or not specification:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="Missing user_intent or specification attributes"
            )

        return OTELAdapterResult(
            success=True,
            detector_input={
                "user_intent": user_intent,
                "task_specification": specification,
            }
        )


class F2DecompositionOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F2 Poor Task Decomposition detection."""

    def get_detection_type(self) -> str:
        return "F2_poor_decomposition"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        task = None
        subtasks = []

        for span in spans:
            attrs = self._parse_attributes(span)
            if 'gen_ai.task' in attrs:
                task = attrs['gen_ai.task']
            if 'gen_ai.subtasks' in attrs:
                try:
                    subtasks = json.loads(attrs['gen_ai.subtasks'])
                except (json.JSONDecodeError, TypeError):
                    subtasks = []

        if not task or not subtasks:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="Missing task or subtasks"
            )

        return OTELAdapterResult(
            success=True,
            detector_input={
                "task": task,
                "subtasks": subtasks,
            }
        )


class F3ResourceMisallocationOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F3 Resource Misallocation detection."""

    def get_detection_type(self) -> str:
        return "F3_resource_misallocation"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        # Build turn snapshots with token usage
        turns = []
        for seq, span in enumerate(spans):
            attrs = self._parse_attributes(span)

            agent_id = attrs.get('gen_ai.agent.id', 'unknown')
            content = attrs.get('gen_ai.response.sample', '')
            task = attrs.get('gen_ai.task', '')

            tokens_in = attrs.get('gen_ai.tokens.input', 0)
            tokens_out = attrs.get('gen_ai.tokens.output', 0)

            # Create turn-aware snapshot (simplified)
            turns.append({
                'agent_id': agent_id,
                'content': content,
                'task': task,
                'tokens_input': tokens_in,
                'tokens_output': tokens_out,
                'sequence': seq,
            })

        if len(turns) == 0:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="No turns with token data found"
            )

        return OTELAdapterResult(
            success=True,
            detector_input=turns  # Return list directly, not wrapped in dict
        )


class F4ToolProvisionOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F4 Inadequate Tool Provision detection."""

    def get_detection_type(self) -> str:
        return "F4_inadequate_tool"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        tool_failures = []
        for span in spans:
            attrs = self._parse_attributes(span)

            tool_name = attrs.get('gen_ai.tool.name')
            tool_available = attrs.get('gen_ai.tool.available', 'true')

            if tool_name and tool_available == 'false':
                tool_failures.append({
                    'tool_name': tool_name,
                    'agent_id': attrs.get('gen_ai.agent.id', 'unknown'),
                    'action': attrs.get('gen_ai.action', 'unknown'),
                })

        if len(tool_failures) == 0:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="No tool failures detected"
            )

        return OTELAdapterResult(
            success=True,
            detector_input={'tool_failures': tool_failures}
        )


class F5WorkflowDesignOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F5 Flawed Workflow Design detection."""

    def get_detection_type(self) -> str:
        return "F5_flawed_workflow"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        workflow_issues = {}
        nodes = []

        for span in spans:
            attrs = self._parse_attributes(span)

            if 'gen_ai.workflow.has_cycles' in attrs:
                workflow_issues['has_cycles'] = attrs['gen_ai.workflow.has_cycles'] == 'true'

            if 'gen_ai.workflow.error_handling' in attrs:
                workflow_issues['error_handling'] = attrs['gen_ai.workflow.error_handling']

            # Build node graph for cycle detection
            if 'gen_ai.next_step' in attrs:
                nodes.append({
                    'id': attrs.get('gen_ai.agent.id', 'unknown'),
                    'next': attrs['gen_ai.next_step'],
                })

        if not workflow_issues and not nodes:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="No workflow design information found"
            )

        return OTELAdapterResult(
            success=True,
            detector_input={
                'workflow_issues': workflow_issues,
                'nodes': nodes,
            }
        )


class F6DerailmentOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F6 Task Derailment detection."""

    def get_detection_type(self) -> str:
        return "F6_task_derailment"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        task = None
        output = None

        for span in spans:
            attrs = self._parse_attributes(span)

            if 'gen_ai.task' in attrs and not task:
                task = attrs['gen_ai.task']

            if 'gen_ai.response.sample' in attrs and attrs.get('gen_ai.action') in ['summarize', 'generate', 'analyze']:
                output = attrs['gen_ai.response.sample']

        if not task or not output:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="Missing task or output"
            )

        return OTELAdapterResult(
            success=True,
            detector_input={
                'task': task,
                'output': output,
            }
        )


class F7ContextNeglectOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F7 Context Neglect detection."""

    def get_detection_type(self) -> str:
        return "F7_context_neglect"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        conversation_history = []

        for span in spans:
            attrs = self._parse_attributes(span)
            content = attrs.get('gen_ai.response.sample', '')

            if content:
                conversation_history.append({
                    'agent_id': attrs.get('gen_ai.agent.id', 'unknown'),
                    'content': content,
                    'action': attrs.get('gen_ai.action', 'unknown'),
                })

        if len(conversation_history) < 2:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="Need at least 2 conversation turns"
            )

        # Last turn is current output, rest is context
        output = conversation_history[-1]['content']
        context = '\n'.join([turn['content'] for turn in conversation_history[:-1]])

        return OTELAdapterResult(
            success=True,
            detector_input={
                'context': context,
                'output': output,
            }
        )


class F8WithholdingOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F8 Information Withholding detection."""

    def get_detection_type(self) -> str:
        return "F8_information_withholding"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        internal_findings = None
        communicated_output = None

        for span in spans:
            attrs = self._parse_attributes(span)

            if 'gen_ai.internal_findings' in attrs:
                internal_findings = attrs['gen_ai.internal_findings']

            if 'gen_ai.response.sample' in attrs and attrs.get('gen_ai.action') == 'report':
                communicated_output = attrs['gen_ai.response.sample']

        if not internal_findings or not communicated_output:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="Missing internal findings or communicated output"
            )

        return OTELAdapterResult(
            success=True,
            detector_input={
                'internal_findings': internal_findings,
                'output': communicated_output,
            }
        )


class F9UsurpationOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F9 Role Usurpation detection."""

    def get_detection_type(self) -> str:
        return "F9_role_usurpation"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        # Build turn snapshots with roles
        turns = []
        for seq, span in enumerate(spans):
            attrs = self._parse_attributes(span)

            agent_id = attrs.get('gen_ai.agent.id', 'unknown')
            content = attrs.get('gen_ai.response.sample', '')
            role = attrs.get('gen_ai.role', agent_id)

            turns.append({
                'agent_id': agent_id,
                'content': content,
                'role_description': role,
                'sequence': seq,
            })

        if len(turns) == 0:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="No turns found"
            )

        return OTELAdapterResult(
            success=True,
            detector_input=turns  # Return list directly, not wrapped in dict
        )


class F10CommunicationOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F10 Communication Breakdown detection."""

    def get_detection_type(self) -> str:
        return "F10_communication_breakdown"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        messages = []
        agent_ids = set()

        for i, span in enumerate(spans):
            attrs = self._parse_attributes(span)

            agent_id = attrs.get('gen_ai.agent.id')
            if not agent_id:
                continue

            agent_ids.add(agent_id)

            # Look for message attributes
            message_to = attrs.get('gen_ai.message.to')
            content = attrs.get('gen_ai.response.sample', '')
            acknowledged = attrs.get('gen_ai.communication.acknowledged', 'true') == 'true'

            if content:
                messages.append(Message(
                    from_agent=agent_id,
                    to_agent=message_to or 'broadcast',
                    content=content,
                    timestamp=float(i),
                    acknowledged=acknowledged,
                ))

        if len(messages) < 2:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="Need at least 2 messages"
            )

        return OTELAdapterResult(
            success=True,
            detector_input={
                'messages': messages,
                'agent_ids': list(agent_ids),
            }
        )


class F12ValidationOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F12 Output Validation Failure detection."""

    def get_detection_type(self) -> str:
        return "F12_output_validation_failure"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        # Build turn snapshots with validation info
        turns = []
        for seq, span in enumerate(spans):
            attrs = self._parse_attributes(span)

            agent_id = attrs.get('gen_ai.agent.id', 'unknown')
            content = attrs.get('gen_ai.response.sample', '')
            schema = attrs.get('gen_ai.expected_schema')
            output = attrs.get('gen_ai.response.sample', '')

            if content or schema:
                turns.append({
                    'agent_id': agent_id,
                    'content': content,
                    'output': output,
                    'schema': schema,
                    'sequence': seq,
                })

        if len(turns) == 0:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="No validation data found"
            )

        return OTELAdapterResult(
            success=True,
            detector_input=turns  # Return list directly
        )


class F13QualityGateOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F13 Quality Gate Bypass detection."""

    def get_detection_type(self) -> str:
        return "F13_quality_gate_bypass"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        # Build turn snapshots with quality gate info
        turns = []
        for seq, span in enumerate(spans):
            attrs = self._parse_attributes(span)

            agent_id = attrs.get('gen_ai.agent.id', 'unknown')
            content = attrs.get('gen_ai.response.sample', '')
            gate_status = attrs.get('gen_ai.quality_gate.status')
            bypassed = attrs.get('gen_ai.quality_gate.bypassed') == 'true'

            if gate_status or bypassed:
                turns.append({
                    'agent_id': agent_id,
                    'content': content,
                    'check_passed': gate_status == 'passed' if gate_status else False,
                    'check_skipped': bypassed,
                    'sequence': seq,
                })

        if len(turns) == 0:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="No quality gate information found"
            )

        return OTELAdapterResult(
            success=True,
            detector_input=turns  # Return list directly
        )


class F14CompletionOTELAdapter(BaseOTELAdapter):
    """Convert OTEL traces for F14 Completion Misjudgment detection."""

    def get_detection_type(self) -> str:
        return "F14_completion_misjudgment"

    def adapt(self, trace: Dict[str, Any]) -> OTELAdapterResult:
        spans = self._extract_spans(trace)

        task = None
        output = None
        missing_requirements = None

        for span in spans:
            attrs = self._parse_attributes(span)

            if 'gen_ai.task' in attrs:
                task = attrs['gen_ai.task']

            if 'gen_ai.response.sample' in attrs:
                output = attrs['gen_ai.response.sample']

            if 'gen_ai.missing_requirements' in attrs:
                missing_requirements = attrs['gen_ai.missing_requirements']

        if not task or not output:
            return OTELAdapterResult(
                success=False,
                detector_input=None,
                error="Missing task or output"
            )

        # Parse missing_requirements if it's a JSON string
        requirements = []
        if missing_requirements:
            try:
                if isinstance(missing_requirements, str):
                    requirements = json.loads(missing_requirements)
                elif isinstance(missing_requirements, list):
                    requirements = missing_requirements
            except (json.JSONDecodeError, TypeError):
                requirements = [missing_requirements] if missing_requirements else []

        return OTELAdapterResult(
            success=True,
            detector_input={
                'task': task,
                'output': output,
                'requirements': requirements,
            }
        )


# Registry of OTEL adapters by detection type
OTEL_ADAPTER_REGISTRY: Dict[str, BaseOTELAdapter] = {
    # Legacy adapters
    "infinite_loop": InfiniteLoopOTELAdapter(),
    "state_corruption": StateCorruptionOTELAdapter(),
    "persona_drift": PersonaDriftOTELAdapter(),
    "coordination_deadlock": CoordinationDeadlockOTELAdapter(),
    # MAST F1-F14 adapters
    "F1_spec_mismatch": F1SpecMismatchOTELAdapter(),
    "F2_poor_decomposition": F2DecompositionOTELAdapter(),
    "F3_resource_misallocation": F3ResourceMisallocationOTELAdapter(),
    "F4_inadequate_tool": F4ToolProvisionOTELAdapter(),
    "F5_flawed_workflow": F5WorkflowDesignOTELAdapter(),
    "F6_task_derailment": F6DerailmentOTELAdapter(),
    "F7_context_neglect": F7ContextNeglectOTELAdapter(),
    "F8_information_withholding": F8WithholdingOTELAdapter(),
    "F9_role_usurpation": F9UsurpationOTELAdapter(),
    "F10_communication_breakdown": F10CommunicationOTELAdapter(),
    "F12_output_validation_failure": F12ValidationOTELAdapter(),
    "F13_quality_gate_bypass": F13QualityGateOTELAdapter(),
    "F14_completion_misjudgment": F14CompletionOTELAdapter(),
}


def get_otel_adapter(detection_type: str) -> Optional[BaseOTELAdapter]:
    """Get OTEL adapter for a specific detection type."""
    return OTEL_ADAPTER_REGISTRY.get(detection_type)
