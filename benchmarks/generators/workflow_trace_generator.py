"""Generate traces using the new pipeline and recovery workflows.

Produces complex, realistic traces with:
- Validation checkpoint spans
- Retry/fallback patterns
- Tool call spans
- Error/recovery spans
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


# Failure mode definitions relevant to new workflows
WORKFLOW_FAILURE_MODES = {
    "F5": {
        "name": "Flawed Workflow Design",
        "description": "Process has structural problems",
        "workflow": "recovery",
        "injection": "skip_error_handling",
    },
    "F11": {
        "name": "Coordination Failure",
        "description": "Timing/sequencing errors",
        "workflow": "pipeline",
        "injection": "race_condition",
    },
    "F13": {
        "name": "Quality Gate Bypass",
        "description": "Verification checkpoints skipped",
        "workflow": "pipeline",
        "injection": "skip_gates",
    },
    "F14": {
        "name": "Completion Misjudgment",
        "description": "Task marked done when incomplete",
        "workflow": "recovery",
        "injection": "premature_completion",
    },
}

# Task templates for different workflows
PIPELINE_TASKS = [
    {"topic": "API security best practices", "requirements": "Include authentication, authorization, and rate limiting"},
    {"topic": "Kubernetes deployment strategies", "requirements": "Cover blue-green, canary, and rolling updates"},
    {"topic": "Database optimization techniques", "requirements": "Focus on indexing, query optimization, and caching"},
    {"topic": "Microservices architecture patterns", "requirements": "Include service discovery, circuit breakers, and API gateways"},
    {"topic": "CI/CD pipeline best practices", "requirements": "Cover testing stages, deployment automation, and rollback strategies"},
]

RECOVERY_TASKS = [
    {"task": "Analyze server logs and identify the root cause of the 500 errors", "context": "Production server returning 500 errors since 2am"},
    {"task": "Migrate user data from legacy PostgreSQL to new MongoDB cluster", "context": "50GB of user records need migration"},
    {"task": "Debug memory leak in the Node.js application", "context": "Memory usage growing 100MB/hour"},
    {"task": "Implement automated backup system for S3 buckets", "context": "Need cross-region backup with 15-minute RPO"},
    {"task": "Set up monitoring and alerting for microservices", "context": "12 services running on Kubernetes"},
]


@dataclass
class SpanCollector(BaseCallbackHandler):
    """Callback handler that collects spans from LLM calls."""

    trace_id: str = ""
    spans: list = field(default_factory=list)
    span_stack: list = field(default_factory=list)

    def _generate_span_id(self) -> str:
        return f"span_{uuid.uuid4().hex[:12]}"

    def on_llm_start(self, serialized: dict, prompts: list, **kwargs) -> None:
        span_id = self._generate_span_id()
        parent_id = self.span_stack[-1] if self.span_stack else None

        span = {
            "trace_id": self.trace_id,
            "span_id": span_id,
            "parent_id": parent_id,
            "name": kwargs.get("name", serialized.get("name", "llm_call")),
            "span_type": "llm",
            "status": "running",
            "start_time": datetime.utcnow().isoformat() + "Z",
            "input_data": {"prompts": prompts[:1]},
            "model": serialized.get("kwargs", {}).get("model", "unknown"),
        }

        self.span_stack.append(span_id)
        self.spans.append(span)

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        if self.span_stack:
            span_id = self.span_stack.pop()
            for span in self.spans:
                if span["span_id"] == span_id:
                    span["status"] = "ok"
                    span["end_time"] = datetime.utcnow().isoformat() + "Z"
                    if response.generations:
                        span["output_data"] = {"response": str(response.generations[0][0].text)[:500]}
                    if hasattr(response, 'llm_output') and response.llm_output:
                        span["tokens_input"] = response.llm_output.get("usage", {}).get("input_tokens", 0)
                        span["tokens_output"] = response.llm_output.get("usage", {}).get("output_tokens", 0)
                    break

    def on_llm_error(self, error: Exception, **kwargs) -> None:
        if self.span_stack:
            span_id = self.span_stack.pop()
            for span in self.spans:
                if span["span_id"] == span_id:
                    span["status"] = "error"
                    span["end_time"] = datetime.utcnow().isoformat() + "Z"
                    span["error"] = str(error)
                    break


class WorkflowTraceGenerator:
    """Generate traces using pipeline and recovery workflows."""

    def __init__(self, api_key: str, output_dir: str = "traces"):
        self.api_key = api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.model = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            max_tokens=2048,
            api_key=api_key,
        )

    def _generate_trace_id(self) -> str:
        return f"trace_{uuid.uuid4().hex[:16]}"

    def _generate_span_id(self) -> str:
        return f"span_{uuid.uuid4().hex[:12]}"

    async def generate_pipeline_trace(
        self,
        task_template: dict,
        failure_mode: str | None = None,
        inject_failure: bool = True,
    ) -> dict:
        """Generate a trace using the pipeline workflow pattern."""

        trace_id = self._generate_trace_id()
        start_time = datetime.utcnow()
        spans = []

        # Root span for pipeline workflow
        root_span_id = self._generate_span_id()

        # Determine if gates should be skipped (F13)
        skip_gates = failure_mode == "F13" and inject_failure

        # 1. Research phase
        research_span_id = self._generate_span_id()
        research_start = start_time + timedelta(milliseconds=50)

        research_prompt = f"""Research the topic: {task_template['topic']}
