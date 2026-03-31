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
        """Extract output text from a span."""
        return self._get_attr(
            span, "output.value", "gen_ai.output", "llm.output",
            "output.message", "gen_ai.completion",
        )

    def _get_input(self, span: TRAILSpan) -> str:
        """Extract input text from a span."""
        return self._get_attr(
            span, "input.value", "gen_ai.input", "llm.input",
            "input.message", "gen_ai.prompt",
        )

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
        """
        output = self._get_output(span)
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
        """
        # The task specification is typically the initial input
        user_intent = self._get_input(span)

        # Look for the original task in root spans
        root_input = ""
        for root in trace.spans:
            inp = self._get_input(root)
            if inp:
                root_input = inp
                break

        task_spec = root_input if root_input else user_intent

        return {
            "task_specification": self._get_output(span),
            "user_intent": task_spec,
        }

    def _extract_context(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for context detector.

        Expected keys: context, output
        """
        output = self._get_output(span)
        context = self._collect_context_text(trace, span.span_id)

        # Also include the input as part of context
        input_text = self._get_input(span)
        if input_text:
            context = input_text + "\n---\n" + context if context else input_text

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
        """
        output = self._get_output(span)

        # Find the original task from root spans
        task = ""
        for root in trace.spans:
            inp = self._get_input(root)
            if inp:
                task = inp
                break

        return {
            "output": output,
            "task": task,
        }

    def _extract_coordination(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for coordination detector.

        Expected keys: agent_ids, messages
        """
        agent_ids: List[str] = []
        messages: List[Dict[str, str]] = []

        for flat_span in trace.flatten_spans():
            agent_id = self._get_attr(
                flat_span, "gen_ai.agent.id", "agent.id", "agent_id"
            )
            if agent_id and agent_id not in agent_ids:
                agent_ids.append(agent_id)

            inp = self._get_input(flat_span)
            out = self._get_output(flat_span)
            sender = agent_id or flat_span.span_name

            if inp:
                messages.append({
                    "sender": sender,
                    "content": inp,
                    "type": "input",
                })
            if out:
                messages.append({
                    "sender": sender,
                    "content": out,
                    "type": "output",
                })

        return {
            "agent_ids": agent_ids,
            "messages": messages,
        }

    def _extract_completion(
        self, span: TRAILSpan, trace: TRAILTrace
    ) -> Dict[str, Any]:
        """Extract for completion detector.

        Expected keys: agent_output, subtasks, success_criteria, task
        """
        agent_output = self._get_output(span)

        # Find task from root
        task = ""
        for root in trace.spans:
            inp = self._get_input(root)
            if inp:
                task = inp
                break

        # Collect subtask outputs
        subtasks: List[str] = []
        for child in span.child_spans:
            out = self._get_output(child)
            if out:
                subtasks.append(out)

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
