"""Raw JSON importer for generic trace formats.

Handles JSON traces that don't match a specific format like LangSmith or OTEL.
Uses heuristics to extract span information from arbitrary JSON structures.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from app.ingestion.universal_trace import UniversalSpan, UniversalTrace, SpanType, SpanStatus
from .base import BaseImporter


class RawJSONImporter(BaseImporter):
    """Importer for generic/raw JSON trace formats.

    This importer uses heuristics to parse JSON traces that don't match
    a specific format. It attempts to extract common fields and build
    a reasonable UniversalTrace representation.
    """

    @property
    def format_name(self) -> str:
        return "raw"

    def import_trace(self, content: str) -> UniversalTrace:
        """Import a raw JSON trace.

        Args:
            content: JSON string containing trace data

        Returns:
            UniversalTrace with parsed spans
        """
        spans = list(self.import_spans(content))

        if not spans:
            raise ValueError("No valid spans found in content")

        # Use first span's trace_id or generate one
        trace_id = spans[0].trace_id if spans else str(uuid.uuid4())

        trace = UniversalTrace(
            trace_id=trace_id,
            spans=spans,
            source_format=self.format_name,
        )

        return trace

    def import_spans(self, content: str) -> Iterator[UniversalSpan]:
        """Parse raw JSON content into spans.

        Args:
            content: JSON string (single object, array, or JSONL)

        Yields:
            UniversalSpan instances
        """
        content = content.strip()

        if not content:
            return

        # Try parsing as array first
        if content.startswith('['):
            try:
                data = json.loads(content)
                if not self._check_depth(data):
                    raise ValueError("JSON depth exceeds limit")

                for item in data:
                    yield from self._parse_item(item)
                return
            except json.JSONDecodeError:
                pass

        # Try parsing as single object
        if content.startswith('{'):
            try:
                data = json.loads(content)
                if not self._check_depth(data):
                    raise ValueError("JSON depth exceeds limit")

                yield from self._parse_item(data)
                return
            except json.JSONDecodeError:
                pass

        # Try parsing as JSONL (newline-delimited JSON)
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if not self._check_depth(data):
                    continue
                yield from self._parse_item(data)
            except json.JSONDecodeError:
                continue

    def _parse_item(self, data: Dict[str, Any], parent_id: Optional[str] = None) -> Iterator[UniversalSpan]:
        """Parse a single item into one or more spans.

        Args:
            data: Dictionary to parse
            parent_id: Optional parent span ID

        Yields:
            UniversalSpan instances
        """
        if not isinstance(data, dict):
            return

        # Generate or extract span ID
        span_id = str(
            data.get("id") or
            data.get("span_id") or
            data.get("run_id") or
            uuid.uuid4()
        )

        # Extract trace ID
        trace_id = str(
            data.get("trace_id") or
            data.get("session_id") or
            data.get("execution_id") or
            span_id
        )

        # Extract parent ID
        extracted_parent = data.get("parent_id") or data.get("parent_run_id") or parent_id

        # Extract name
        name = str(
            data.get("name") or
            data.get("operation") or
            data.get("action") or
            data.get("type") or
            "unknown"
        )

        # Extract timing
        start_time = self._parse_timestamp(
            data.get("start_time") or
            data.get("started_at") or
            data.get("timestamp") or
            datetime.utcnow()
        )
        end_time = None
        if data.get("end_time") or data.get("ended_at"):
            end_time = self._parse_timestamp(data.get("end_time") or data.get("ended_at"))

        # Infer type and status
        span_type = self._infer_span_type(data)
        status = self._infer_status(data)

        # Extract error info
        error_msg, error_type = self._extract_error(data)

        # Extract token counts
        tokens_input, tokens_output = self._extract_tokens(data)

        # Extract input/output
        input_data = self._extract_input(data)
        output_data = self._extract_output(data)

        # Extract LLM-specific fields
        prompt = self._extract_prompt(data)
        response = self._extract_response(data)
        model = data.get("model") or data.get("model_name") or data.get("llm_model")

        # Extract tool-specific fields
        tool_name = data.get("tool_name") or data.get("function_name") or data.get("tool")
        tool_args = data.get("tool_args") or data.get("function_args") or data.get("arguments")
        tool_result = data.get("tool_result") or data.get("function_result") or data.get("result")

        # If tool_args is a string, try to parse it
        if isinstance(tool_args, str):
            try:
                tool_args = json.loads(tool_args)
            except json.JSONDecodeError:
                tool_args = {"raw": tool_args}

        # Extract agent info
        agent_id = data.get("agent_id") or data.get("agent")
        agent_name = data.get("agent_name") or agent_id

        # Create the span
        span = UniversalSpan(
            id=span_id,
            trace_id=trace_id,
            name=name,
            span_type=span_type,
            status=status,
            start_time=start_time,
            end_time=end_time,
            parent_id=extracted_parent,
            agent_id=agent_id,
            agent_name=agent_name,
            input_data=input_data,
            output_data=output_data,
            prompt=prompt,
            response=response,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            error=error_msg,
            error_type=error_type,
            source_format=self.format_name,
            raw_data=data,
            metadata=data.get("metadata") or data.get("extra") or {},
        )

        yield span

        # Recursively process nested spans
        for key in ["children", "spans", "steps", "runs", "tool_calls"]:
            if key in data and isinstance(data[key], list):
                for child in data[key]:
                    if isinstance(child, dict):
                        yield from self._parse_item(child, parent_id=span_id)

    def _extract_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract input data from various field patterns."""
        input_data = {}

        # Check common input field names
        for key in ["input", "inputs", "request", "query", "question", "messages"]:
            if key in data:
                val = data[key]
                if isinstance(val, dict):
                    input_data.update(val)
                elif isinstance(val, str):
                    input_data["text"] = val
                elif isinstance(val, list):
                    input_data["items"] = val
                break

        return input_data

    def _extract_output(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract output data from various field patterns."""
        output_data = {}

        # Check common output field names
        for key in ["output", "outputs", "response", "answer", "result", "completion"]:
            if key in data:
                val = data[key]
                if isinstance(val, dict):
                    output_data.update(val)
                elif isinstance(val, str):
                    output_data["text"] = val
                elif isinstance(val, list):
                    output_data["items"] = val
                break

        return output_data

    def _extract_prompt(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract LLM prompt from various field patterns."""
        # Direct prompt field
        if "prompt" in data:
            prompt = data["prompt"]
            if isinstance(prompt, str):
                return prompt
            if isinstance(prompt, list):
                return json.dumps(prompt)

        # Messages array (ChatGPT style)
        if "messages" in data:
            messages = data["messages"]
            if isinstance(messages, list):
                return json.dumps(messages)

        # Input field might contain prompt
        inputs = data.get("inputs") or data.get("input") or {}
        if isinstance(inputs, dict):
            for key in ["prompt", "input", "query", "question", "messages"]:
                if key in inputs:
                    val = inputs[key]
                    return json.dumps(val) if not isinstance(val, str) else val

        return None

    def _extract_response(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract LLM response from various field patterns."""
        # Direct response/completion field
        for key in ["response", "completion", "answer", "generated_text", "content"]:
            if key in data:
                val = data[key]
                if isinstance(val, str):
                    return val
                if isinstance(val, dict) and "text" in val:
                    return val["text"]

        # Output field might contain response
        outputs = data.get("outputs") or data.get("output") or {}
        if isinstance(outputs, dict):
            for key in ["response", "text", "content", "generated"]:
                if key in outputs:
                    return str(outputs[key])
            if "text" not in outputs and outputs:
                # Return first string value
                for v in outputs.values():
                    if isinstance(v, str):
                        return v

        if isinstance(outputs, str):
            return outputs

        # Choices array (OpenAI style)
        if "choices" in data:
            choices = data["choices"]
            if isinstance(choices, list) and len(choices) > 0:
                choice = choices[0]
                if isinstance(choice, dict):
                    message = choice.get("message") or choice.get("text") or {}
                    if isinstance(message, dict):
                        return message.get("content")
                    if isinstance(message, str):
                        return message

        return None