Requirements: {task_template['requirements']}

Provide comprehensive research notes."""

        research_response = await self.model.ainvoke([
            SystemMessage(content="You are a research agent."),
            HumanMessage(content=research_prompt),
        ])
        research_output = research_response.content
        research_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": research_span_id,
            "parent_id": root_span_id,
            "name": "research_agent",
            "agent_id": "researcher",
            "span_type": "agent",
            "status": "ok",
            "start_time": research_start.isoformat() + "Z",
            "end_time": research_end.isoformat() + "Z",
            "duration_ms": int((research_end - research_start).total_seconds() * 1000),
            "input_data": {"topic": task_template['topic']},
            "output_data": {"research": research_output[:300]},
        })

        # 2. Research validation checkpoint
        val1_span_id = self._generate_span_id()
        val1_start = research_end + timedelta(milliseconds=20)

        if skip_gates:
            val1_status = "skipped"
            val1_output = "VALIDATION SKIPPED: Quality gate bypassed"
        else:
            val1_prompt = f"""Validate this research:
{research_output[:500]}

Check for: relevance, factual accuracy, completeness."""

            val1_response = await self.model.ainvoke([
                SystemMessage(content="You are a validation agent."),
                HumanMessage(content=val1_prompt),
            ])
            val1_output = val1_response.content
            val1_status = "ok"

        val1_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": val1_span_id,
            "parent_id": root_span_id,
            "name": "validate_research",
            "agent_id": "validator",
            "span_type": "validation",
            "status": val1_status,
            "start_time": val1_start.isoformat() + "Z",
            "end_time": val1_end.isoformat() + "Z",
            "duration_ms": int((val1_end - val1_start).total_seconds() * 1000),
            "input_data": {"validation_type": "research_quality"},
            "output_data": {"result": val1_output[:200]},
            "gate_passed": True,
            "gate_skipped": skip_gates,
        })

        # 3. Writer phase
        writer_span_id = self._generate_span_id()
        writer_start = val1_end + timedelta(milliseconds=30)

        writer_prompt = f"""Based on this research:
{research_output[:800]}

Write a comprehensive article about {task_template['topic']}.
Requirements: {task_template['requirements']}"""

        writer_response = await self.model.ainvoke([
            SystemMessage(content="You are a technical writer."),
            HumanMessage(content=writer_prompt),
        ])
        writer_output = writer_response.content
        writer_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": writer_span_id,
            "parent_id": root_span_id,
            "name": "writer_agent",
            "agent_id": "writer",
            "span_type": "agent",
            "status": "ok",
            "start_time": writer_start.isoformat() + "Z",
            "end_time": writer_end.isoformat() + "Z",
            "duration_ms": int((writer_end - writer_start).total_seconds() * 1000),
            "input_data": {"research_summary": research_output[:100]},
            "output_data": {"content": writer_output[:300]},
        })

        # 4. Content validation checkpoint
        val2_span_id = self._generate_span_id()
        val2_start = writer_end + timedelta(milliseconds=20)

        if skip_gates:
            val2_status = "skipped"
            val2_output = "VALIDATION SKIPPED: Quality gate bypassed"
        else:
            val2_prompt = f"""Validate this content:
{writer_output[:500]}

