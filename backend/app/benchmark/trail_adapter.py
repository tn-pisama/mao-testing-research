"""TRAIL Span Adapter for Pisama detectors.

Converts TRAIL OTEL spans into the input format expected by Pisama
detection algorithms. Each detector expects specific fields (see
Golden Dataset Key Reference in MEMORY.md).
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from app.benchmark.trail_loader import TRAILSpan, TRAILTrace

logger = logging.getLogger(__name__)


class TRAILSpanAdapter:
    """Converts TRAIL OTEL spans to Pisama detector input format.

    TRAIL provides raw OTEL spans with ``input.value``, ``output.value``,
    ``tool.name``, etc. Pisama detectors expect structured dicts with
    keys like ``output``, ``sources``, ``context``, ``states``.

    The adapter:
    1. Finds the annotated span in the trace
    2. Gathers context (parent span, sibling spans, child spans)
    3. Extracts the relevant text fields
    4. Constructs the detector-specific input dict
    """

    def __init__(self):
        self._extractors: Dict[str, Callable[..., Dict[str, Any]]] = {
            "hallucination": self._extract_hallucination,
            "retrieval_quality": self._extract_retrieval_quality,
            "grounding": self._extract_grounding,
            "specification": self._extract_specification,
            "context": self._extract_context,
            "loop": self._extract_loop,
            "derailment": self._extract_derailment,
            "coordination": self._extract_coordination,
            "completion": self._extract_completion,
            "workflow": self._extract_workflow,
            "overflow": self._extract_overflow,
        }

    def extract_for_detector(
        self,
        detector_type: str,
        annotated_span: TRAILSpan,
        trace: TRAILTrace,
    ) -> Optional[Dict[str, Any]]:
        """Extract detector-specific input from a TRAIL span and its context.

        Args:
            detector_type: Pisama detector name (e.g. "hallucination").
            annotated_span: The span where the failure was annotated.
            trace: The full trace for context.

        Returns:
            Dict with detector-specific keys, or None if extraction fails.
        """
        extractor = self._extractors.get(detector_type)
        if extractor is None:
            logger.debug("No extractor for detector type: %s", detector_type)
            return None

        try:
            return extractor(annotated_span, trace)
        except Exception as exc:
            logger.warning(
                "Extraction failed for %s on span %s: %s",
                detector_type,
                annotated_span.span_id,
                exc,
            )
            return None

    @property
    def supported_detectors(self) -> List[str]:
        return list(self._extractors.keys())

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _get_attr(self, span: TRAILSpan, *keys: str) -> str:
        """Get first matching attribute value from a span."""
        for key in keys:
            val = span.attributes.get(key)
            if val is not None:
                return str(val)
        return ""

    def _get_output(self, span: TRAILSpan) -> str:
        """Extract output text from a span.

        Prefers llm.output_messages (clean text) over output.value (JSON).
        """
        # Try clean LLM output first
        llm_out = self._get_attr(span, "llm.output_messages.0.message.content")
        if llm_out:
            return llm_out
        # Fall back to output.value which may be JSON-encoded
        raw = self._get_attr(
            span, "output.value", "gen_ai.output", "gen_ai.completion",
        )
        if raw:
            return self._try_extract_content(raw)
        return ""

    def _get_input(self, span: TRAILSpan) -> str:
        """Extract input text from a span.

        Prefers the user message from llm.input_messages over raw input.value.
        """
        # Try to find the user message in LLM input messages
        for i in range(20):  # check up to 20 messages
            role = span.attributes.get(f"llm.input_messages.{i}.message.role", "")
            content = span.attributes.get(f"llm.input_messages.{i}.message.content", "")
            if role == "user" and content:
                return str(content)
        # Fall back to input.value
        raw = self._get_attr(
            span, "input.value", "gen_ai.input", "gen_ai.prompt",
        )
        if raw:
            return self._try_extract_content(raw)
        return ""

    def _get_system_prompt(self, span: TRAILSpan) -> str:
        """Extract the system prompt from LLM input messages."""
        return str(span.attributes.get("llm.input_messages.0.message.content", ""))

    def _get_full_conversation(self, span: TRAILSpan) -> str:
        """Extract the full conversation history from LLM input messages."""
        parts = []
        for i in range(50):
            role = span.attributes.get(f"llm.input_messages.{i}.message.role", "")
            content = span.attributes.get(f"llm.input_messages.{i}.message.content", "")
            if not role and not content:
                break
            if content:
                parts.append(f"[{role}] {str(content)[:2000]}")
        return "\n\n".join(parts)

    def _try_extract_content(self, raw: str) -> str:
        """Try to extract 'content' from a JSON string, or return as-is."""
        import json as _json
        if raw.startswith("{") or raw.startswith("["):
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, dict):
                    return str(parsed.get("content", raw))
                if isinstance(parsed, list) and parsed:
                    return str(parsed[0].get("content", raw) if isinstance(parsed[0], dict) else raw)
            except (ValueError, _json.JSONDecodeError):
                pass
        return raw

    def _collect_context_text(self, trace: TRAILTrace, exclude_span_id: str) -> str:
        """Collect contextual text from other spans in the trace.

        Limits output to avoid memory issues with large traces.
        """
        context_parts: List[str] = []
        max_chars = 8000
        total = 0

        for span in trace.flatten_spans():
            if span.span_id == exclude_span_id:
                continue
            output = self._get_output(span)
            if output and total + len(output) < max_chars:
                context_parts.append(output)
                total += len(output)
            if total >= max_chars:
                break

        return "\n---\n".join(context_parts)

    def _collect_source_documents(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> List[str]:
        """Collect source/reference documents from tool outputs and context."""
        sources: List[str] = []

        # Check tool output spans (children of the annotated span, or siblings)
        candidates = list(span.child_spans)
        parent = trace.get_parent_span(span)
        if parent:
            candidates.extend(
                s for s in parent.child_spans if s.span_id != span.span_id
            )

        for child in candidates:
            tool = child.tool_name
            output = self._get_output(child)
            if tool and output:
                sources.append(f"[{tool}] {output}")
            elif output:
                sources.append(output)

        # Also check input for context/document references
        input_text = self._get_input(span)
        if input_text and len(input_text) > 100:
            # Input often contains the context the LLM was given
            sources.append(input_text)

        return sources

    def _collect_child_outputs(self, span: TRAILSpan) -> List[str]:
        """Collect outputs from all child spans."""
        outputs: List[str] = []
        for child in span.child_spans:
            out = self._get_output(child)
            if out:
                tool = child.tool_name
                prefix = f"[{tool}] " if tool else ""
                outputs.append(f"{prefix}{out}")
            outputs.extend(self._collect_child_outputs(child))
        return outputs

    # ------------------------------------------------------------------
    # Per-detector extractors
    # ------------------------------------------------------------------

    def _extract_hallucination(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for hallucination detector.

        Expected keys: output, sources
        Uses the full conversation context as sources -- the LLM's input
        messages contain the factual grounding (tool results, documents).
        """
        output = self._get_output(span)
        sources = []

        # Extract tool responses and prior context from the conversation
        for i in range(50):
            role = span.attributes.get(f"llm.input_messages.{i}.message.role", "")
            content = span.attributes.get(f"llm.input_messages.{i}.message.content", "")
            if not role and not content:
                break
            # Tool responses and observations are the "ground truth"
            if role in ("tool-response", "tool", "tool-call", "function"):
                if content:
                    sources.append(str(content)[:4000])
            # Prior assistant outputs may contain retrieved facts
            elif role == "assistant" and content:
                sources.append(str(content)[:4000])

        # Also collect from child/sibling tool outputs
        if not sources:
            sources = self._collect_source_documents(span, trace)

        return {
            "output": output,
            "sources": sources,
        }

    def _extract_retrieval_quality(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for retrieval_quality detector.

        Expected keys: agent_output, query, retrieved_documents
        """
        agent_output = self._get_output(span)
        query = self._get_input(span)

        # Gather retrieved documents from child tool calls
        retrieved: List[str] = []
        for child in span.child_spans:
            out = self._get_output(child)
            if out:
                retrieved.append(out)

        # If no child docs, look for sibling tool results
        if not retrieved:
            siblings = trace.get_sibling_spans(span)
            for sib in siblings:
                if sib.tool_name:
                    out = self._get_output(sib)
                    if out:
                        retrieved.append(out)

        return {
            "agent_output": agent_output,
            "query": query,
            "retrieved_documents": retrieved,
        }

    def _extract_grounding(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for grounding detector.

        Expected keys: agent_output, source_documents
        """
        agent_output = self._get_output(span)
        source_docs = self._collect_source_documents(span, trace)

        return {
            "agent_output": agent_output,
            "source_documents": source_docs,
        }

    def _extract_specification(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for specification detector.

        Expected keys: task_specification, user_intent
        The user_intent is the original task. The task_specification is
        what the agent actually produced (its output).
        """
        # Find the original user task from root spans or conversation
        user_intent = ""
        # Try the agent's root span input first
        for root in trace.spans:
            for child in root.child_spans:
                inp = self._get_input(child)
                if inp and len(inp) > 20:
                    user_intent = inp
                    break
            if user_intent:
                break
        if not user_intent:
            user_intent = self._get_input(span)

        # The specification is what the LLM actually output
        task_spec = self._get_output(span)

        return {
            "task_specification": task_spec,
            "user_intent": user_intent,
        }

    def _extract_context(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for context detector.

        Expected keys: context, output
        Uses the full conversation history as context -- the LLM had access
        to all previous messages, tool results, and system instructions.
        """
        output = self._get_output(span)

        # The "context" is everything the LLM was given as input
        # Use the full conversation for richest context
        context = self._get_full_conversation(span)
        if not context:
            # Fallback: use input.value
            context = self._get_input(span)
        if not context:
            # Last resort: collect from other spans
            context = self._collect_context_text(trace, span.span_id)

        return {
            "context": context,
            "output": output,
        }

    def _extract_loop(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for loop detector.

        Expected keys: states
        """
        states: List[Dict[str, Any]] = []

        # Build states from all spans in the trace
        for i, flat_span in enumerate(trace.flatten_spans()):
            state: Dict[str, Any] = {
                "agent_id": self._get_attr(
                    flat_span, "gen_ai.agent.id", "agent.id", "agent_id"
                ) or f"agent_{i}",
                "content": self._get_output(flat_span) or self._get_input(flat_span),
                "state_delta": {},
            }

            # Extract state delta from attributes
            state_delta_raw = flat_span.attributes.get(
                "gen_ai.state.delta",
                flat_span.attributes.get("state_delta"),
            )
            if isinstance(state_delta_raw, str):
                try:
                    state["state_delta"] = json.loads(state_delta_raw)
                except json.JSONDecodeError:
                    state["state_delta"] = {"raw": state_delta_raw}
            elif isinstance(state_delta_raw, dict):
                state["state_delta"] = state_delta_raw

            states.append(state)

        return {"states": states}

    def _extract_derailment(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for derailment detector.

        Expected keys: output, task
        The task is the original user request. The output is what the LLM
        produced at this step (which may have deviated from the task).
        """
        output = self._get_output(span)

        # Find the original task: look for user messages in the conversation
        task = ""
        # First try: user message in this span's conversation
        for i in range(50):
            role = span.attributes.get(f"llm.input_messages.{i}.message.role", "")
            content = span.attributes.get(f"llm.input_messages.{i}.message.content", "")
            if role == "user" and content and len(str(content)) > 20:
                task = str(content)[:4000]
                break

        # Fallback: root span's agent input
        if not task:
            for root in trace.spans:
                for child in root.child_spans:
                    inp = self._get_input(child)
                    if inp and len(inp) > 20:
                        task = inp[:4000]
                        break
                if task:
                    break

        if not task:
            task = self._get_input(span)

        return {
            "output": output,
            "task": task,
        }

    def _extract_coordination(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for coordination detector.

        Expected keys: agent_ids, messages
        TRAIL traces often use smolagents with managed sub-agents.
        Agent IDs come from span names and smolagents metadata.
        """
        agent_ids: List[str] = []
        messages: List[Dict[str, str]] = []

        for flat_span in trace.flatten_spans():
            # Try multiple agent ID sources
            agent_id = self._get_attr(
                flat_span, "gen_ai.agent.id", "agent.id", "agent_id"
            )
            # TRAIL smolagents traces use span names as agent identifiers
            if not agent_id:
                name = flat_span.span_name
                if "Agent" in name or "agent" in name:
                    agent_id = name
                elif name.startswith("Step"):
                    agent_id = "main_agent"
            # Also check for managed_agents in attributes
            if not agent_id:
                for k, v in flat_span.attributes.items():
                    if "managed_agents" in k and "description" in k:
                        agent_id = str(v)[:50]
                        break

            if agent_id and agent_id not in agent_ids:
                agent_ids.append(agent_id)

            inp = self._get_input(flat_span)
            out = self._get_output(flat_span)
            sender = agent_id or flat_span.span_name

            if out:
                messages.append({
                    "sender": sender,
                    "content": str(out)[:2000],
                    "type": "output",
                })

        # If only one agent found, try to infer from conversation roles
        if len(agent_ids) <= 1:
            for i in range(50):
                role = span.attributes.get(f"llm.input_messages.{i}.message.role", "")
                if role == "tool-call":
                    if "tool_agent" not in agent_ids:
                        agent_ids.append("tool_agent")
                elif role == "tool-response":
                    if "tool_executor" not in agent_ids:
                        agent_ids.append("tool_executor")

        return {
            "agent_ids": agent_ids,
            "messages": messages,
        }

    def _extract_completion(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for completion detector.

        Expected keys: agent_output, subtasks, success_criteria, task
        For TRAIL's "Formatting Errors", this captures the agent's output
        and the task requirements to check if completion claims are valid.
        """
        agent_output = self._get_output(span)

        # Find the original task from conversation or root spans
        task = ""
        for i in range(50):
            role = span.attributes.get(f"llm.input_messages.{i}.message.role", "")
            content = span.attributes.get(f"llm.input_messages.{i}.message.content", "")
            if role == "user" and content and len(str(content)) > 20:
                task = str(content)[:4000]
                break
        if not task:
            for root in trace.spans:
                for child in root.child_spans:
                    inp = self._get_input(child)
                    if inp and len(inp) > 20:
                        task = inp[:4000]
                        break
                if task:
                    break

        # Collect subtask outputs from child spans and sibling steps
        subtasks: List[str] = []
        parent = trace.get_parent_span(span)
        if parent:
            for sibling in parent.child_spans:
                out = self._get_output(sibling)
                if out and sibling.span_id != span.span_id:
                    subtasks.append(out[:2000])

        return {
            "agent_output": agent_output,
            "subtasks": subtasks,
            "success_criteria": [],
            "task": task,
        }

    def _extract_workflow(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for workflow detector.

        Expected keys: execution_result, workflow_definition
        """
        execution_result = self._get_output(span)

        # Reconstruct workflow from span tree
        workflow_steps: List[Dict[str, str]] = []
        for flat_span in trace.flatten_spans():
            step: Dict[str, str] = {"name": flat_span.span_name}
            if flat_span.tool_name:
                step["tool"] = flat_span.tool_name
            inp = self._get_input(flat_span)
            if inp:
                step["input"] = inp[:500]
            out = self._get_output(flat_span)
            if out:
                step["output"] = out[:500]
            workflow_steps.append(step)

        return {
            "execution_result": execution_result,
            "workflow_definition": {"steps": workflow_steps},
        }

    def _extract_overflow(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for overflow detector.

        Expected keys: context (the text that may be too large),
        plus token usage metadata if available.
        """
        # Aggregate all text in the trace to estimate context size
        total_text: List[str] = []
        total_tokens = 0

        for flat_span in trace.flatten_spans():
            inp = self._get_input(flat_span)
            out = self._get_output(flat_span)
            if inp:
                total_text.append(inp)
            if out:
                total_text.append(out)

            # Check for token usage attributes
            tokens = flat_span.attributes.get(
                "gen_ai.usage.prompt_tokens",
                flat_span.attributes.get("llm.token_count.prompt", 0),
            )
            if tokens:
                total_tokens += int(tokens)

        return {
            "context": "\n".join(total_text),
            "token_count": total_tokens,
        }
