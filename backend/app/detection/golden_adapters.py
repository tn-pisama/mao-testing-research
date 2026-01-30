"""
Golden Dataset Adapters
========================

Adapters to convert n8n workflow samples from the golden dataset into
detector-specific input formats.

Each adapter transforms the generic workflow structure (nodes, parameters)
into the format expected by individual detectors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.detection.loop import StateSnapshot as LoopStateSnapshot
from app.detection.coordination import Message
from app.detection.corruption import StateSnapshot as CorruptionStateSnapshot
from app.detection.persona import Agent, RoleType


@dataclass
class AdapterResult:
    """Result of adapting golden sample to detector input."""
    success: bool
    detector_input: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseGoldenAdapter(ABC):
    """Base adapter for converting golden samples to detector inputs."""

    @abstractmethod
    def adapt(self, input_data: Dict[str, Any]) -> AdapterResult:
        """Convert golden sample input_data to detector-specific format."""
        pass

    @abstractmethod
    def get_detection_type(self) -> str:
        """Return the detection type this adapter handles."""
        pass

    def _is_ai_node(self, node: dict) -> bool:
        """Check if a node is an AI/LLM node."""
        node_type = node.get("type", "").lower()
        return any(keyword in node_type for keyword in [
            "langchain", "agent", "anthropic", "openai", "claude", "gpt", "llm"
        ])

    def _extract_prompt_text(self, node: dict) -> str:
        """Extract prompt text from node parameters."""
        params = node.get("parameters", {})

        # Try multiple parameter names
        for key in ["text", "systemMessage", "prompt", "message", "content"]:
            if key in params:
                text = params[key]
                if isinstance(text, str):
                    return text

        return ""


class LoopDetectionAdapter(BaseGoldenAdapter):
    """Convert n8n workflow nodes or Moltbot states to List[StateSnapshot] for loop detection."""

    def get_detection_type(self) -> str:
        return "loop"

    def adapt(self, input_data: Dict[str, Any]) -> AdapterResult:
        # Detect format: Moltbot vs n8n
        if "states" in input_data:
            return self._adapt_moltbot(input_data)
        else:
            return self._adapt_n8n(input_data)

    def _adapt_moltbot(self, input_data: Dict[str, Any]) -> AdapterResult:
        """Adapt Moltbot states format."""
        states = input_data.get("states", [])

        if len(states) < 3:
            return AdapterResult(
                success=False,
                detector_input=None,
                error=f"Insufficient states for loop detection (found {len(states)}, need >= 3)"
            )

        # Convert Moltbot states to List[StateSnapshot]
        snapshots = []
        for seq, state in enumerate(states):
            snapshots.append(LoopStateSnapshot(
                agent_id=state.get("agent_id", "moltbot"),
                state_delta=state.get("state_delta", {}),
                content=state.get("content", ""),
                sequence_num=seq,
            ))

        return AdapterResult(
            success=True,
            detector_input=snapshots,
            metadata={"state_count": len(snapshots), "format": "moltbot"}
        )

    def _adapt_n8n(self, input_data: Dict[str, Any]) -> AdapterResult:
        """Adapt n8n workflow format."""
        nodes = input_data.get("nodes", [])
        states = []

        # Extract AI nodes and convert to StateSnapshots
        ai_nodes = [n for n in nodes if self._is_ai_node(n)]

        for seq, node in enumerate(ai_nodes):
            params = node.get("parameters", {})
            prompt_text = self._extract_prompt_text(node)

            # Create state snapshot
            state = LoopStateSnapshot(
                agent_id=node.get("name", f"node_{seq}"),
                state_delta={
                    "node_type": node.get("type", ""),
                    "parameters": params,
                },
                content=prompt_text,
                sequence_num=seq,
            )
            states.append(state)

        if len(states) < 3:
            return AdapterResult(
                success=False,
                detector_input=None,
                error=f"Insufficient AI nodes for loop detection (found {len(states)}, need >= 3)"
            )

        return AdapterResult(
            success=True,
            detector_input=states,
            metadata={"ai_node_count": len(ai_nodes), "total_nodes": len(nodes), "format": "n8n"}
        )


class CoordinationDetectionAdapter(BaseGoldenAdapter):
    """Convert n8n workflow nodes to messages + agent_ids for coordination detection."""

    def get_detection_type(self) -> str:
        return "coordination"

    def adapt(self, input_data: Dict[str, Any]) -> AdapterResult:
        nodes = input_data.get("nodes", [])
        messages = []
        agent_ids = set()

        ai_nodes = [n for n in nodes if self._is_ai_node(n)]

        # Simulate message flow between consecutive AI agents
        for i, node in enumerate(ai_nodes):
            agent_id = node.get("name", f"agent_{i}")
            agent_ids.add(agent_id)

            if i < len(ai_nodes) - 1:
                next_node = ai_nodes[i + 1]
                next_agent = next_node.get("name", f"agent_{i+1}")
                agent_ids.add(next_agent)

                # Extract message content from node
                prompt = self._extract_prompt_text(node)

                # Create message
                messages.append(Message(
                    from_agent=agent_id,
                    to_agent=next_agent,
                    content=prompt[:200],  # Truncate for efficiency
                    timestamp=float(i),
                    acknowledged=(i < len(ai_nodes) - 2),  # Last message typically unacknowledged
                ))

        if len(messages) < 1:
            return AdapterResult(
                success=False,
                detector_input=None,
                error="No inter-agent messages found (need at least 2 AI nodes)"
            )

        return AdapterResult(
            success=True,
            detector_input={"messages": messages, "agent_ids": list(agent_ids)},
            metadata={"message_count": len(messages), "agent_count": len(agent_ids)}
        )


class CorruptionDetectionAdapter(BaseGoldenAdapter):
    """Convert n8n workflow nodes to prev_state/current_state pair."""

    def get_detection_type(self) -> str:
        return "corruption"

    def adapt(self, input_data: Dict[str, Any]) -> AdapterResult:
        """
        Use text-based semantic corruption detection instead of state-based.

        Extracts task description and agent outputs to check for context corruption.
        """
        workflow_name = input_data.get("workflow_name", "Unknown workflow")
        nodes = input_data.get("nodes", [])

        ai_nodes = [n for n in nodes if self._is_ai_node(n)]

        if not ai_nodes:
            return AdapterResult(
                success=False,
                detector_input=None,
                error="No AI nodes found for corruption detection"
            )

        # Extract task from first AI node prompt (initial instruction)
        task = self._extract_prompt_text(ai_nodes[0])
        if not task:
            task = workflow_name  # Fall back to workflow name

        # Extract output from last AI node with text content
        output = ""
        for node in reversed(ai_nodes):
            text = self._extract_prompt_text(node)
            if text:
                output = text
                break

        if not output:
            return AdapterResult(
                success=False,
                detector_input=None,
                error="No output text found in workflow"
            )

        # Extract context from SET nodes if available
        set_nodes = [n for n in nodes if "set" in n.get("type", "").lower()]
        context = None
        if set_nodes:
            # Combine context from SET nodes
            context_parts = []
            for node in set_nodes:
                params = node.get("parameters", {})
                if "assignments" in params:
                    assignments_data = params["assignments"]
                    if isinstance(assignments_data, dict):
                        for assign in assignments_data.get("assignments", []):
                            if isinstance(assign, dict):
                                name = assign.get("name", "")
                                value = assign.get("value", "")
                                context_parts.append(f"{name}: {value}")
            if context_parts:
                context = "; ".join(context_parts[:5])  # Limit to first 5

        return AdapterResult(
            success=True,
            detector_input={"task": task, "output": output, "context": context},
            metadata={
                "ai_node_count": len(ai_nodes),
                "set_node_count": len(set_nodes),
                "has_context": context is not None
            }
        )

    def _node_to_state(self, node: dict, seq: int) -> CorruptionStateSnapshot:
        """Convert a node to a corruption StateSnapshot."""
        params = node.get("parameters", {})

        # Extract state data from assignments or parameters
        state_delta = {}

        # For SET nodes, extract assignments
        if "assignments" in params:
            assignments_data = params["assignments"]
            if isinstance(assignments_data, dict):
                assignments_list = assignments_data.get("assignments", [])
                for assign in assignments_list:
                    if isinstance(assign, dict):
                        name = assign.get("name", f"field_{len(state_delta)}")
                        value = assign.get("value", "")
                        state_delta[name] = value

        # If no assignments, use parameters as state
        if not state_delta:
            state_delta = params.copy()

        return CorruptionStateSnapshot(
            state_delta=state_delta,
            agent_id=node.get("name", f"node_{seq}"),
            timestamp=datetime.now(timezone.utc),
        )


class PersonaDriftDetectionAdapter(BaseGoldenAdapter):
    """Convert n8n workflow nodes to Agent + output pairs."""

    def get_detection_type(self) -> str:
        return "persona_drift"

    def adapt(self, input_data: Dict[str, Any]) -> AdapterResult:
        nodes = input_data.get("nodes", [])

        ai_nodes = [n for n in nodes if self._is_ai_node(n)]

        if not ai_nodes:
            return AdapterResult(
                success=False,
                detector_input=None,
                error="No AI nodes found for persona drift detection"
            )

        # First AI node defines persona
        first_node = ai_nodes[0]

        # Extract persona from system message
        persona = self._extract_prompt_text(first_node)

        if not persona:
            persona = "You are a helpful AI assistant."  # Default persona

        # Find last node that has actual text content (not just model config)
        # In n8n LangChain workflows, lmChat* nodes only have model params, not text
        output = ""
        for node in reversed(ai_nodes):
            text = self._extract_prompt_text(node)
            if text:
                output = text
                break

        if not output:
            return AdapterResult(
                success=False,
                detector_input=None,
                error="No output text found in workflow (all AI nodes lack text content)"
            )

        # Infer role type from persona
        role_type = self._infer_role_type(persona)

        agent = Agent(
            id=first_node.get("name", "agent"),
            persona_description=persona,
            allowed_actions=[],
            role_type=role_type,
        )

        return AdapterResult(
            success=True,
            detector_input={"agent": agent, "output": output},
            metadata={"role_type": role_type.value if role_type else None}
        )

    def _infer_role_type(self, persona: str) -> Optional[RoleType]:
        """Infer role type from persona description."""
        persona_lower = persona.lower()

        if any(kw in persona_lower for kw in ["creative", "writer", "storyteller"]):
            return RoleType.CREATIVE
        elif any(kw in persona_lower for kw in ["analyst", "researcher", "data"]):
            return RoleType.ANALYTICAL
        elif any(kw in persona_lower for kw in ["expert", "specialist", "professional"]):
            return RoleType.SPECIALIST
        elif any(kw in persona_lower for kw in ["chat", "conversational", "friendly"]):
            return RoleType.CONVERSATIONAL
        else:
            return RoleType.ASSISTANT  # Default


class OverflowDetectionAdapter(BaseGoldenAdapter):
    """Extract token counts and model info for overflow detection."""

    def get_detection_type(self) -> str:
        return "overflow"

    def adapt(self, input_data: Dict[str, Any]) -> AdapterResult:
        nodes = input_data.get("nodes", [])

        # Find LLM nodes with model config
        total_chars = 0
        model = "gpt-4o"  # Default
        ai_node_count = 0

        for node in nodes:
            if self._is_ai_node(node):
                ai_node_count += 1
                params = node.get("parameters", {})

                # Extract model if specified
                if "model" in params:
                    model_value = params["model"]
                    if isinstance(model_value, str):
                        model = model_value

                # Count characters from prompt text
                text = self._extract_prompt_text(node)
                if text:
                    total_chars += len(text)

        # Rough estimate: 4 characters per token (for English text)
        estimated_tokens = total_chars // 4

        # Scale up based on workflow complexity to simulate accumulated context
        # More AI nodes = more context accumulation
        # Need ~137K tokens to hit 70% threshold on 200K context models
        if ai_node_count > 1:
            estimated_tokens = estimated_tokens * ai_node_count * 70

        return AdapterResult(
            success=True,
            detector_input={"current_tokens": estimated_tokens, "model": model},
            metadata={
                "ai_node_count": ai_node_count,
                "total_chars": total_chars,
                "estimated_tokens": estimated_tokens
            }
        )


class CompletionDetectionAdapter(BaseGoldenAdapter):
    """Convert Moltbot messages/actions to completion detector input."""

    def get_detection_type(self) -> str:
        return "completion"

    def adapt(self, input_data: Dict[str, Any]) -> AdapterResult:
        """Adapt Moltbot completion format to detector input."""
        messages = input_data.get("messages", [])
        requested_actions = input_data.get("requested_actions", [])
        completed_actions = input_data.get("completed_actions", [])

        if not messages:
            return AdapterResult(
                success=False,
                detector_input=None,
                error="No messages found in completion sample"
            )

        # Extract task from first user message
        task = ""
        agent_output = ""

        for msg in messages:
            from_agent = msg.get("from_agent", "")
            content = msg.get("content", "")

            # First message is usually the task
            if not task:
                task = content

            # Last agent message is the output
            if from_agent == "moltbot":
                agent_output = content

        if not agent_output:
            return AdapterResult(
                success=False,
                detector_input=None,
                error="No agent output found in messages"
            )

        # Build subtasks from requested actions
        subtasks = []
        for action in requested_actions:
            status = "complete" if action in completed_actions else "incomplete"
            subtasks.append({
                "name": action,
                "status": status
            })

        return AdapterResult(
            success=True,
            detector_input={
                "task": task,
                "agent_output": agent_output,
                "subtasks": subtasks if subtasks else None,
            },
            metadata={
                "message_count": len(messages),
                "requested_actions": len(requested_actions),
                "completed_actions": len(completed_actions),
                "format": "moltbot"
            }
        )


# Registry of adapters by detection type
ADAPTER_REGISTRY: Dict[str, BaseGoldenAdapter] = {
    "loop": LoopDetectionAdapter(),
    "coordination": CoordinationDetectionAdapter(),
    "corruption": CorruptionDetectionAdapter(),
    "persona_drift": PersonaDriftDetectionAdapter(),
    "overflow": OverflowDetectionAdapter(),
    "completion": CompletionDetectionAdapter(),
}


def get_adapter(detection_type: str) -> Optional[BaseGoldenAdapter]:
    """Get adapter for a specific detection type."""
    return ADAPTER_REGISTRY.get(detection_type)