Check for: format compliance, completeness, quality."""

            val2_response = await self.model.ainvoke([
                SystemMessage(content="You are a validation agent."),
                HumanMessage(content=val2_prompt),
            ])
            val2_output = val2_response.content
            val2_status = "ok"

        val2_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": val2_span_id,
            "parent_id": root_span_id,
            "name": "validate_content",
            "agent_id": "validator",
            "span_type": "validation",
            "status": val2_status,
            "start_time": val2_start.isoformat() + "Z",
            "end_time": val2_end.isoformat() + "Z",
            "duration_ms": int((val2_end - val2_start).total_seconds() * 1000),
            "input_data": {"validation_type": "content_quality"},
            "output_data": {"result": val2_output[:200]},
            "gate_passed": True,
            "gate_skipped": skip_gates,
        })

        # 5. Review phase
        review_span_id = self._generate_span_id()
        review_start = val2_end + timedelta(milliseconds=30)

        review_prompt = f"""Review this content:
{writer_output[:600]}

Provide feedback on quality, accuracy, and completeness."""

        review_response = await self.model.ainvoke([
            SystemMessage(content="You are a content reviewer."),
            HumanMessage(content=review_prompt),
        ])
        review_output = review_response.content
        review_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": review_span_id,
            "parent_id": root_span_id,
            "name": "reviewer_agent",
            "agent_id": "reviewer",
            "span_type": "agent",
            "status": "ok",
            "start_time": review_start.isoformat() + "Z",
            "end_time": review_end.isoformat() + "Z",
            "duration_ms": int((review_end - review_start).total_seconds() * 1000),
            "input_data": {"content_summary": writer_output[:100]},
            "output_data": {"feedback": review_output[:300]},
        })

        # 6. Final validation checkpoint
        val3_span_id = self._generate_span_id()
        val3_start = review_end + timedelta(milliseconds=20)

        if skip_gates:
            val3_status = "skipped"
            val3_output = "FINAL VALIDATION SKIPPED: Quality gate bypassed - proceeding without approval"
            final_status = "completed_with_bypassed_gates"
        else:
            val3_prompt = f"""Final validation check:
Content: {writer_output[:300]}
Review: {review_output[:200]}

Confirm all requirements are met."""

            val3_response = await self.model.ainvoke([
                SystemMessage(content="You are a final validation agent."),
                HumanMessage(content=val3_prompt),
            ])
            val3_output = val3_response.content
            val3_status = "ok"
            final_status = "success"

        val3_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": val3_span_id,
            "parent_id": root_span_id,
            "name": "validate_final",
            "agent_id": "validator",
            "span_type": "validation",
            "status": val3_status,
            "start_time": val3_start.isoformat() + "Z",
            "end_time": val3_end.isoformat() + "Z",
            "duration_ms": int((val3_end - val3_start).total_seconds() * 1000),
            "input_data": {"validation_type": "final_approval"},
            "output_data": {"result": val3_output[:200]},
            "gate_passed": True,
            "gate_skipped": skip_gates,
        })

        # Root span
        root_end = val3_end + timedelta(milliseconds=30)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "workflow.pipeline",
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "input_data": {"task": task_template['topic'], "requirements": task_template['requirements']},
            "output_data": {"final_status": final_status},
            "workflow_type": "pipeline",
            "validation_checkpoints": 3,
            "gates_skipped": skip_gates,
            "metadata": {
                "failure_mode": failure_mode,
                "failure_injected": inject_failure and failure_mode is not None,
            }
        })

        return {
            "trace_id": trace_id,
            "workflow_type": "pipeline",
            "failure_mode": failure_mode,
            "spans": spans,
            "total_duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "span_count": len(spans),
        }

    async def generate_recovery_trace(
        self,
        task_template: dict,
        failure_mode: str | None = None,
        inject_failure: bool = True,
        force_retries: int = 0,
    ) -> dict:
        """Generate a trace using the recovery workflow pattern."""

        trace_id = self._generate_trace_id()
        start_time = datetime.utcnow()
        spans = []

        # Root span for recovery workflow
        root_span_id = self._generate_span_id()

        # Determine failure injection
        should_fail_initially = inject_failure and failure_mode in ["F5", "F14"]
        max_retries = 3 if should_fail_initially else 1
        actual_retries = force_retries if force_retries > 0 else (2 if should_fail_initially else 0)

        # 1. Planning phase
        plan_span_id = self._generate_span_id()
        plan_start = start_time + timedelta(milliseconds=50)

        plan_prompt = f"""Create an execution plan for this task:
