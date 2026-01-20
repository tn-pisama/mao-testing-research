"""LangSmith trace importer.

Handles traces exported from LangSmith (LangChain's tracing platform).
Supports both single-run exports and multi-run session exports.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from app.ingestion.universal_trace import UniversalSpan, UniversalTrace, SpanType, SpanStatus
from app.ingestion.importers.base import BaseImporter


class LangSmithImporter(BaseImporter):
    """Importer for LangSmith trace format.

    LangSmith exports traces in JSONL format with each line containing
    a run object with fields like:
    - run_type: "llm", "chain", "tool", "retriever"
    - inputs: input data
    - outputs: output data
    - session_id: trace/session identifier
    - id: run/span identifier
    """

    @property
    def format_name(self) -> str:
        return "langsmith"

    def import_trace(self, content: str) -> UniversalTrace:
        """Import a LangSmith trace export.

        Args:
            content: JSONL or JSON content from LangSmith

        Returns:
            UniversalTrace with parsed spans
        """
        spans = list(self.import_spans(content))

        if not spans:
            raise ValueError("No valid spans found in LangSmith content")

        # Use session_id from first span or generate one
        trace_id = spans[0].trace_id if spans else str(uuid.uuid4())

        trace = UniversalTrace(
            trace_id=trace_id,
            spans=spans,
            source_format=self.format_name,
        )

        return trace

    def import_spans(self, content: str) -> Iterator[UniversalSpan]:
        """Parse LangSmith content into spans.

        Args:
            content: JSONL or JSON content

        Yields:
            UniversalSpan instances
        """
        content = content.strip()

        if not content:
            return

        # Try parsing as JSON array first
        if content.startswith('['):
            try:
                data = json.loads(content)
                if not self._check_depth(data):
                    raise ValueError("JSON depth exceeds limit")

                for run in data:
                    yield from self._parse_run(run)
                return
            except json.JSONDecodeError:
                pass

        # Parse as JSONL (each line is a run)
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                run = json.loads(line)
                if not self._check_depth(run):
                    continue
                yield from self._parse_run(run)
            except json.JSONDecodeError:
                continue

    def _parse_run(self, run: Dict[str, Any]) -> Iterator[UniversalSpan]:
        """Parse a LangSmith run object into UniversalSpan.

        Args:
            run: LangSmith run dictionary

        Yields:
            UniversalSpan instances
        """
        if not isinstance(run, dict):
            return

        # Extract identifiers
        span_id = str(run.get("id") or run.get("run_id") or uuid.uuid4())
        trace_id = str(run.get("session_id") or run.get("trace_id") or span_id)
        parent_id = run.get("parent_run_id")

        # Map run_type to SpanType
        run_type = run.get("run_type", "").lower()
        span_type = self._map_run_type(run_type)

        # Extract name
        name = run.get("name") or run_type or "unknown"

        # Extract timing
        start_time = self._parse_timestamp(run.get("start_time") or datetime.utcnow())
        end_time = None
        if run.get("end_time"):
            end_time = self._parse_timestamp(run["end_time"])

        # Determine status
        status = SpanStatus.OK
        error_msg = None
        error_type = None

        if run.get("error"):
            status = SpanStatus.ERROR
            error_msg = run["error"]
            error_type = "LangSmithError"
        elif run.get("status") == "error":
            status = SpanStatus.ERROR

        # Extract inputs/outputs
        inputs = run.get("inputs") or {}
        outputs = run.get("outputs") or {}

        # Extract LLM-specific data
        prompt = None
        response = None
        model = None
        tokens_input = 0
        tokens_output = 0

        if run_type in ["llm", "chat"]:
            # Extract prompt from inputs
            if "prompts" in inputs:
                prompt = json.dumps(inputs["prompts"])
            elif "messages" in inputs:
                prompt = json.dumps(inputs["messages"])
            elif isinstance(inputs, dict) and inputs:
                prompt = json.dumps(inputs)

            # Extract response from outputs
            if "generations" in outputs:
                generations = outputs["generations"]
                if isinstance(generations, list) and len(generations) > 0:
                    gen = generations[0]
                    if isinstance(gen, list) and len(gen) > 0:
                        gen = gen[0]
                    if isinstance(gen, dict):
                        response = gen.get("text") or gen.get("content")
            elif "output" in outputs:
                response = outputs["output"]

            # Extract token usage
            if "llm_output" in outputs:
                llm_output = outputs["llm_output"] or {}
                usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
                tokens_input = usage.get("prompt_tokens") or 0
                tokens_output = usage.get("completion_tokens") or 0

            # Extract model info
            extra = run.get("extra") or {}
            invocation_params = extra.get("invocation_params") or {}
            model = invocation_params.get("model") or invocation_params.get("model_name")

        # Extract tool-specific data
        tool_name = None
        tool_args = None
        tool_result = None

        if run_type == "tool":
            tool_name = name
            tool_args = inputs
            tool_result = outputs

        # Create span
        span = UniversalSpan(
            id=span_id,
            trace_id=trace_id,
            name=name,
            span_type=span_type,
            status=status,
            start_time=start_time,
            end_time=end_time,
            parent_id=parent_id,
            input_data=inputs if isinstance(inputs, dict) else {"value": inputs},
            output_data=outputs if isinstance(outputs, dict) else {"value": outputs},
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
            raw_data=run,
            metadata=run.get("extra") or {},
        )

        yield span

        # Process child runs if present
        for child in run.get("child_runs") or []:
            yield from self._parse_run(child)

    def _map_run_type(self, run_type: str) -> SpanType:
        """Map LangSmith run_type to SpanType.

        Args:
            run_type: LangSmith run type string

        Returns:
            Corresponding SpanType
        """
        mapping = {
            "llm": SpanType.LLM_CALL,
            "chat": SpanType.LLM_CALL,
            "chain": SpanType.CHAIN,
            "tool": SpanType.TOOL_CALL,
            "retriever": SpanType.RETRIEVAL,
            "embedding": SpanType.RETRIEVAL,
            "agent": SpanType.AGENT,
        }
        return mapping.get(run_type, SpanType.UNKNOWN)