Task: {task_template['task']}
Context: {task_template['context']}

Break down into steps with tool requirements."""

        plan_response = await self.model.ainvoke([
            SystemMessage(content="You are a planning agent."),
            HumanMessage(content=plan_prompt),
        ])
        plan_output = plan_response.content
        plan_end = datetime.utcnow()

        spans.append({
            "trace_id": trace_id,
            "span_id": plan_span_id,
            "parent_id": root_span_id,
            "name": "planner_agent",
            "agent_id": "planner",
            "span_type": "agent",
            "status": "ok",
            "start_time": plan_start.isoformat() + "Z",
            "end_time": plan_end.isoformat() + "Z",
            "duration_ms": int((plan_end - plan_start).total_seconds() * 1000),
            "input_data": {"task": task_template['task']},
            "output_data": {"plan": plan_output[:300]},
        })

        # 2. Execution attempts (with retries)
        last_exec_end = plan_end
        execution_success = False
        errors = []

        for attempt in range(actual_retries + 1):
            exec_span_id = self._generate_span_id()
            exec_start = last_exec_end + timedelta(milliseconds=30)

            # Tool call spans within execution
            tool_spans = []
            tool_start = exec_start + timedelta(milliseconds=10)

            # Simulate tool calls
            tools_to_call = ["database_query", "file_read", "api_call"]
            for tool_idx, tool_name in enumerate(tools_to_call):
                tool_span_id = self._generate_span_id()
                tool_call_start = tool_start + timedelta(milliseconds=tool_idx * 100)

                # Determine if this tool call fails
                tool_fails = should_fail_initially and attempt < actual_retries and tool_idx == 1

                tool_call_end = tool_call_start + timedelta(milliseconds=80)

                tool_span = {
                    "trace_id": trace_id,
                    "span_id": tool_span_id,
                    "parent_id": exec_span_id,
                    "name": f"tool.{tool_name}",
                    "agent_id": "executor",
                    "span_type": "tool_call",
                    "status": "error" if tool_fails else "ok",
                    "start_time": tool_call_start.isoformat() + "Z",
                    "end_time": tool_call_end.isoformat() + "Z",
                    "duration_ms": int((tool_call_end - tool_call_start).total_seconds() * 1000),
                    "input_data": {"tool": tool_name, "params": {"query": f"execute_{tool_name}"}},
                    "output_data": {"result": "error: connection timeout" if tool_fails else "success"},
                    "tool_name": tool_name,
                    "tool_status": "error" if tool_fails else "success",
                }

                if tool_fails:
                    tool_span["error"] = "Connection timeout after 30s"
                    errors.append(f"Tool {tool_name} failed: Connection timeout")

                tool_spans.append(tool_span)

            spans.extend(tool_spans)

            # Execution result
            exec_fails = should_fail_initially and attempt < actual_retries

            if exec_fails:
                exec_prompt = f"""Execution attempt {attempt + 1} for: {task_template['task']}

Some tools failed. Generate a partial result."""
                exec_status = "error"
            else:
                exec_prompt = f"""Execute the task: {task_template['task']}
Plan: {plan_output[:300]}

Generate successful execution output."""
                exec_status = "ok"
                execution_success = True

            exec_response = await self.model.ainvoke([
                SystemMessage(content="You are an executor agent."),
                HumanMessage(content=exec_prompt),
            ])
            exec_output = exec_response.content
            exec_end = datetime.utcnow()

            spans.append({
                "trace_id": trace_id,
                "span_id": exec_span_id,
                "parent_id": root_span_id,
                "name": f"executor_agent.attempt_{attempt + 1}",
                "agent_id": "executor",
                "span_type": "agent",
                "status": exec_status,
                "start_time": exec_start.isoformat() + "Z",
                "end_time": exec_end.isoformat() + "Z",
                "duration_ms": int((exec_end - exec_start).total_seconds() * 1000),
                "input_data": {"task": task_template['task'], "attempt": attempt + 1},
                "output_data": {"result": exec_output[:300]},
                "retry_attempt": attempt + 1,
                "max_retries": max_retries,
                "errors": errors.copy() if exec_fails else [],
            })

            # Add retry span if not the last attempt and failed
            if exec_fails and attempt < actual_retries:
                retry_span_id = self._generate_span_id()
                retry_start = exec_end + timedelta(milliseconds=20)
                retry_end = retry_start + timedelta(milliseconds=50)

                spans.append({
                    "trace_id": trace_id,
                    "span_id": retry_span_id,
                    "parent_id": root_span_id,
                    "name": "retry_decision",
                    "agent_id": "orchestrator",
                    "span_type": "retry",
                    "status": "ok",
                    "start_time": retry_start.isoformat() + "Z",
                    "end_time": retry_end.isoformat() + "Z",
                    "duration_ms": int((retry_end - retry_start).total_seconds() * 1000),
                    "input_data": {"current_attempt": attempt + 1, "max_retries": max_retries},
                    "output_data": {"decision": "retry", "reason": f"Attempt {attempt + 1} failed, retrying..."},
                    "retry_count": attempt + 1,
                })

                exec_end = retry_end

            last_exec_end = exec_end

            if execution_success:
                break

        # 3. Fallback (if all retries exhausted without success)
        if not execution_success and should_fail_initially:
            fallback_span_id = self._generate_span_id()
            fallback_start = last_exec_end + timedelta(milliseconds=30)

            fallback_prompt = f"""FALLBACK MODE: Simplified execution for: {task_template['task']}
Previous errors: {', '.join(errors[:3])}

Attempt minimal successful completion."""

            fallback_response = await self.model.ainvoke([
                SystemMessage(content="You are a fallback executor."),
                HumanMessage(content=fallback_prompt),
            ])
            fallback_output = fallback_response.content
            fallback_end = datetime.utcnow()

            spans.append({
                "trace_id": trace_id,
                "span_id": fallback_span_id,
                "parent_id": root_span_id,
                "name": "fallback_executor",
                "agent_id": "executor",
                "span_type": "agent",
                "status": "ok",
                "start_time": fallback_start.isoformat() + "Z",
                "end_time": fallback_end.isoformat() + "Z",
                "duration_ms": int((fallback_end - fallback_start).total_seconds() * 1000),
                "input_data": {"task": task_template['task'], "mode": "fallback"},
                "output_data": {"result": fallback_output[:300]},
                "is_fallback": True,
                "previous_errors": errors,
            })

            last_exec_end = fallback_end
            final_status = "partial_success"
        elif execution_success:
            final_status = "success"
        else:
            final_status = "failed"

        # F14: Premature completion - mark as complete despite issues
        if failure_mode == "F14" and inject_failure:
            final_status = "success"  # Falsely claiming success

        # Root span
        root_end = last_exec_end + timedelta(milliseconds=30)
        spans.insert(0, {
            "trace_id": trace_id,
            "span_id": root_span_id,
            "parent_id": None,
            "name": "workflow.recovery",
            "agent_id": "orchestrator",
            "span_type": "chain",
            "status": "ok",
            "start_time": start_time.isoformat() + "Z",
            "end_time": root_end.isoformat() + "Z",
            "duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "input_data": {"task": task_template['task'], "context": task_template['context']},
            "output_data": {"final_status": final_status},
            "workflow_type": "recovery",
            "total_retries": actual_retries,
            "used_fallback": not execution_success and should_fail_initially,
            "errors_encountered": len(errors),
            "metadata": {
                "failure_mode": failure_mode,
                "failure_injected": inject_failure and failure_mode is not None,
            }
        })

        return {
            "trace_id": trace_id,
            "workflow_type": "recovery",
            "failure_mode": failure_mode,
            "spans": spans,
            "total_duration_ms": int((root_end - start_time).total_seconds() * 1000),
            "span_count": len(spans),
            "retry_count": actual_retries,
            "used_fallback": not execution_success and should_fail_initially,
        }

    async def generate_all_workflow_traces(
        self,
        traces_per_workflow: int = 10,
        include_healthy: bool = True,
        include_failures: bool = True,
        concurrency: int = 5,
    ) -> list[dict]:
        """Generate traces for both workflows with and without failure injection."""

        all_traces = []
        semaphore = asyncio.Semaphore(concurrency)

        async def generate_with_semaphore(coro, desc: str):
            async with semaphore:
                try:
                    result = await coro
                    print(f"  ✓ {desc}", flush=True)
                    return result
                except Exception as e:
                    print(f"  ✗ {desc}: {e}")
                    return None

        tasks = []

        # Generate pipeline workflow traces
        print("\n" + "="*60)
        print("Generating Pipeline Workflow Traces")
        print("="*60)

        for i in range(traces_per_workflow):
            task_template = PIPELINE_TASKS[i % len(PIPELINE_TASKS)]

            if include_healthy:
                tasks.append(generate_with_semaphore(
                    self.generate_pipeline_trace(task_template, failure_mode=None, inject_failure=False),
                    f"Pipeline healthy #{i+1}"
                ))

            if include_failures:
                # F13: Quality Gate Bypass
                tasks.append(generate_with_semaphore(
                    self.generate_pipeline_trace(task_template, failure_mode="F13", inject_failure=True),
                    f"Pipeline F13 #{i+1}"
                ))

                # F11: Coordination Failure (simulated via validation issues)
                if i % 2 == 0:
                    tasks.append(generate_with_semaphore(
                        self.generate_pipeline_trace(task_template, failure_mode="F11", inject_failure=True),
                        f"Pipeline F11 #{i+1}"
                    ))

        # Generate recovery workflow traces
        print("\n" + "="*60)
        print("Generating Recovery Workflow Traces")
        print("="*60)

        for i in range(traces_per_workflow):
            task_template = RECOVERY_TASKS[i % len(RECOVERY_TASKS)]

            if include_healthy:
                tasks.append(generate_with_semaphore(
                    self.generate_recovery_trace(task_template, failure_mode=None, inject_failure=False),
                    f"Recovery healthy #{i+1}"
                ))

            if include_failures:
                # F5: Flawed Workflow Design (missing error handling)
                tasks.append(generate_with_semaphore(
                    self.generate_recovery_trace(task_template, failure_mode="F5", inject_failure=True, force_retries=2),
                    f"Recovery F5 #{i+1}"
                ))

                # F14: Completion Misjudgment (premature completion)
                if i % 2 == 0:
                    tasks.append(generate_with_semaphore(
                        self.generate_recovery_trace(task_template, failure_mode="F14", inject_failure=True),
                        f"Recovery F14 #{i+1}"
                    ))

        # Execute all tasks
        results = await asyncio.gather(*tasks)
        all_traces = [t for t in results if t is not None]

        # Save traces
        output_file = self.output_dir / "workflow_traces.jsonl"
        with open(output_file, "w") as f:
            for trace in all_traces:
                for span in trace["spans"]:
                    span["_trace_metadata"] = {
                        "workflow_type": trace["workflow_type"],
                        "failure_mode": trace["failure_mode"],
                    }
                    f.write(json.dumps(span) + "\n")

        print(f"\n{'='*60}")
        print(f"COMPLETE: Generated {len(all_traces)} traces ({sum(t['span_count'] for t in all_traces)} spans)")
        print(f"Saved to {output_file}")
        print(f"{'='*60}")

        # Summary
        pipeline_count = len([t for t in all_traces if t["workflow_type"] == "pipeline"])
        recovery_count = len([t for t in all_traces if t["workflow_type"] == "recovery"])
        healthy_count = len([t for t in all_traces if t["failure_mode"] is None])
        failure_count = len([t for t in all_traces if t["failure_mode"] is not None])

        print(f"\nSummary:")
        print(f"  Pipeline traces: {pipeline_count}")
        print(f"  Recovery traces: {recovery_count}")
        print(f"  Healthy traces: {healthy_count}")
        print(f"  Failure traces: {failure_count}")

        return all_traces


async def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        return

    generator = WorkflowTraceGenerator(
        api_key=api_key,
        output_dir="traces"
    )

    traces = await generator.generate_all_workflow_traces(
        traces_per_workflow=10,
        include_healthy=True,
        include_failures=True,
        concurrency=5,
    )

    return traces


if __name__ == "__main__":
    asyncio.run(main())
